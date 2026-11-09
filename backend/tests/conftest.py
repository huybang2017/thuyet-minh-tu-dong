import os
import time
import uuid

import httpx
import pymysql
from pymysql.cursors import DictCursor
import pytest

BASE = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
MYSQL = dict(host=os.environ.get("MYSQL_HOST", "mysql"), port=int(os.environ.get("MYSQL_PORT", "3306")),
             user=os.environ.get("MYSQL_USER", "root"), password=os.environ.get("MYSQL_PASSWORD", "thuyetminh"),
             database=os.environ.get("MYSQL_DB", "thuyetminh"), charset="utf8mb4", autocommit=True, cursorclass=DictCursor)


class Sql:
    """Truy vấn đồng bộ (chỉ cho test) để đối chiếu dữ liệu trong MySQL."""

    def __init__(self):
        self.conn = pymysql.connect(**MYSQL)

    def all(self, sql, args=()):
        with self.conn.cursor() as cur:
            cur.execute(sql, args)
            return cur.fetchall()

    def one(self, sql, args=()):
        rows = self.all(sql, args)
        return rows[0] if rows else None

    def scalar(self, sql, args=()):
        r = self.one(sql, args)
        return next(iter(r.values())) if r else None

    def exec(self, sql, args=()):
        with self.conn.cursor() as cur:
            return cur.execute(sql, args)

    def close(self):
        self.conn.close()
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
def sql():
    c = Sql()
    yield c
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
def _cleanup_test_accounts(sql):
    """Dọn tài khoản/đơn đăng ký do test tạo (username dạng prefix + 8 hex)."""
    yield
    ids = [u["id"] for u in sql.all("SELECT id FROM admin_users WHERE username REGEXP %s", [r"^(own|u|usr|rl|sa|x)[0-9a-f]{8}$"])]
    for i in ids:
        sql.exec("DELETE FROM owner_notifications WHERE owner_id=%s", [i])
        sql.exec("DELETE FROM admin_users WHERE id=%s", [i])  # cascade xoá đơn đăng ký
