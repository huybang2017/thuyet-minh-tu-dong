"""Nâng cấp DB cũ (id chuỗi VARCHAR) lên schema mới (id số BIGINT tự tăng), GIỮ NGUYÊN dữ liệu.

Cách làm: đổi tên các bảng có id chuỗi thành `<bảng>__old`, tạo bảng mới theo SCHEMA, rồi copy dữ liệu sang
với id số mới (bảng ánh xạ id cũ → mới cho poi và admin_users, khoá ngoại được ánh xạ theo). Nếu có lỗi giữa chừng
thì khôi phục lại bảng cũ. Chỉ chạy một lần: chạy lại khi DB đã là id số sẽ không làm gì.
"""
import logging

log = logging.getLogger("migrate_int_ids")

# thứ tự không quan trọng (FOREIGN_KEY_CHECKS=0); audio_tasks là dữ liệu tạm nên không copy
TABLES = ["poi", "admin_users", "poi_localizations", "removed_pois", "menu_items", "poi_owner_registrations",
          "poi_submissions", "owner_notifications", "audit_logs", "audio_tasks", "analytics_events", "ai_usage_limits"]
FKS = [("poi_localizations", "fk_loc_poi", "FOREIGN KEY (poi_id) REFERENCES poi(id) ON DELETE CASCADE"),
       ("menu_items", "fk_menu_poi", "FOREIGN KEY (poi_id) REFERENCES poi(id) ON DELETE CASCADE"),
       ("poi_owner_registrations", "fk_reg_user", "FOREIGN KEY (user_id) REFERENCES admin_users(id) ON DELETE CASCADE")]

MAPS = [
    "DROP TABLE IF EXISTS _map_user",
    "DROP TABLE IF EXISTS _map_poi",
    "CREATE TABLE _map_user (old_id VARCHAR(80) NOT NULL PRIMARY KEY, new_id BIGINT NOT NULL AUTO_INCREMENT, UNIQUE KEY (new_id))",
    "CREATE TABLE _map_poi (old_id VARCHAR(80) NOT NULL PRIMARY KEY, new_id BIGINT NOT NULL AUTO_INCREMENT, UNIQUE KEY (new_id))",
    "INSERT INTO _map_user (old_id) SELECT id FROM admin_users ORDER BY created_at, id",
    "INSERT INTO _map_poi (old_id) SELECT id FROM poi ORDER BY id",
]

COPY = [
    # (tên bảng, câu INSERT ... SELECT) — bảng mới đã được tạo theo SCHEMA
    ("admin_users",
     "INSERT INTO admin_users (id, username, email, password_hash, role, display_name, is_active, is_verified, "
     "is_poi_owner_verified, created_at, deleted_at) "
     "SELECT m.new_id, o.username, o.email, o.password_hash, o.role, o.display_name, o.is_active, o.is_verified, "
     "o.is_poi_owner_verified, o.created_at, o.deleted_at "
     "FROM admin_users__old o JOIN _map_user m ON m.old_id=o.id"),
    ("poi",
     "INSERT INTO poi (id, name, description, lat, lng, trigger_radius, audio_priority, images, address, area, owner_id, "
     "is_active, activation_requested, audio_status, updated_at, deleted_at) "
     "SELECT m.new_id, o.name, o.description, o.lat, o.lng, o.trigger_radius, o.audio_priority, o.images, o.address, o.area, "
     "u.new_id, o.is_active, o.activation_requested, o.audio_status, o.updated_at, o.deleted_at "
     "FROM poi__old o JOIN _map_poi m ON m.old_id=o.id LEFT JOIN _map_user u ON u.old_id=o.owner_id"),
    ("poi_localizations",
     "INSERT INTO poi_localizations (id, poi_id, lang, name, description, audio_url, source_hash, updated_at) "
     "SELECT o.id, m.new_id, o.lang, o.name, o.description, o.audio_url, o.source_hash, o.updated_at "
     "FROM poi_localizations__old o JOIN _map_poi m ON m.old_id=o.poi_id"),
    ("removed_pois",
     "INSERT INTO removed_pois (id, removed_at) SELECT m.new_id, o.removed_at "
     "FROM removed_pois__old o JOIN _map_poi m ON m.old_id=o.id"),
    ("menu_items",
     "INSERT INTO menu_items (poi_id, name, price, description, created_at, deleted_at) "
     "SELECT m.new_id, o.name, o.price, o.description, o.created_at, o.deleted_at "
     "FROM menu_items__old o JOIN _map_poi m ON m.old_id=o.poi_id ORDER BY o.created_at, o.id"),
    ("poi_owner_registrations",
     "INSERT INTO poi_owner_registrations (user_id, shop_name, phone, cccd_encrypted, status, admin_note, reviewed_by, "
     "reviewed_at, pii_redacted_at, created_at) "
     "SELECT u.new_id, o.shop_name, o.phone, o.cccd_encrypted, o.status, o.admin_note, r.new_id, o.reviewed_at, "
     "o.pii_redacted_at, o.created_at "
     "FROM poi_owner_registrations__old o JOIN _map_user u ON u.old_id=o.user_id "
     "LEFT JOIN _map_user r ON r.old_id=o.reviewed_by ORDER BY o.created_at, o.id"),
    ("poi_submissions",
     "INSERT INTO poi_submissions (owner_id, type, poi_id, data, status, admin_note, reviewed_by, reviewed_at, created_at) "
     "SELECT u.new_id, o.type, p.new_id, o.data, o.status, o.admin_note, r.new_id, o.reviewed_at, o.created_at "
     "FROM poi_submissions__old o JOIN _map_user u ON u.old_id=o.owner_id "
     "LEFT JOIN _map_poi p ON p.old_id=o.poi_id LEFT JOIN _map_user r ON r.old_id=o.reviewed_by "
     "ORDER BY o.created_at, o.id"),
    ("owner_notifications",
     "INSERT INTO owner_notifications (owner_id, title, body, `read`, created_at) "
     "SELECT u.new_id, o.title, o.body, o.`read`, o.created_at "
     "FROM owner_notifications__old o JOIN _map_user u ON u.old_id=o.owner_id ORDER BY o.created_at, o.id"),
    ("audit_logs",
     "INSERT INTO audit_logs (id, action, resource, detail, user_id, username, `timestamp`) "
     "SELECT o.id, o.action, o.resource, o.detail, u.new_id, o.username, o.`timestamp` "
     "FROM audit_logs__old o LEFT JOIN _map_user u ON u.old_id=o.user_id"),
    ("analytics_events",
     "INSERT INTO analytics_events (id, device_id, session_id, event, poi_id, lang, ts) "
     "SELECT o.id, o.device_id, o.session_id, o.event, p.new_id, o.lang, o.ts "
     "FROM analytics_events__old o LEFT JOIN _map_poi p ON p.old_id=o.poi_id"),
    ("ai_usage_limits",
     "INSERT INTO ai_usage_limits (id, user_id, `date`, `count`) "
     "SELECT o.id, u.new_id, o.`date`, o.`count` FROM ai_usage_limits__old o JOIN _map_user u ON u.old_id=o.user_id"),
]


async def needs_migration(db, schema_name: str) -> bool:
    t = await db.scalar("SELECT DATA_TYPE FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA=%s AND TABLE_NAME='poi' AND COLUMN_NAME='id'", [schema_name])
    return t is not None and str(t).lower() != "bigint"


async def migrate(db, schema: list[str]) -> dict[str, int]:
    """Chạy migration trên 1 kết nối duy nhất (FOREIGN_KEY_CHECKS là cài đặt theo phiên). Trả về số dòng đã copy."""
    copied: dict[str, int] = {}
    async with db.pool.acquire() as conn, conn.cursor() as cur:
        async def run(sql: str) -> int:
            return await cur.execute(sql)

        await run("SET FOREIGN_KEY_CHECKS=0")
        renamed: list[str] = []
        dropped_fks: list[tuple] = []
        try:
            for stmt in MAPS:
                await run(stmt)
            for table, name, ddl in FKS:
                await run(f"ALTER TABLE {table} DROP FOREIGN KEY {name}")
                dropped_fks.append((table, name, ddl))
            for t in TABLES:
                await run(f"RENAME TABLE {t} TO {t}__old")
                renamed.append(t)
            for stmt in schema:
                await run(stmt)
            for table, sql in COPY:
                copied[table] = await run(sql)
            # kiểm tra: không được mất người dùng / quán nào
            for table in ("admin_users", "poi"):
                await run(f"SELECT COUNT(*) FROM {table}__old")
                old_n = (await cur.fetchone())[0]
                if old_n != copied[table]:
                    raise RuntimeError(f"{table}: {old_n} dòng cũ nhưng chỉ copy được {copied[table]}")
            for t in TABLES:
                await run(f"DROP TABLE {t}__old")
            await run("DROP TABLE _map_user")
            await run("DROP TABLE _map_poi")
        except Exception:
            log.exception("Migration id số thất bại — khôi phục bảng cũ")
            for t in TABLES:  # bỏ bảng mới (nếu đã tạo), trả lại bảng cũ
                if t in renamed:
                    await run(f"DROP TABLE IF EXISTS {t}")
                    await run(f"RENAME TABLE {t}__old TO {t}")
            for table, name, ddl in dropped_fks:
                try:
                    await run(f"ALTER TABLE {table} ADD CONSTRAINT {name} {ddl}")
                except Exception:
                    log.exception("Không thêm lại được FK %s", name)
            await run("DROP TABLE IF EXISTS _map_user")
            await run("DROP TABLE IF EXISTS _map_poi")
            raise
        finally:
            await run("SET FOREIGN_KEY_CHECKS=1")
    return copied
