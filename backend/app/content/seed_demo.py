"""Nạp dữ liệu demo (idempotent): thêm quán còn thiếu + thực đơn + khu vực, rồi tạo giọng đọc 5 ngôn ngữ theo từng nhóm nhỏ.

Chạy trong container backend:  python -m app.content.seed_demo
Chạy lại an toàn: quán/món đã có được bỏ qua; quán chưa hiển thị (lần trước lỗi/bị ngắt) được xử lý lại.

Dịch vụ dịch miễn phí giới hạn tốc độ, nên không dịch cả trăm quán cùng lúc: xử lý BATCH quán mỗi lượt,
nghỉ giữa các lượt, và thử lại các quán lỗi tối đa ROUNDS vòng.
"""
import asyncio

from ..admin.service import now
from ..audio import task_manager
from ..db import close_db, connect_db, get_db
from . import ops
from .demo_data import DEMO_MENUS, DEMO_POIS
from .demo_data_hcm import DEMO_MENUS_HCM, DEMO_POIS_HCM
from .seed import _RAW

CORE_AREA = "Ven sông Sài Gòn"
ALL_POIS = [{**p, "area": p.get("area", CORE_AREA)} for p in DEMO_POIS] + DEMO_POIS_HCM
ALL_MENUS = {**DEMO_MENUS, **DEMO_MENUS_HCM}
BATCH = 6          # số quán xử lý đồng thời
ROUNDS = 4         # số vòng thử lại cho quán lỗi
COOLDOWN_S = 20    # nghỉ giữa các vòng để dịch vụ dịch hạ giới hạn


async def assign_core_area() -> int:
    """Gán khu vực cho 8 quán gốc + 12 quán demo đầu nếu chưa có (DB tạo trước khi có trường area)."""
    db = get_db()
    names = [r[0] for r in _RAW] + [p["name"] for p in DEMO_POIS]
    marks = ",".join(["%s"] * len(names))
    return await db.execute(f"UPDATE poi SET area=%s WHERE name IN ({marks}) AND area IS NULL", [CORE_AREA, *names])


async def seed_pois() -> int:
    """Thêm quán còn thiếu. Việc tạo giọng đọc được hoãn lại để chạy theo nhóm (xem process_pending)."""
    db = get_db()
    added = 0
    real_enqueue = task_manager.enqueue
    task_manager.enqueue = lambda *a, **k: None  # create_poi gọi enqueue; tạm vô hiệu để không dịch ồ ạt
    try:
        for poi in ALL_POIS:
            existing = await db.fetchone("SELECT id, area FROM poi WHERE name=%s LIMIT 1", [poi["name"]])
            if existing:
                if existing["area"] is None:
                    await db.update("poi", existing["id"], {"area": poi["area"]})
                continue
            await ops.create_poi(dict(poi))
            added += 1
    finally:
        task_manager.enqueue = real_enqueue
    return added


async def pending_ids() -> list[int]:
    """Quán demo chưa hiển thị (mới tạo, lỗi, hoặc bị ngắt giữa chừng)."""
    names = list({p["name"] for p in ALL_POIS})
    marks = ",".join(["%s"] * len(names))
    rows = await get_db().fetchall(f"SELECT id FROM poi WHERE name IN ({marks}) AND is_active=0", names)
    return [r["id"] for r in rows]


async def process_pending() -> None:
    db = get_db()
    for rnd in range(1, ROUNDS + 1):
        todo = await pending_ids()
        if not todo:
            return
        print(f"Vòng {rnd}/{ROUNDS}: {len(todo)} quán cần tạo giọng đọc", flush=True)
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            for pid in chunk:
                await db.update("poi", pid, {"audio_status": "processing", "activation_requested": True})
                task_manager.enqueue(pid)
            while task_manager.has_active():
                await asyncio.sleep(5)
            active = await db.scalar("SELECT COUNT(*) FROM poi WHERE is_active=1")
            print(f"  nhóm {i // BATCH + 1}/{-(-len(todo) // BATCH)} xong — hiện có {active} quán hiển thị", flush=True)
        if rnd < ROUNDS and await pending_ids():
            await asyncio.sleep(COOLDOWN_S)


async def seed_menus() -> int:
    db = get_db()
    added = 0
    for poi_name, items in ALL_MENUS.items():
        poi = await db.fetchone("SELECT id FROM poi WHERE name=%s LIMIT 1", [poi_name])
        if not poi:
            continue
        for name, price in items:
            if await db.fetchone("SELECT id FROM menu_items WHERE poi_id=%s AND name=%s LIMIT 1", [poi["id"], name]):
                continue
            await db.insert("menu_items", {"poi_id": poi["id"], "name": name,
                                           "price": price, "created_at": now()})
            added += 1
    return added


async def main() -> None:
    await connect_db()
    try:
        fixed = await assign_core_area()
        pois = await seed_pois()
        menus = await seed_menus()
        print(f"Đã thêm {pois} quán, {menus} món (gán khu vực cho {fixed} quán cũ).", flush=True)
        await process_pending()
        db = get_db()
        total = await db.scalar("SELECT COUNT(*) FROM poi")
        active = await db.scalar("SELECT COUNT(*) FROM poi WHERE is_active=1")
        left = await pending_ids()
        print(f"Xong. Tổng {total} quán, {active} quán đang hiển thị. Quán demo chưa hiển thị: {len(left)}")
        if left:
            print("Chạy lại lệnh này để thử lại các quán còn lại (thường do dịch vụ dịch miễn phí đang giới hạn).")
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
