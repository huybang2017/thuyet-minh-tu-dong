import json

import pytest

from conftest import make_client, uid, wait_for

A = "/api/v1/admin"


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Test tạo nhiều tài khoản từ cùng IP → xoá bộ đếm rate limit để không bị 429 giả."""
    import redis
    rc = redis.Redis.from_url("redis://redis:6379/0")
    for pat in ("rl:regowner:*", "rl:login:*", "rl:collect:*", "rl:loc:*"):
        for k in rc.scan_iter(pat):
            rc.delete(k)
    yield
POI_BODY = {"name": "Quán Test Cơm Tấm", "description": "Cơm tấm sườn bì chả thơm ngon, nước mắm pha đậm đà.",
            "lat": 10.7611, "lng": 106.7040}


# ---------- health / auth ----------
def test_health_ready(anon):
    r = anon.get("/health/ready").json()
    assert r["status"] == "ready" and r["routers"] == 9


def test_login_flow_and_cookies(anon, admin):
    c = make_client()
    assert c.post(f"{A}/auth/login", json={"username": "admin", "password": "nope"}).status_code == 401
    r = c.post(f"{A}/auth/login", json={"username": "admin", "password": "admin12345"})
    assert r.status_code == 200
    set_cookie = r.headers.get_list("set-cookie")
    assert any("access_token" in h and "HttpOnly" in h and "SameSite=lax" in h for h in set_cookie)
    assert any("refresh_token" in h and "HttpOnly" in h for h in set_cookie)
    me = c.get(f"{A}/auth/me").json()
    assert me["user"]["username"] == "admin" and len(me["permissions"]) == 32
    assert anon.get(f"{A}/auth/me").status_code == 401
    # Bearer fallback
    tok = c.cookies["access_token"]
    assert anon.get(f"{A}/auth/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    assert anon.get(f"{A}/auth/me", headers={"Authorization": "Bearer junk"}).status_code == 401
    assert c.post(f"{A}/auth/refresh").status_code == 200
    c.post(f"{A}/auth/logout")
    assert c.get(f"{A}/auth/me").status_code == 401


def test_change_password(admin, make_user):
    c = make_user("user")
    assert c.post(f"{A}/auth/change-password", json={"old_password": "bad", "new_password": "NewPassw0rd!"}).status_code == 400
    assert c.post(f"{A}/auth/change-password", json={"old_password": "Passw0rd!x", "new_password": "short"}).status_code == 422
    assert c.post(f"{A}/auth/change-password", json={"old_password": "Passw0rd!x", "new_password": "NewPassw0rd!"}).status_code == 200


# ---------- RBAC ----------
def test_rbac_matrix(admin, make_user, anon):
    plain = make_user("user")
    assert plain.get(f"{A}/pois").status_code == 200  # poi:read
    assert plain.post(f"{A}/pois", json=POI_BODY).status_code == 403
    assert plain.get(f"{A}/users").status_code == 403
    assert plain.get(f"{A}/roles").status_code == 403
    assert plain.get(f"{A}/audit-logs").status_code == 403
    assert anon.get(f"{A}/pois").status_code == 401
    mgr = make_user("admin")
    assert mgr.get(f"{A}/users").status_code == 200
    assert mgr.get(f"{A}/roles").status_code == 403  # admin mặc định không có role:*
    r = mgr.post(f"{A}/users", json={"username": uid("sa"), "password": "Passw0rd!x", "role": "super_admin"})
    assert r.status_code == 403  # admin không tự nâng lên super_admin


def test_roles_crud_and_guards(admin):
    perms = admin.get(f"{A}/permissions").json()
    assert len(perms["all"]) == 32
    roles = {r["name"] for r in admin.get(f"{A}/roles").json()["items"]}
    assert {"super_admin", "admin", "poi_owner", "user"} <= roles
    name = uid("role").lower()
    assert admin.post(f"{A}/roles", json={"name": name, "permissions": ["bogus:perm"]}).status_code == 422
    assert admin.post(f"{A}/roles", json={"name": name, "permissions": ["poi:read"]}).status_code == 201
    assert admin.post(f"{A}/roles", json={"name": name, "permissions": ["poi:read"]}).status_code == 409
    assert admin.put(f"{A}/roles/{name}", json={"permissions": ["poi:read", "menu:read"]}).status_code == 200
    assert admin.put(f"{A}/roles/super_admin", json={"priority": 5}).status_code == 400
    assert admin.delete(f"{A}/roles/admin").status_code == 400
    assert admin.delete(f"{A}/roles/{name}").status_code == 200
    assert admin.delete(f"{A}/roles/{name}").status_code == 404


def test_users_crud_and_guards(admin):
    name = uid("usr")
    r = admin.post(f"{A}/users", json={"username": name, "password": "Passw0rd!x", "role": "user"})
    assert r.status_code == 201
    uid_ = r.json()["id"]
    assert "password_hash" not in r.text
    assert admin.post(f"{A}/users", json={"username": name, "password": "Passw0rd!x", "role": "user"}).status_code == 409
    assert admin.post(f"{A}/users", json={"username": uid("x"), "password": "Passw0rd!x", "role": "ghost"}).status_code == 422
    assert admin.post(f"{A}/users", json={"username": "a b", "password": "Passw0rd!x", "role": "user"}).status_code == 422
    assert admin.put(f"{A}/users/{uid_}", json={"is_active": False}).status_code == 200
    assert make_client().post(f"{A}/auth/login", json={"username": name, "password": "Passw0rd!x"}).status_code == 403
    me = admin.get(f"{A}/auth/me").json()["user"]["id"]
    assert admin.delete(f"{A}/users/{me}").status_code == 400
    assert admin.put(f"{A}/users/{me}", json={"is_active": False}).status_code == 400
    assert admin.delete(f"{A}/users/{uid_}").status_code == 200
    assert admin.delete(f"{A}/users/{uid_}").status_code == 404


def test_login_rate_limit():
    c = make_client()
    name = uid("rl")
    codes = [c.post(f"{A}/auth/login", json={"username": name, "password": "x"}).status_code for _ in range(12)]
    assert codes[0] == 401 and 429 in codes


# ---------- POI lifecycle ----------
def _poi_state(admin, pid):
    return next((p for p in admin.get(f"{A}/pois").json()["items"] if p["id"] == pid), None)


def test_poi_validation(admin):
    assert admin.post(f"{A}/pois", json={**POI_BODY, "lat": 200}).status_code == 422
    assert admin.post(f"{A}/pois", json={**POI_BODY, "name": ""}).status_code == 422
    assert admin.post(f"{A}/pois", json={**POI_BODY, "trigger_radius": 1}).status_code == 422
    assert admin.put(f"{A}/pois/khong-ton-tai", json={"name": "x"}).status_code == 404
    assert admin.delete(f"{A}/pois/khong-ton-tai").status_code == 404


def test_poi_lifecycle_activation_gate_delta_and_delete(admin, anon, mongo):
    r = admin.post(f"{A}/pois", json=POI_BODY)
    assert r.status_code == 201
    pid = r.json()["id"]
    try:
        st = _poi_state(admin, pid)
        # activation gate: chưa public khi audio chưa sẵn sàng
        assert st["is_active"] is False and st["audio_status"] == "processing" and st["activation_requested"] is True
        pub = anon.get("/api/v1/poi/load-all?lang=vi").json()["pois"]
        assert pid not in [p["id"] for p in pub]
        st = wait_for(lambda: (s := _poi_state(admin, pid)) and s["audio_status"] == "ready" and s)
        assert st["is_active"] is True
        assert mongo.poi_localizations.count_documents({"poi_id": pid}) == 5
        en = anon.get("/api/v1/poi/load-all?lang=en").json()["pois"]
        mine = next(p for p in en if p["id"] == pid)
        assert mine["lang"] == "en" and mine["is_fallback"] is False and mine["audio_url"].startswith("/static/audio/")
        assert "?v=" in mine["audio_url"] and "&l=en" in mine["audio_url"]
        assert "owner_id" not in mine and "location" not in mine

        # đổi mô tả → xoá audio cũ, khoá public, sinh lại rồi tự kích hoạt lại
        before = mine["audio_url"]
        r = admin.put(f"{A}/pois/{pid}", json={"description": "Cơm tấm sườn nướng than hoa, thêm trứng ốp la."})
        assert r.status_code == 200
        st = _poi_state(admin, pid)
        assert st["is_active"] is False and st["audio_status"] == "processing"
        st = wait_for(lambda: (s := _poi_state(admin, pid)) and s["audio_status"] == "ready" and s["is_active"] and s)
        en2 = next(p for p in anon.get("/api/v1/poi/load-all?lang=en").json()["pois"] if p["id"] == pid)
        assert en2["audio_url"].split("?")[0] != before.split("?")[0]

        # ETag / 304 / delta
        full = anon.get("/api/v1/poi/load-all?lang=vi")
        etag = full.headers["etag"]
        assert anon.get("/api/v1/poi/load-all?lang=vi", headers={"If-None-Match": etag}).status_code == 304
        cursor = full.json()["sync_cursor"]
        admin.put(f"{A}/pois/{pid}", json={"audio_priority": 2})
        delta = anon.get("/api/v1/poi/load-all", params={"lang": "vi", "updated_after": cursor}).json()
        assert delta["sync_mode"] == "delta" and pid in [p["id"] for p in delta["pois"]]

        # tắt → delta báo removed; bật lại
        cursor = delta["sync_cursor"]
        assert admin.post(f"{A}/pois/{pid}/toggle", json={"active": False}).status_code == 200
        d2 = anon.get("/api/v1/poi/load-all", params={"lang": "vi", "updated_after": cursor}).json()
        assert pid in d2["removed_poi_ids"] and pid not in [p["id"] for p in d2["pois"]]
        assert admin.post(f"{A}/pois/{pid}/toggle", json={"active": True}).status_code == 200
        assert _poi_state(admin, pid)["is_active"] is True  # EN đã sẵn sàng → bật ngay

        # xoá → cascade + removed_poi_ids
        cursor = anon.get("/api/v1/poi/load-all?lang=vi").json()["sync_cursor"]
        assert admin.delete(f"{A}/pois/{pid}").status_code == 200
        assert mongo.poi_localizations.count_documents({"poi_id": pid}) == 0
        d3 = anon.get("/api/v1/poi/load-all", params={"lang": "vi", "updated_after": cursor}).json()
        assert pid in d3["removed_poi_ids"]
    finally:
        admin.delete(f"{A}/pois/{pid}")


def test_nearby_and_fallback_tiers(anon, admin):
    r = anon.get("/api/v1/poi/nearby", params={"lat": 10.7612, "lng": 106.7046, "radius": 100}).json()["pois"]
    assert r and r[0]["distance_m"] <= 100
    assert anon.get("/api/v1/poi/nearby", params={"lat": 0, "lng": 0, "radius": 100}).json()["pois"] == []
    assert anon.get("/api/v1/poi/nearby", params={"lat": 1, "lng": 1, "radius": 99999}).status_code == 422
    # ngôn ngữ chưa có bản dịch → rơi về EN/VI và đánh dấu is_fallback
    pois = anon.get("/api/v1/poi/load-all?lang=ja").json()["pois"]
    assert pois and all("is_fallback" in p for p in pois)


def test_menu_crud_and_public(admin, anon):
    pid = "poi-oc-oanh"
    assert admin.post(f"{A}/menus", json={"poi_id": "ghost", "name": "x", "price": 1}).status_code == 404
    assert admin.post(f"{A}/menus", json={"poi_id": pid, "name": "x", "price": -5}).status_code == 422
    m = admin.post(f"{A}/menus", json={"poi_id": pid, "name": "Ốc len xào dừa", "price": 65000})
    assert m.status_code == 201
    mid = m.json()["id"]
    assert admin.put(f"{A}/menus/{mid}", json={"price": 70000}).json()["price"] == 70000
    items = anon.get(f"/api/v1/poi/{pid}/menu").json()["items"]
    assert any(i["id"] == mid and i["price"] == 70000 for i in items)
    assert admin.delete(f"{A}/menus/{mid}").status_code == 200
    assert admin.delete(f"{A}/menus/{mid}").status_code == 404


# ---------- owner flow ----------
def _register(c, **over):
    body = {"username": uid("own"), "email": f"{uid('e')}@example.com", "password": "Passw0rd!x",
            "display_name": "Chủ Quán", "shop_name": "Quán Của Tôi", "phone": "0901234567", "cccd": "012345678901"}
    body.update(over)
    return body, c.post(f"{A}/auth/register-owner", json=body)


def test_owner_registration_validation(anon):
    assert _register(anon, cccd="abc")[1].status_code == 422
    assert _register(anon, email="not-an-email")[1].status_code == 422
    assert _register(anon, password="short")[1].status_code == 422
    assert _register(anon, phone="x")[1].status_code == 422
    body, r = _register(anon)
    assert r.status_code == 201
    assert anon.post(f"{A}/auth/register-owner", json=body).status_code == 409


def test_owner_full_flow(admin, anon, mongo):
    body, r = _register(anon)
    assert r.status_code == 201
    assert "012345678901" not in r.text and "cccd" not in r.json()
    reg = mongo.poi_owner_registrations.find_one({"shop_name": "Quán Của Tôi", "status": "pending"}, sort=[("created_at", -1)])
    assert reg["cccd_encrypted"].startswith("v1:") and "012345678901" not in reg["cccd_encrypted"]

    owner = make_client()
    assert owner.post(f"{A}/auth/login", json={"username": body["username"], "password": body["password"]}).status_code == 200
    # owner gate: chưa xác minh → chỉ lane registration-status
    assert owner.get("/api/v1/owner/pois").status_code == 403
    assert owner.post("/api/v1/owner/pois", json=POI_BODY).status_code == 403
    st = owner.get("/api/v1/owner/registration-status").json()
    assert st["status"] == "pending" and st["is_poi_owner_verified"] is False
    assert owner.get(f"{A}/pois").status_code == 200 and owner.post(f"{A}/pois", json=POI_BODY).status_code == 403

    regs = admin.get(f"{A}/registrations?status=pending").json()["items"]
    mine = next(x for x in regs if x["user_id"] == reg["user_id"])
    assert "cccd_encrypted" not in json.dumps(mine) and "012345678901" not in json.dumps(mine) and mine["has_cccd"] is True
    assert admin.post(f"{A}/registrations/{mine['id']}/approve", json={"admin_note": "Hồ sơ hợp lệ"}).status_code == 200
    assert admin.post(f"{A}/registrations/{mine['id']}/approve").status_code == 409

    notes = owner.get("/api/v1/owner/notifications").json()
    assert notes["unread"] >= 1 and "duyệt" in notes["items"][0]["title"]
    nid = notes["items"][0]["id"]
    assert owner.get(f"/api/v1/owner/notifications/{nid}").json()["body"] == "Hồ sơ hợp lệ"
    assert owner.post(f"/api/v1/owner/notifications/{nid}/read").status_code == 200
    assert owner.get("/api/v1/owner/notifications").json()["unread"] == notes["unread"] - 1

    # JWT cũ vẫn mang is_poi_owner_verified=false → cần refresh để nhận claims mới
    assert owner.get("/api/v1/owner/pois").status_code == 403
    assert owner.post(f"{A}/auth/refresh").status_code == 200
    assert owner.get("/api/v1/owner/pois").json()["items"] == []

    # owner gửi POI mới → chờ admin duyệt, chưa lên app
    r = owner.post("/api/v1/owner/pois", json={**POI_BODY, "name": "Quán Owner Test"})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert owner.get("/api/v1/owner/submissions").json()["items"][0]["status"] == "pending"
    assert not any(p["name"] == "Quán Owner Test" for p in anon.get("/api/v1/poi/load-all").json()["pois"])
    assert admin.post(f"{A}/submissions/{sid}/approve", json={"admin_note": "OK"}).status_code == 200
    assert admin.post(f"{A}/submissions/{sid}/reject").status_code == 409
    mypois = owner.get("/api/v1/owner/pois").json()["items"]
    assert len(mypois) == 1
    pid = mypois[0]["id"]
    try:
        # owner không sửa được quán người khác
        assert owner.put("/api/v1/owner/pois/poi-oc-oanh", json={"name": "Hack"}).status_code == 404
        assert owner.put(f"/api/v1/owner/pois/{pid}", json={}).status_code == 422
        r = owner.put(f"/api/v1/owner/pois/{pid}", json={"description": "Mô tả mới do chủ quán."})
        assert r.status_code == 200 and r.json()["status"] == "pending"
        sid2 = r.json()["id"]
        old_desc = mongo.poi.find_one({"_id": pid})["description"]
        assert old_desc != "Mô tả mới do chủ quán."  # chưa duyệt thì chưa đổi
        # reject → thông báo, dữ liệu giữ nguyên
        assert admin.post(f"{A}/submissions/{sid2}/reject", json={"admin_note": "Thiếu chi tiết"}).status_code == 200
        assert mongo.poi.find_one({"_id": pid})["description"] == old_desc
        assert owner.get("/api/v1/owner/notifications").json()["items"][0]["body"] == "Thiếu chi tiết"
        # owner không vào được admin
        assert owner.get(f"{A}/users").status_code == 403
        assert owner.get("/api/v1/owner/analytics").status_code == 200
    finally:
        admin.delete(f"{A}/pois/{pid}")
        mongo.admin_users.delete_one({"_id": reg["user_id"]})


def test_owner_registration_reject(admin, anon, mongo):
    body, _ = _register(anon)
    reg = mongo.poi_owner_registrations.find_one({"user_id": mongo.admin_users.find_one({"username": body["username"]})["_id"]})
    assert admin.post(f"{A}/registrations/{reg['_id']}/reject", json={"admin_note": "Thiếu giấy tờ"}).status_code == 200
    u = mongo.admin_users.find_one({"_id": reg["user_id"]})
    assert u["is_poi_owner_verified"] is False
    mongo.admin_users.delete_one({"_id": reg["user_id"]})


# ---------- AI advisor ----------
def test_ai_advisor_quota_and_errors(admin, make_user, anon):
    plain = make_user("user")
    assert plain.get("/api/v1/ai/usage").status_code == 403
    assert anon.get("/api/v1/ai/usage").status_code == 401
    u = admin.get("/api/v1/ai/usage").json()
    assert u["limit"] is None  # admin không giới hạn
    owner = make_user("poi_owner")
    assert owner.get("/api/v1/ai/usage").json() == {"limit": 10, "used": 0, "remaining": 10}
    assert owner.post("/api/v1/ai/enhance-description", json={"name": "", "description": "x"}).status_code == 422


# ---------- analytics / observability ----------
def test_analytics_consent_gate(admin, anon):
    dev = uid("dev") + "0000"
    ev = {"device_id": dev, "event": "narration_played", "poi_id": "poi-oc-oanh", "lang": "en"}
    assert anon.post("/api/v1/analytics/collect", json={**ev, "consent": False}).status_code == 403
    assert anon.post("/api/v1/analytics/collect", json={**ev, "consent": True, "event": "hack"}).status_code == 422
    assert anon.post("/api/v1/analytics/collect", json={**ev, "consent": True, "device_id": "bad id!"}).status_code == 422
    assert anon.post("/api/v1/analytics/collect", json={**ev, "consent": True}).status_code == 202
    s = admin.get("/api/v1/analytics/summary").json()
    assert s["tracked_online_users"] >= 1 and s["events"]["narration_played"] >= 1
    assert s["redis"] is True
    assert anon.get("/api/v1/analytics/summary").status_code == 401


def test_runtime_observability_separate_lane(admin, anon, mongo):
    before = mongo.analytics_events.count_documents({})
    assert anon.post("/api/v1/runtime/location", json={"lat": 10.7611, "lng": 106.7041}).status_code == 202
    assert anon.post("/api/v1/runtime/location", json={"lat": 999, "lng": 0}).status_code == 422
    assert mongo.analytics_events.count_documents({}) == before  # không trộn vào analytics
    w = admin.get(f"{A}/observability").json()
    assert w["total"] >= 1 and w["cells"][0]["count"] >= 1
    assert anon.get(f"{A}/observability").status_code == 401


# ---------- ui bundles / maps / audio ----------
def test_ui_bundles(anon):
    for loc in ("en", "vi", "zh", "ja", "ko"):
        b = anon.get(f"/api/v1/ui-bundles/{loc}").json()
        assert b["status"] == "ready" and b["strings"]["app.title"]
    vi = anon.get("/api/v1/ui-bundles/vi").json()
    en = anon.get("/api/v1/ui-bundles/en").json()
    assert set(vi["strings"]) == set(en["strings"]) and vi["strings"]["poi.listen"] != en["strings"]["poi.listen"]
    p = anon.get("/api/v1/ui-bundles/fr").json()  # long-tail → EN fallback + pending + source_hash
    assert p["source_hash"] == en["source_hash"] and p["status"] in ("pending", "ready")
    if p["status"] == "pending":
        assert p["strings"] == en["strings"]
    else:  # đã dịch xong dưới nền ở lần chạy trước
        assert set(p["strings"]) == set(en["strings"]) and p["strings"]["lang.label"] != "Language"
    assert anon.get("/api/v1/ui-bundles/../etc").status_code in (400, 404)
    assert anon.get("/api/v1/ui-bundles/x").status_code == 400


def test_audio_tts(anon):
    langs = anon.get("/api/v1/audio/languages").json()["languages"]
    assert {l["code"] for l in langs} == {"vi", "en", "zh", "ja", "ko"}
    r = anon.post("/api/v1/audio/tts", json={"text": "Xin chào Quận Bốn", "lang": "vi"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and len(r.content) > 1000
    assert r.headers["x-static-url"].startswith("/static/audio/")
    assert anon.post("/api/v1/audio/tts", json={"text": "Xin chào Quận Bốn", "lang": "vi"}).headers["x-cache"] == "HIT"
    assert anon.post("/api/v1/audio/tts", json={"text": "x", "lang": "xx"}).status_code == 400
    assert anon.post("/api/v1/audio/tts", json={"text": "", "lang": "vi"}).status_code == 422


def test_on_demand_errors_and_rate_limit(anon):
    assert anon.post("/api/v1/localizations/on-demand", json={"poi_id": "x", "lang": "xx"}).status_code == 400
    assert anon.post("/api/v1/localizations/on-demand", json={"poi_id": "ghost", "lang": "en"}).status_code == 404
    codes = [anon.post("/api/v1/localizations/on-demand", json={"poi_id": "ghost", "lang": "en"}).status_code for _ in range(32)]
    assert 429 in codes
    r = anon.post("/api/v1/localizations/on-demand", json={"poi_id": "ghost", "lang": "en"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    import redis
    rc = redis.Redis.from_url("redis://redis:6379/0")
    for k in rc.scan_iter("rl:ondemand:*"):
        rc.delete(k)  # trả lại hạn mức cho các lần thử sau


# ---------- audio task control / SSE ----------
def test_audio_task_pause_cancel_and_sse(admin, anon):
    pid = "poi-che"
    t = admin.post(f"{A}/pois/{pid}/regenerate-audio").json()
    assert t["status"] in ("queued", "running")
    tid = t["id"]
    assert admin.post(f"{A}/audio-tasks/{tid}/explode").status_code == 400
    assert admin.post(f"{A}/audio-tasks/nope/cancel").status_code == 404
    admin.post(f"{A}/audio-tasks/{tid}/pause")
    admin.post(f"{A}/audio-tasks/{tid}/resume")
    admin.post(f"{A}/audio-tasks/{tid}/cancel")
    lst = lambda: next(x for x in admin.get(f"{A}/audio-tasks").json()["items"] if x["id"] == tid)
    assert wait_for(lambda: lst()["status"] in ("cancelled", "completed", "failed") and lst())["status"] in ("cancelled", "completed", "failed")
    with admin.stream("GET", f"{A}/audio-tasks-stream") as s:
        assert s.headers["content-type"].startswith("text/event-stream")
        line = next(l for l in s.iter_lines() if l.startswith("data:"))
        assert isinstance(json.loads(line[5:]), list)
    # khôi phục audio cho poi-che để không ảnh hưởng test khác
    admin.post(f"{A}/pois/{pid}/regenerate-audio")
    assert anon.get("/health").status_code == 200


def test_audit_log_records_actions(admin):
    items = admin.get(f"{A}/audit-logs?limit=50").json()["items"]
    actions = {i["action"] for i in items}
    assert {"login", "poi.create"} & actions
    assert all("password_hash" not in json.dumps(i) and "Passw0rd" not in json.dumps(i) for i in items)
