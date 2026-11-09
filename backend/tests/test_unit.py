import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app import cache, security
from app.admin.permissions import ALL_PERMISSIONS, DEFAULT_ROLES, PERMISSION_DOMAINS
from app.config import Settings
from app.content.service import haversine_m


def test_permissions_32_over_9_domains():
    assert len(ALL_PERMISSIONS) == 32 and len(PERMISSION_DOMAINS) == 9
    assert len(set(ALL_PERMISSIONS)) == 32


def test_default_roles():
    names = {r["name"]: r for r in DEFAULT_ROLES}
    assert set(names) == {"super_admin", "admin", "poi_owner", "user"}
    assert names["super_admin"]["permissions"] == ALL_PERMISSIONS
    assert [names[n]["priority"] for n in ("super_admin", "admin", "poi_owner", "user")] == [0, 1, 10, 100]
    assert "user:delete" not in names["poi_owner"]["permissions"]


def test_password_hash_roundtrip():
    h = security.hash_password("Secret123")
    assert h != "Secret123" and security.verify_password("Secret123", h)
    assert not security.verify_password("wrong", h)
    assert not security.verify_password("x", "not-a-hash")


def test_jwt_types_and_expiry():
    a = security.create_token({"sub": 1}, "access")
    assert security.decode_token(a, "access")["sub"] == 1  # id số: lưu dạng chuỗi trong JWT, giải mã lại thành int
    assert security.decode_token(a, "refresh") is None  # sai loại / sai secret
    expired = jwt.encode({"sub": "1", "type": "access", "exp": datetime.now(timezone.utc) - timedelta(seconds=5)},
                         security.settings.jwt_secret, algorithm="HS256")
    assert security.decode_token(expired, "access") is None
    assert security.decode_token("garbage", "access") is None


def test_pii_encrypt_decrypt():
    enc = security.encrypt_pii("012345678901")
    assert enc.startswith("v1:") and "012345678901" not in enc
    assert security.decrypt_pii(enc) == "012345678901"
    assert security.decrypt_pii("v1:corrupted") is None
    assert security.decrypt_pii(None) is None


def test_non_dev_fail_fast():
    with pytest.raises(RuntimeError):
        Settings(app_env="prod").assert_secure()
    with pytest.raises(RuntimeError):
        Settings(app_env="prod", jwt_secret="a" * 20, refresh_token_secret="b" * 20, secret_key="c" * 20).assert_secure()
    Settings(app_env="prod", jwt_secret="a" * 20, refresh_token_secret="b" * 20, secret_key="c" * 20,
             superadmin_password="longpassword").assert_secure()
    Settings(app_env="dev").assert_secure()


def test_haversine():
    assert haversine_m(10.76, 106.70, 10.76, 106.70) == 0
    assert 100 < haversine_m(10.7600, 106.7000, 10.7610, 106.7000) < 120


async def test_rate_limit_memory_fallback(monkeypatch):
    async def no_redis():
        return None
    monkeypatch.setattr(cache, "_r", no_redis)
    key = f"unit:{time.time()}"
    assert [await cache.rate_hit(key, 3, 60) for _ in range(3)] == [None, None, None]
    assert await cache.rate_hit(key, 3, 60) >= 1
    await cache.presence_touch("devunit0001")
    assert await cache.presence_count() >= 1


async def test_pii_redaction_after_retention():
    from app.admin import service
    from app.db import close_db, connect_db, get_db
    await connect_db()
    try:
        db = get_db()
        await db.execute("DELETE FROM admin_users WHERE username='pii-test-user'")  # cascade xoá đơn đăng ký
        uid = await db.insert("admin_users", {"username": "pii-test-user", "password_hash": "x",
                                              "role": "user", "created_at": datetime.now(timezone.utc)})
        old = {"user_id": uid, "shop_name": "s", "phone": "0900000000",
               "cccd_encrypted": security.encrypt_pii("123456789"), "status": "pending",
               "created_at": datetime.now(timezone.utc) - timedelta(days=181)}
        new = {**old, "created_at": datetime.now(timezone.utc) - timedelta(days=10)}
        old_id = await db.insert("poi_owner_registrations", old)
        new_id = await db.insert("poi_owner_registrations", new)
        assert await service.redact_expired_pii() >= 1
        get = lambda i: db.fetchone("SELECT cccd_encrypted FROM poi_owner_registrations WHERE id=%s", [i])
        assert (await get(old_id))["cccd_encrypted"] is None
        assert (await get(new_id))["cccd_encrypted"].startswith("v1:")
        await db.execute("DELETE FROM admin_users WHERE id=%s", [uid])
    finally:
        await close_db()


def test_translation_chunks_respect_byte_limit():
    from app.audio.service import _chunks
    text = ". ".join(["Bánh xèo vàng giòn nhân tôm thịt rất ngon"] * 30)
    parts = _chunks(text, 450)
    assert len(parts) > 1 and all(len(p.encode()) <= 450 for p in parts)
    assert _chunks("Một câu ngắn.") == ["Một câu ngắn."]


async def test_translation_provider_fallback_and_cache(monkeypatch):
    from app.audio import service as audio
    from app.db import close_db, connect_db, get_db
    calls = []

    async def bad(text, target):
        calls.append("gtx")
        raise RuntimeError("429")

    async def good(text, target):
        calls.append("mymemory")
        return f"[{target}] {text}"

    async def no_gemini(text, target):
        raise RuntimeError("no key")  # Gemini là nhà cung cấp đầu chuỗi; test này kiểm tra gtx → mymemory

    monkeypatch.setattr(audio, "_gemini_translate", no_gemini)
    monkeypatch.setattr(audio, "_gtx_translate", bad)
    monkeypatch.setattr(audio, "_mymemory_translate", good)
    await connect_db()
    try:
        text = f"chuoi-thu-nghiem-{time.time()}"
        assert await audio.translate_text(text, "en") == f"[en] {text}"
        assert calls == ["gtx", "mymemory"]  # gtx lỗi → rơi sang MyMemory
        assert await audio.translate_text(text, "en") == f"[en] {text}"
        assert calls == ["gtx", "mymemory"]  # lần 2 lấy từ cache, không gọi nhà cung cấp
        assert await audio.translate_text(text, "vi") == text
        await get_db().execute("DELETE FROM translation_cache WHERE lang='en' AND text=%s", [f"[en] {text}"])
    finally:
        await close_db()


# ---------- AI advisor: kiểm tra xác định, không gọi Gemini thật ----------
class _FakeResp:
    def __init__(self, status, payload=None):
        self.status_code, self._p = status, payload

    def json(self):
        if self._p is None:
            raise ValueError("no json")
        return self._p


def _fake_client(result):
    class C:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **k):
            if isinstance(result, Exception):
                raise result
            return result
    return C


async def test_ai_advisor_provider_paths_and_quota(monkeypatch):
    import httpx
    from fastapi import HTTPException
    from app.ai_advisor import router as ai
    from app.db import close_db, connect_db, get_db

    await connect_db()
    owner = {"sub": 900000001, "role": "poi_owner", "permissions": ["owner:access"]}
    body = ai.Enhance(name="Quán", description="Ngon")
    db = get_db()
    await db.execute("DELETE FROM ai_usage_limits WHERE user_id=%s", [900000001])
    try:
        async def used():
            return (await ai.usage(owner))["used"]

        # 1. chưa cấu hình key → 503 provider_unconfigured, không tốn quota
        monkeypatch.setattr(ai.settings, "gemini_api_key", "")
        with pytest.raises(HTTPException) as e:
            await ai.enhance(body, owner)
        assert e.value.status_code == 503 and e.value.detail["code"] == "provider_unconfigured"
        assert await used() == 0

        monkeypatch.setattr(ai.settings, "gemini_api_key", "fake-key")
        # 2. các lỗi provider → mã rõ ràng, không tốn quota
        for result, status, code in [
            (httpx.TimeoutException("t"), 504, "provider_timeout"),
            (httpx.ConnectError("c"), 502, "provider_unreachable"),
            (_FakeResp(500), 502, "provider_error"),
            (_FakeResp(200, {"candidates": []}), 502, "provider_bad_response"),
        ]:
            monkeypatch.setattr(ai.httpx, "AsyncClient", _fake_client(result))
            with pytest.raises(HTTPException) as e:
                await ai.enhance(body, owner)
            assert (e.value.status_code, e.value.detail["code"]) == (status, code)
        assert await used() == 0

        # 3. thành công → trừ đúng 1 lượt; hết 10 lượt → 429
        ok = _FakeResp(200, {"candidates": [{"content": {"parts": [{"text": " Mô tả mới "}]}}]})
        monkeypatch.setattr(ai.httpx, "AsyncClient", _fake_client(ok))
        assert (await ai.enhance(body, owner))["description"] == "Mô tả mới"
        assert await used() == 1
        for _ in range(9):
            await ai.enhance(body, owner)
        with pytest.raises(HTTPException) as e:
            await ai.enhance(body, owner)
        assert e.value.status_code == 429
        assert (await ai.usage(owner)) == {"limit": 10, "used": 10, "remaining": 0}

        # 4. admin không giới hạn
        admin = {"sub": 900000002, "role": "admin", "permissions": ["poi:update"]}
        assert (await ai.usage(admin))["limit"] is None
        # 5. user thường bị chặn
        with pytest.raises(HTTPException) as e:
            await ai.enhance(body, {"sub": 900000003, "role": "user", "permissions": ["poi:read"]})
        assert e.value.status_code == 403
    finally:
        await db.execute("DELETE FROM ai_usage_limits WHERE user_id IN (%s,%s)", [900000001, 900000002])
        await close_db()


async def test_ui_bundle_translation_failure_is_not_cached_as_ready(monkeypatch):
    from app.db import close_db, connect_db, get_db
    from app.ui_i18n import router as ui
    await connect_db()
    try:
        db = get_db()
        await db.execute("DELETE FROM ui_translation_bundles WHERE locale=%s", ["zz"])

        async def all_fail(locale):
            return dict(ui.EN), len(ui.EN)  # mọi chuỗi lỗi → vẫn tiếng Anh

        monkeypatch.setattr(ui, "translate_bundle", all_fail)
        ui._inflight.add("zz")
        await ui._translate_and_store("zz")
        assert await db.fetchone("SELECT id FROM ui_translation_bundles WHERE locale=%s", ["zz"]) is None  # không lưu bản hỏng
        assert "zz" in ui._retry_after and "zz" not in ui._inflight

        async def mostly_ok(locale):
            return {k: f"[{locale}] {v}" for k, v in ui.EN.items()}, 0

        monkeypatch.setattr(ui, "translate_bundle", mostly_ok)
        ui._inflight.add("zz")
        await ui._translate_and_store("zz")
        rec = await db.fetchone("SELECT * FROM ui_translation_bundles WHERE locale=%s", ["zz"])
        assert rec["status"] == "ready" and rec["strings"]["app.title"].startswith("[zz]")
        await db.execute("DELETE FROM ui_translation_bundles WHERE locale=%s", ["zz"])
        ui._retry_after.pop("zz", None)
    finally:
        await close_db()


def test_demo_data_is_consistent():
    """Dữ liệu demo toàn TP.HCM: tên duy nhất, toạ độ trong TP, không chồng vùng kích hoạt, đủ thực đơn và khu vực."""
    from app.content.demo_data import DEMO_MENUS, DEMO_POIS
    from app.content.demo_data_hcm import AREAS, DEMO_MENUS_HCM, DEMO_POIS_HCM
    from app.content.seed import _RAW
    from app.content.service import haversine_m

    core = [r[0] for r in _RAW] + [p["name"] for p in DEMO_POIS]
    names = core + [p["name"] for p in DEMO_POIS_HCM]
    assert len(core) == 20 and len(DEMO_POIS_HCM) == 4 * len(AREAS) == 60
    assert len(names) == len(set(names)) == 80
    coords = [(r[2], r[3]) for r in _RAW] + [(p["lat"], p["lng"]) for p in DEMO_POIS + DEMO_POIS_HCM]
    for i, a in enumerate(coords):
        assert 10.65 < a[0] < 10.90 and 106.55 < a[1] < 106.85, a  # trong phạm vi TP.HCM
        for b in coords[i + 1:]:
            assert haversine_m(*a, *b) > 60, (a, b)  # > 2 × bán kính mặc định 30 m
    for p in DEMO_POIS + DEMO_POIS_HCM:
        assert 20 <= len(p["description"]) <= 3000 and 1 <= p["audio_priority"] <= 9
    for p in DEMO_POIS_HCM:
        assert p["area"] in AREAS
        # quán nằm gần tâm khu vực của nó (< 400 m)
        assert haversine_m(p["lat"], p["lng"], *AREAS[p["area"]]) < 400
    menus = {**DEMO_MENUS, **DEMO_MENUS_HCM}
    assert set(menus) == set(names)  # đủ 80 quán, không thừa
    for poi_name, items in menus.items():
        assert len(items) >= 3 and len({n for n, _ in items}) == len(items)
        assert all(price > 0 and price % 1000 == 0 for _, price in items)
