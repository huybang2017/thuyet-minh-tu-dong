"""Tài khoản + dữ liệu mẫu (idempotent). Chạy trong container backend:  python -m app.content.seed_accounts

Mật khẩu mặc định chỉ để DEV/DEMO — đổi hoặc xoá trước khi triển khai thật.
"""
import asyncio
import random
from datetime import timedelta

from ..admin.service import now
from ..db import close_db, connect_db, get_db
from ..security import hash_password

DEFAULT_PASSWORD = "Demo@12345"

# (username, role, display_name, email, is_poi_owner_verified)
ACCOUNTS = [
    ("admin2", "admin", "Quản trị viên 2", "admin2@demo.local", False),
    ("owner1", "poi_owner", "Chủ quán Nguyễn Văn A", "owner1@demo.local", True),
    ("owner2", "poi_owner", "Chủ quán Trần Thị B", "owner2@demo.local", True),
    ("user1", "user", "Du khách Lê C", "user1@demo.local", False),
    ("user2", "user", "Du khách Phạm D", "user2@demo.local", False),
]
PENDING_OWNER = ("owner_pending", "poi_owner", "Chủ quán chờ duyệt", "pending@demo.local", False)
OWNER_POIS = {"owner1": 4, "owner2": 3}  # số quán gán cho mỗi owner (lấy từ quán chưa có chủ)
LANGS = ["vi", "en", "zh", "ja", "ko"]


async def _ensure_user(u: tuple) -> int:
    db = get_db()
    username, role, name, email, verified = u
    row = await db.fetchone("SELECT id FROM admin_users WHERE username=%s", [username])
    if row:
        return row["id"]
    return await db.insert("admin_users", {
        "username": username, "email": email, "password_hash": hash_password(DEFAULT_PASSWORD),
        "role": role, "display_name": name, "is_active": True, "is_verified": True,
        "is_poi_owner_verified": verified, "created_at": now()})


async def seed_users() -> dict[str, int]:
    ids = {u[0]: await _ensure_user(u) for u in ACCOUNTS}
    db = get_db()
    # owner đã duyệt → có hồ sơ đăng ký trạng thái approved
    for u in ACCOUNTS:
        if u[4] and not await db.fetchone("SELECT id FROM poi_owner_registrations WHERE user_id=%s", [ids[u[0]]]):
            await db.insert("poi_owner_registrations", {
                "user_id": ids[u[0]], "shop_name": f"Quán của {u[2]}", "phone": "0901234567",
                "status": "approved", "reviewed_at": now(), "created_at": now()})
    # 1 owner chờ duyệt để demo màn hình duyệt
    pid = await _ensure_user(PENDING_OWNER)
    if not await db.fetchone("SELECT id FROM poi_owner_registrations WHERE user_id=%s", [pid]):
        await db.insert("poi_owner_registrations", {
            "user_id": pid, "shop_name": "Bún riêu Cô Ba", "phone": "0987654321",
            "status": "pending", "created_at": now()})
    ids[PENDING_OWNER[0]] = pid
    return ids


async def assign_owner_pois(ids: dict[str, int]) -> int:
    db = get_db()
    n = 0
    for owner, count in OWNER_POIS.items():
        if await db.scalar("SELECT COUNT(*) FROM poi WHERE owner_id=%s", [ids[owner]]) >= count:
            continue
        rows = await db.fetchall("SELECT id FROM poi WHERE owner_id IS NULL ORDER BY id LIMIT %s", [count])
        for r in rows:
            n += await db.update("poi", r["id"], {"owner_id": ids[owner]})
        await db.insert("owner_notifications", {
            "owner_id": ids[owner], "title": "Chào mừng chủ quán",
            "body": "Tài khoản của bạn đã được duyệt. Bạn có thể quản lý quán và thực đơn.", "read": False, "created_at": now()})
    return n


async def seed_analytics(days: int = 7, per_day: int = 40) -> int:
    """Sự kiện mẫu để dashboard có số liệu (chỉ nạp một lần)."""
    db = get_db()
    if await db.scalar("SELECT COUNT(*) FROM analytics_devices WHERE device_id LIKE %s", ["demo-device-%"]) > 0:
        return 0
    poi_ids = [r["id"] for r in await db.fetchall("SELECT id FROM poi WHERE is_active=1")] or \
              [r["id"] for r in await db.fetchall("SELECT id FROM poi LIMIT 10")]
    rnd = random.Random(42)
    devices = [f"demo-device-{i:03d}" for i in range(25)]
    t0 = now()
    for d in devices:
        await db.upsert("analytics_devices", {"device_id": d, "first_seen": t0 - timedelta(days=days), "last_seen": t0}, ["last_seen"])
    rows = []
    for day in range(days):
        for _ in range(per_day):
            dev, lang = rnd.choice(devices), rnd.choice(LANGS)
            ts = t0 - timedelta(days=day, minutes=rnd.randint(0, 1000))
            ev = rnd.choices(["app_open", "language_changed", "poi_viewed", "narration_played"], [2, 1, 4, 5])[0]
            rows.append({"device_id": dev, "session_id": f"s{day}-{dev[-3:]}", "event": ev,
                         "poi_id": rnd.choice(poi_ids) if ev in ("poi_viewed", "narration_played") and poi_ids else None,
                         "lang": lang, "ts": ts})
    await db.insert_many("analytics_events", rows)
    return len(rows)


async def main() -> None:
    await connect_db()
    try:
        ids = await seed_users()
        assigned = await assign_owner_pois(ids)
        events = await seed_analytics()
        print(f"Tài khoản (mật khẩu chung: {DEFAULT_PASSWORD}):")
        for u in [*ACCOUNTS, PENDING_OWNER]:
            print(f"  {u[0]:15} {u[1]}")
        print("  admin           super_admin (mật khẩu theo SUPERADMIN_PASSWORD trong .env)")
        print(f"Gán {assigned} quán cho owner; nạp {events} sự kiện analytics mẫu.")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
