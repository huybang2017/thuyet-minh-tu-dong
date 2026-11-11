"""Test tích hợp cho các chức năng bổ sung: ảnh quán, quên mật khẩu, thực đơn cho du khách, xuất thống kê."""
import time

import pytest

from conftest import make_client, uid

A = "/api/v1/admin"
POI_BODY = {"name": "Quán Test Ảnh", "description": "Quán thử nghiệm ảnh.", "lat": 10.7611, "lng": 106.7040}
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360f8cfc0f01f0005000201e2b1f6a30000000049454e44ae426082")


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    import redis
    rc = redis.Redis.from_url("redis://redis:6379/0")
    for pat in ("rl:login:*", "rl:collect:*", "rl:forgot:*", "rl:reset:*", "rl:upload:*"):
        for k in rc.scan_iter(pat):
            rc.delete(k)
    yield


def _first_poi(admin):
    return next(p for p in admin.get(f"{A}/pois").json()["items"] if p["is_active"])["id"]


def _poi_state(admin, pid):
    return next(p for p in admin.get(f"{A}/pois").json()["items"] if p["id"] == pid)


def _png(c, body=PNG_1PX, ctype="image/png"):
    return c.post("/api/v1/media/images", content=body, headers={"Content-Type": ctype})


# ---------- ảnh quán ----------
def test_image_upload_validation(admin, anon, make_user):
    assert _png(anon).status_code == 401
    assert _png(make_user("user")).status_code == 403
    assert _png(make_user("poi_owner")).status_code == 201  # owner do admin tạo = đã xác minh
    # magic bytes quyết định, không tin Content-Type → SVG giả PNG bị chặn
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    assert _png(admin, svg).status_code == 415
    assert _png(admin, b"").status_code == 422
    assert _png(admin, PNG_1PX + b"\0" * (2 * 1024 * 1024)).status_code == 413
    r = _png(admin, ctype="application/octet-stream")
    assert r.status_code == 201
    url = r.json()["url"]
    assert url.startswith("/static/images/") and url.endswith(".png")
    assert _png(admin).json()["url"] == url  # nội dung trùng → cùng file
    got = anon.get(url)
    assert got.status_code == 200 and got.content == PNG_1PX


def test_poi_images_only_uploaded_and_no_audio_regen(admin, anon):
    url = _png(admin).json()["url"]
    assert admin.post(f"{A}/pois", json={**POI_BODY, "images": ["https://evil.example/x.png"]}).status_code == 422
    assert admin.post(f"{A}/pois", json={**POI_BODY, "images": ["/static/images/../../app/main.py"]}).status_code == 422
    assert admin.post(f"{A}/pois", json={**POI_BODY, "images": [url] * 9}).status_code == 422
    pid = _first_poi(admin)
    before = _poi_state(admin, pid)
    try:
        r = admin.put(f"{A}/pois/{pid}", json={"images": [url, url]})
        assert r.status_code == 200 and r.json()["images"] == [url]  # bỏ trùng
        after = _poi_state(admin, pid)
        assert after["is_active"] == before["is_active"] and after["audio_status"] == before["audio_status"]
        pub = next(p for p in anon.get("/api/v1/poi/load-all?lang=vi").json()["pois"] if p["id"] == pid)
        assert pub["images"] == [url]
    finally:
        admin.put(f"{A}/pois/{pid}", json={"images": before.get("images") or []})


# ---------- quên mật khẩu ----------
def _token(res: dict) -> str:
    return res["dev_reset_url"].split("token=")[1]


def test_forgot_and_reset_password(admin, anon, sql):
    name, email, pw = uid("u"), f"{uid('e')}@example.com", "Passw0rd!x"
    r = admin.post(f"{A}/users", json={"username": name, "password": pw, "role": "user", "email": email})
    assert r.status_code == 201
    user_id = r.json()["id"]
    try:
        # tài khoản không tồn tại → cùng thông điệp, không phát hành link
        ghost = anon.post(f"{A}/auth/forgot-password", json={"identifier": "khong-ai-ca"}).json()
        assert ghost["ok"] and "dev_reset_url" not in ghost
        old = make_client()
        assert old.post(f"{A}/auth/login", json={"username": name, "password": pw}).status_code == 200

        res = anon.post(f"{A}/auth/forgot-password", json={"identifier": email}).json()
        assert res["message"] == ghost["message"]
        token = _token(res)
        rec = sql.one("SELECT * FROM password_resets WHERE user_id=%s", [user_id])
        assert rec and rec["token_hash"] != token  # DB chỉ giữ hash

        bad = anon.post(f"{A}/auth/reset-password", json={"token": "x" * 30, "new_password": "NewPassw0rd!"})
        assert bad.status_code == 400
        assert anon.post(f"{A}/auth/reset-password", json={"token": token, "new_password": "short"}).status_code == 422
        time.sleep(1.1)  # iat tính theo giây: tách phiên cũ khỏi thời điểm đổi mật khẩu
        assert anon.post(f"{A}/auth/reset-password", json={"token": token, "new_password": "NewPassw0rd!"}).status_code == 200
        # token chỉ dùng được một lần
        assert anon.post(f"{A}/auth/reset-password", json={"token": token, "new_password": "Another0ne!"}).status_code == 400

        c = make_client()
        assert c.post(f"{A}/auth/login", json={"username": name, "password": pw}).status_code == 401
        assert c.post(f"{A}/auth/login", json={"username": name, "password": "NewPassw0rd!"}).status_code == 200
        assert old.post(f"{A}/auth/refresh").status_code == 401  # phiên cũ bị vô hiệu
        assert c.post(f"{A}/auth/refresh").status_code == 200

        # yêu cầu mới huỷ token cũ chưa dùng
        t1 = _token(anon.post(f"{A}/auth/forgot-password", json={"identifier": name}).json())
        anon.post(f"{A}/auth/forgot-password", json={"identifier": name})
        assert anon.post(f"{A}/auth/reset-password", json={"token": t1, "new_password": "NewPassw0rd!2"}).status_code == 400

        codes = [anon.post(f"{A}/auth/forgot-password", json={"identifier": name}).status_code for _ in range(4)]
        assert 429 in codes
    finally:
        admin.delete(f"{A}/users/{user_id}")
        sql.exec("DELETE FROM password_resets WHERE user_id=%s", [user_id])


def test_change_password_keeps_current_session(make_user):
    c = make_user("user")
    time.sleep(1.1)
    r = c.post(f"{A}/auth/change-password", json={"old_password": "Passw0rd!x", "new_password": "NewPassw0rd!"})
    assert r.status_code == 200
    assert c.post(f"{A}/auth/refresh").status_code == 200  # phiên hiện tại được cấp cookie mới


def test_delete_user_removes_personal_data(admin, anon, sql):
    body = {"username": uid("own"), "email": f"{uid('e')}@example.com", "password": "Passw0rd!x",
            "display_name": "Chủ Quán", "shop_name": "Quán Xoá", "phone": "0901234567"}
    assert anon.post(f"{A}/auth/register-owner", json=body).status_code == 201
    user_id = sql.one("SELECT id FROM admin_users WHERE username=%s", [body["username"]])["id"]
    reg = sql.one("SELECT id FROM poi_owner_registrations WHERE user_id=%s", [user_id])
    assert admin.post(f"{A}/registrations/{reg['id']}/reject", json={"admin_note": "x"}).status_code == 200
    assert sql.scalar("SELECT COUNT(*) FROM owner_notifications WHERE owner_id=%s", [user_id]) == 1
    assert admin.delete(f"{A}/users/{user_id}").status_code == 200
    assert sql.scalar("SELECT COUNT(*) FROM poi_owner_registrations WHERE user_id=%s", [user_id]) == 0
    assert sql.scalar("SELECT COUNT(*) FROM owner_notifications WHERE owner_id=%s", [user_id]) == 0


# ---------- thực đơn cho du khách ----------
def test_public_menu_translated_and_hidden_for_inactive(admin, anon, sql):
    pid = sql.scalar("SELECT m.poi_id FROM menu_items m JOIN poi p ON p.id=m.poi_id WHERE p.is_active=1 AND p.deleted_at IS NULL "
                     "AND m.deleted_at IS NULL GROUP BY m.poi_id ORDER BY COUNT(*) DESC LIMIT 1")
    assert pid, "cần ít nhất một quán có thực đơn (seed demo)"
    assert admin.post(f"{A}/menus", json={"poi_id": pid, "name": "x", "price": 1, "description": "x" * 301}).status_code == 422
    vi = anon.get(f"/api/v1/poi/{pid}/menu").json()
    assert vi["lang"] == "vi" and vi["items"] and all(i["name_translated"] is None for i in vi["items"])
    prices = [i["price"] for i in vi["items"]]
    assert prices == sorted(prices)
    en = anon.get(f"/api/v1/poi/{pid}/menu?lang=en").json()
    assert en["lang"] == "en" and {"name", "name_translated", "price"} <= set(en["items"][0])
    assert anon.get(f"/api/v1/poi/{pid}/menu?lang=xx").json()["lang"] == "vi"
    assert anon.get("/api/v1/poi/99999999/menu").status_code == 404
    assert admin.post(f"{A}/pois/{pid}/toggle", json={"active": False}).status_code == 200
    try:
        assert anon.get(f"/api/v1/poi/{pid}/menu").status_code == 404  # quán ẩn → không lộ thực đơn
    finally:
        admin.post(f"{A}/pois/{pid}/toggle", json={"active": True})


# ---------- xuất thống kê ----------
def test_analytics_export_csv(admin, anon, make_user, sql):
    poi = sql.one("SELECT id, name FROM poi WHERE is_active=1 AND deleted_at IS NULL ORDER BY id LIMIT 1")
    dev = uid("dev") + "0000"
    ev = {"consent": True, "device_id": dev, "event": "narration_played", "poi_id": poi["id"], "lang": "ja"}
    assert anon.post("/api/v1/analytics/collect", json=ev).status_code == 202
    assert anon.get("/api/v1/analytics/export").status_code == 401
    assert make_user("poi_owner").get("/api/v1/analytics/export").status_code == 403
    assert admin.get("/api/v1/analytics/export?days=0").status_code == 422
    r = admin.get("/api/v1/analytics/export?days=7")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"] and ".csv" in r.headers["content-disposition"]
    text = r.content.decode("utf-8")
    assert text.startswith("﻿")
    lines = text.lstrip("﻿").splitlines()
    assert lines[0] == "ngay,su_kien,poi_id,ten_quan,ngon_ngu,so_luot,so_thiet_bi"
    assert any(f",narration_played,{poi['id']},{poi['name']},ja," in line for line in lines[1:])
    top = admin.get("/api/v1/analytics/summary").json()["top_pois"]
    assert top and "name" in top[0]
