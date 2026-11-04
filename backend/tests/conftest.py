import os
import time
import uuid

import httpx
import pymongo
import pytest

BASE = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
MONGO = os.environ.get("MONGO_URL", "mongodb://mongo:27017")
ADMIN = ("admin", os.environ.get("SUPERADMIN_PASSWORD") or "admin12345")


def uid(prefix="t") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def wait_for(fn, timeout=120, interval=1.5):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        last = fn()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"timeout, last={last!r}")


@pytest.fixture(scope="session")
def mongo():
    c = pymongo.MongoClient(MONGO)
    yield c["thuyetminh"]
    c.close()


def make_client() -> httpx.Client:
    return httpx.Client(base_url=BASE, timeout=60)


@pytest.fixture(scope="session")
def admin():
    c = make_client()
    r = c.post("/api/v1/admin/auth/login", json={"username": ADMIN[0], "password": ADMIN[1]})
    assert r.status_code == 200, r.text
    yield c
    c.close()


@pytest.fixture(scope="session")
def anon():
    c = make_client()
    yield c
    c.close()


@pytest.fixture()
def make_user(admin):
    """Tạo user với role chỉ định, trả về client đã đăng nhập."""
    created = []

    def _make(role: str):
        name, pw = uid("u"), "Passw0rd!x"
        r = admin.post("/api/v1/admin/users", json={"username": name, "password": pw, "role": role})
        assert r.status_code == 201, r.text
        created.append(r.json()["id"])
        c = make_client()
        assert c.post("/api/v1/admin/auth/login", json={"username": name, "password": pw}).status_code == 200
        return c

    yield _make
    for i in created:
        admin.delete(f"/api/v1/admin/users/{i}")


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_accounts(mongo):
    """Dọn tài khoản/đơn đăng ký do test tạo (username dạng prefix + 8 hex)."""
    yield
    pattern = {"$regex": r"^(own|u|usr|rl|sa|x)[0-9a-f]{8}$"}
    ids = [u["_id"] for u in mongo.admin_users.find({"username": pattern}, {"_id": 1})]
    mongo.poi_owner_registrations.delete_many({"user_id": {"$in": ids}})
    mongo.owner_notifications.delete_many({"owner_id": {"$in": ids}})
    mongo.admin_users.delete_many({"_id": {"$in": ids}})
