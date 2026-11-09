"""Tầng truy cập MySQL (aiomysql): connection pool, helper truy vấn và schema quan hệ."""
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import aiomysql
from aiomysql import DictCursor
from pymysql.constants import CLIENT

from .config import settings

# cột JSON được tự (de)serialize; cột BOOL trả về True/False thay vì 0/1.
# DATETIME lưu UTC và trả về naive UTC.
JSON_COLS = {"images", "permissions", "langs", "failed_langs", "data", "strings"}
BOOL_COLS = {"is_active", "activation_requested", "is_verified", "is_poi_owner_verified", "is_default", "read"}

# bảng xoá mềm: DELETE chỉ đặt deleted_at; mọi truy vấn đọc phải lọc `deleted_at IS NULL`
SOFT_DELETE_TABLES = ("roles", "admin_users", "poi", "menu_items")

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS roles (
        name VARCHAR(32) NOT NULL PRIMARY KEY,
        priority INT NOT NULL DEFAULT 50,
        permissions JSON NOT NULL,
        is_default TINYINT(1) NOT NULL DEFAULT 0,
        deleted_at DATETIME(6) NULL
    )""",
    """CREATE TABLE IF NOT EXISTS admin_users (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(32) NOT NULL,
        email VARCHAR(255) NULL,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(32) NOT NULL,
        display_name VARCHAR(120) NULL,
        is_active TINYINT(1) NOT NULL DEFAULT 1,
        is_verified TINYINT(1) NOT NULL DEFAULT 0,
        is_poi_owner_verified TINYINT(1) NOT NULL DEFAULT 0,
        created_at DATETIME(6) NOT NULL,
        deleted_at DATETIME(6) NULL,
        UNIQUE KEY uq_admin_users_username (username),
        UNIQUE KEY uq_admin_users_email (email),
        KEY ix_admin_users_role (role)
    )""",
    """CREATE TABLE IF NOT EXISTS poi (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(120) NOT NULL,
        description TEXT NOT NULL,
        lat DOUBLE NOT NULL,
        lng DOUBLE NOT NULL,
        trigger_radius INT NOT NULL DEFAULT 30,
        audio_priority INT NOT NULL DEFAULT 3,
        images JSON NOT NULL,
        address VARCHAR(255) NULL,
        area VARCHAR(60) NULL,
        owner_id BIGINT NULL,
        is_active TINYINT(1) NOT NULL DEFAULT 0,
        activation_requested TINYINT(1) NOT NULL DEFAULT 0,
        audio_status VARCHAR(16) NOT NULL DEFAULT 'none',
        updated_at DATETIME(6) NOT NULL,
        deleted_at DATETIME(6) NULL,
        KEY ix_poi_name (name),
        KEY ix_poi_owner (owner_id),
        KEY ix_poi_active (is_active),
        KEY ix_poi_updated (updated_at),
        KEY ix_poi_latlng (lat, lng)
    )""",
    """CREATE TABLE IF NOT EXISTS poi_localizations (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        poi_id BIGINT NOT NULL,
        lang VARCHAR(8) NOT NULL,
        name VARCHAR(255) NOT NULL,
        description TEXT NOT NULL,
        audio_url VARCHAR(255) NULL,
        source_hash CHAR(32) NULL,
        updated_at DATETIME(6) NOT NULL,
        UNIQUE KEY uq_loc_poi_lang (poi_id, lang),
        KEY ix_loc_lang_updated (lang, updated_at),
        CONSTRAINT fk_loc_poi FOREIGN KEY (poi_id) REFERENCES poi(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS removed_pois (
        id BIGINT NOT NULL PRIMARY KEY,
        removed_at DATETIME(6) NOT NULL,
        KEY ix_removed_at (removed_at)
    )""",
    """CREATE TABLE IF NOT EXISTS menu_items (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        poi_id BIGINT NOT NULL,
        name VARCHAR(120) NOT NULL,
        price DOUBLE NOT NULL DEFAULT 0,
        description TEXT NULL,
        created_at DATETIME(6) NOT NULL,
        deleted_at DATETIME(6) NULL,
        KEY ix_menu_poi (poi_id),
        CONSTRAINT fk_menu_poi FOREIGN KEY (poi_id) REFERENCES poi(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS poi_owner_registrations (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT NOT NULL,
        shop_name VARCHAR(120) NOT NULL,
        phone VARCHAR(20) NOT NULL,
        cccd_encrypted TEXT NULL,
        status VARCHAR(16) NOT NULL DEFAULT 'pending',
        admin_note VARCHAR(500) NULL,
        reviewed_by BIGINT NULL,
        reviewed_at DATETIME(6) NULL,
        pii_redacted_at DATETIME(6) NULL,
        created_at DATETIME(6) NOT NULL,
        KEY ix_reg_user (user_id),
        KEY ix_reg_status (status, created_at),
        CONSTRAINT fk_reg_user FOREIGN KEY (user_id) REFERENCES admin_users(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS poi_submissions (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        owner_id BIGINT NOT NULL,
        type VARCHAR(16) NOT NULL,
        poi_id BIGINT NULL,
        data JSON NOT NULL,
        status VARCHAR(16) NOT NULL DEFAULT 'pending',
        admin_note VARCHAR(500) NULL,
        reviewed_by BIGINT NULL,
        reviewed_at DATETIME(6) NULL,
        created_at DATETIME(6) NOT NULL,
        KEY ix_sub_owner (owner_id, created_at),
        KEY ix_sub_status (status, created_at)
    )""",
    """CREATE TABLE IF NOT EXISTS owner_notifications (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        owner_id BIGINT NOT NULL,
        title VARCHAR(255) NOT NULL,
        body TEXT NOT NULL,
        `read` TINYINT(1) NOT NULL DEFAULT 0,
        created_at DATETIME(6) NOT NULL,
        KEY ix_notif_owner (owner_id, created_at)
    )""",
    """CREATE TABLE IF NOT EXISTS audit_logs (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        action VARCHAR(64) NOT NULL,
        resource VARCHAR(120) NOT NULL,
        detail VARCHAR(300) NOT NULL DEFAULT '',
        user_id BIGINT NULL,
        username VARCHAR(32) NULL,
        `timestamp` DATETIME(6) NOT NULL,
        KEY ix_audit_ts (`timestamp`)
    )""",
    """CREATE TABLE IF NOT EXISTS audio_tasks (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        poi_id BIGINT NOT NULL,
        langs JSON NOT NULL,
        status VARCHAR(16) NOT NULL,
        total INT NOT NULL DEFAULT 0,
        done INT NOT NULL DEFAULT 0,
        failed_langs JSON NOT NULL,
        error VARCHAR(255) NULL,
        created_at DATETIME(6) NOT NULL,
        updated_at DATETIME(6) NOT NULL,
        KEY ix_task_updated (updated_at)
    )""",
    """CREATE TABLE IF NOT EXISTS translation_cache (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        cache_key CHAR(32) NOT NULL,
        lang VARCHAR(8) NOT NULL,
        text MEDIUMTEXT NOT NULL,
        UNIQUE KEY uq_cache_key (cache_key)
    )""",
    """CREATE TABLE IF NOT EXISTS analytics_events (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        device_id VARCHAR(64) NOT NULL,
        session_id VARCHAR(64) NULL,
        event VARCHAR(32) NOT NULL,
        poi_id BIGINT NULL,
        lang VARCHAR(8) NULL,
        ts DATETIME(6) NOT NULL,
        KEY ix_ev_ts (ts, event),
        KEY ix_ev_poi (poi_id, event)
    )""",
    """CREATE TABLE IF NOT EXISTS analytics_devices (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        device_id VARCHAR(64) NOT NULL,
        first_seen DATETIME(6) NOT NULL,
        last_seen DATETIME(6) NOT NULL,
        UNIQUE KEY uq_device_id (device_id),
        KEY ix_dev_last_seen (last_seen)
    )""",
    """CREATE TABLE IF NOT EXISTS runtime_location_hourly (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        `hour` DATETIME NOT NULL,
        cell VARCHAR(32) NOT NULL,
        lat DOUBLE NOT NULL,
        lng DOUBLE NOT NULL,
        `count` INT NOT NULL DEFAULT 0,
        UNIQUE KEY uq_loc_hour_cell (`hour`, cell)
    )""",
    """CREATE TABLE IF NOT EXISTS ai_usage_limits (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT NOT NULL,
        `date` CHAR(10) NOT NULL,
        `count` INT NOT NULL DEFAULT 0,
        UNIQUE KEY uq_ai_user_date (user_id, `date`)
    )""",
    """CREATE TABLE IF NOT EXISTS ui_translation_bundles (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        namespace VARCHAR(32) NOT NULL,
        locale VARCHAR(16) NOT NULL,
        source_hash VARCHAR(32) NOT NULL,
        status VARCHAR(16) NOT NULL,
        strings JSON NOT NULL,
        updated_at DATETIME(6) NOT NULL,
        UNIQUE KEY uq_bundle (namespace, locale, source_hash)
    )""",
]


def _to_db(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc).replace(tzinfo=None) if v.tzinfo else v
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v


def _row(r: dict | None) -> dict | None:
    if r is None:
        return None
    for k, v in list(r.items()):
        if v is None:
            continue
        if k in JSON_COLS and isinstance(v, (str, bytes)):
            r[k] = json.loads(v)
        elif k in BOOL_COLS:
            r[k] = bool(v)
    if "id" in r:
        r["_id"] = r["id"]  # tương thích với code cũ dùng d["_id"]
    return r


class Database:
    def __init__(self, pool: aiomysql.Pool):
        self.pool = pool

    async def fetchall(self, sql: str, args: tuple | list = ()) -> list[dict]:
        async with self.pool.acquire() as conn, conn.cursor(DictCursor) as cur:
            await cur.execute(sql, tuple(_to_db(a) for a in args))
            return [_row(r) for r in await cur.fetchall()]

    async def fetchone(self, sql: str, args: tuple | list = ()) -> dict | None:
        async with self.pool.acquire() as conn, conn.cursor(DictCursor) as cur:
            await cur.execute(sql, tuple(_to_db(a) for a in args))
            return _row(await cur.fetchone())

    async def scalar(self, sql: str, args: tuple | list = ()) -> Any:
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(sql, tuple(_to_db(a) for a in args))
            r = await cur.fetchone()
            return r[0] if r else None

    async def execute(self, sql: str, args: tuple | list = ()) -> int:
        """Trả về số dòng khớp (CLIENT.FOUND_ROWS) cho UPDATE, số dòng xoá cho DELETE."""
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            n = await cur.execute(sql, tuple(_to_db(a) for a in args))
            await conn.commit()
            return n

    async def insert(self, table: str, row: dict) -> int:
        """Trả về id tự sinh (AUTO_INCREMENT) của dòng vừa chèn; 0 nếu bảng không có cột tự tăng."""
        cols = ", ".join(f"`{c}`" for c in row)
        marks = ", ".join(["%s"] * len(row))
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(_to_db(v) for v in row.values()))
            await conn.commit()
            return cur.lastrowid

    async def insert_many(self, table: str, rows: list[dict]) -> None:
        if not rows:
            return
        cols = list(rows[0])
        sql = f"INSERT INTO {table} ({', '.join(f'`{c}`' for c in cols)}) VALUES ({', '.join(['%s'] * len(cols))})"
        async with self.pool.acquire() as conn, conn.cursor() as cur:
            await cur.executemany(sql, [tuple(_to_db(r[c]) for c in cols) for r in rows])
            await conn.commit()

    async def update(self, table: str, pk: Any, fields: dict, key: str = "id") -> int:
        if not fields:
            return await self.scalar(f"SELECT COUNT(*) FROM {table} WHERE `{key}`=%s", [pk])
        sets = ", ".join(f"`{c}`=%s" for c in fields)
        return await self.execute(f"UPDATE {table} SET {sets} WHERE `{key}`=%s", [*fields.values(), pk])

    async def upsert(self, table: str, row: dict, update_cols: list[str]) -> None:
        """INSERT ... ON DUPLICATE KEY UPDATE trên các cột update_cols."""
        cols = ", ".join(f"`{c}`" for c in row)
        marks = ", ".join(["%s"] * len(row))
        upd = ", ".join(f"`{c}`=VALUES(`{c}`)" for c in update_cols)
        await self.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks}) ON DUPLICATE KEY UPDATE {upd}", list(row.values()))

    async def ping(self) -> None:
        await self.scalar("SELECT 1")


_pool: aiomysql.Pool | None = None
_db: Database | None = None


def _conn_kwargs() -> dict:
    return dict(host=settings.mysql_host, port=settings.mysql_port, user=settings.mysql_user,
                password=settings.mysql_password, charset="utf8mb4", autocommit=True,  # tránh snapshot REPEATABLE READ cũ giữa các request
                client_flag=CLIENT.FOUND_ROWS)


async def connect_db(retries: int = 30) -> Database:
    global _pool, _db
    last: Exception | None = None
    for _ in range(retries):  # MySQL trong Docker khởi động chậm hơn backend
        try:
            boot = await aiomysql.connect(**_conn_kwargs())
            async with boot.cursor() as cur:
                await cur.execute(f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_db}` "
                                  "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            await boot.ensure_closed()
            break
        except Exception as e:
            last = e
            await asyncio.sleep(2)
    else:
        raise RuntimeError(f"Không kết nối được MySQL: {last}")
    _pool = await aiomysql.create_pool(db=settings.mysql_db, minsize=1, maxsize=10, init_command="SET time_zone='+00:00'",
                                       **_conn_kwargs())
    _db = Database(_pool)
    await _migrate_int_ids(_db)
    for stmt in SCHEMA:
        await _db.execute(stmt)
    await _migrate_soft_delete(_db)
    await _migrate_aux_ids(_db)
    return _db


async def _migrate_int_ids(db: Database) -> None:
    """DB cũ dùng id chuỗi → tự nâng cấp lên id số tự tăng, giữ nguyên dữ liệu (xem migrate_int_ids.py)."""
    from . import migrate_int_ids
    if await migrate_int_ids.needs_migration(db, settings.mysql_db):
        await _migrate_soft_delete(db)
        await migrate_int_ids.migrate(db, SCHEMA)


async def _col_exists(db: Database, table: str, col: str) -> bool:
    return bool(await db.scalar(
        "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s",
        [settings.mysql_db, table, col]))


async def _migrate_aux_ids(db: Database) -> None:
    """Bảng còn khoá chính chuỗi (hash cache, device id) → thêm id số tự tăng, khoá cũ thành cột UNIQUE."""
    if not await _col_exists(db, "translation_cache", "cache_key"):
        await db.execute("ALTER TABLE translation_cache DROP PRIMARY KEY, CHANGE id cache_key CHAR(32) NOT NULL, "
                         "ADD UNIQUE KEY uq_cache_key (cache_key), ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST")
    if not await _col_exists(db, "analytics_devices", "device_id"):
        await db.execute("ALTER TABLE analytics_devices DROP PRIMARY KEY, CHANGE id device_id VARCHAR(64) NOT NULL, "
                         "ADD UNIQUE KEY uq_device_id (device_id), ADD COLUMN id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST")
    await db.execute("ALTER TABLE audio_tasks MODIFY id BIGINT NOT NULL AUTO_INCREMENT")


async def _migrate_soft_delete(db: Database) -> None:
    """DB cũ (tạo trước khi có soft delete) chưa có cột deleted_at → thêm vào."""
    for table in SOFT_DELETE_TABLES:
        has = await db.scalar(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME='deleted_at'", [settings.mysql_db, table])
        if not has:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN deleted_at DATETIME(6) NULL")


def get_db() -> Database:
    assert _db is not None, "DB chưa kết nối"
    return _db


async def close_db() -> None:
    global _pool, _db
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()
    _pool = _db = None
