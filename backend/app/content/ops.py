"""Nghiệp vụ ghi POI dùng chung cho admin và duyệt submission của owner."""
from datetime import datetime, timezone

from ..audio import task_manager
from ..db import get_db

MAX_POI_IMAGES = 8
EDITABLE = {"name", "description", "lat", "lng", "trigger_radius", "audio_priority", "images", "address", "area"}


def _now():
    return datetime.now(timezone.utc)


def _clean(data: dict) -> dict:
    out = {k: v for k, v in data.items() if k in EDITABLE and v is not None}
    if "images" in out:
        out["images"] = list(out["images"])[:MAX_POI_IMAGES]
    return out


async def create_poi(data: dict, owner_id: int | None = None, activate: bool = True) -> dict:
    db = get_db()
    d = _clean(data)
    row = {
        "images": [], "trigger_radius": 30, "audio_priority": 3, **d,
        "owner_id": owner_id,
        # text lưu trước; chỉ public khi EN + audio sẵn sàng (activation gate)
        "is_active": False, "activation_requested": activate, "audio_status": "processing",
        "updated_at": _now(),
    }
    pid = await db.insert("poi", row)  # id số do MySQL tự sinh
    task_manager.enqueue(pid)
    return await db.fetchone("SELECT * FROM poi WHERE id=%s", [pid])


async def update_poi(pid: int, data: dict) -> dict | None:
    db = get_db()
    old = await db.fetchone("SELECT * FROM poi WHERE id=%s AND deleted_at IS NULL", [pid])
    if not old:
        return None
    d = _clean(data)
    upd = {**d, "updated_at": _now()}
    text_changed = ("description" in d and d["description"] != old["description"]) or \
                   ("name" in d and d["name"] != old["name"])
    if text_changed:
        # xoá audio cũ, khoá public tới khi sinh lại xong, nhớ ý định kích hoạt
        await db.execute("DELETE FROM poi_localizations WHERE poi_id=%s", [pid])
        upd.update({"audio_status": "processing", "activation_requested": bool(old.get("is_active") or old.get("activation_requested")),
                    "is_active": False})
    await db.update("poi", pid, upd)
    if text_changed:
        task_manager.enqueue(pid)
    return await db.fetchone("SELECT * FROM poi WHERE id=%s", [pid])


async def delete_poi(pid: int) -> bool:
    db = get_db()
    """Xoá mềm: ẩn khỏi app + admin nhưng giữ nguyên dòng, bản dịch/audio và menu để khôi phục."""
    now = _now()
    if not await db.execute(
            "UPDATE poi SET deleted_at=%s, is_active=0, activation_requested=0, updated_at=%s "
            "WHERE id=%s AND deleted_at IS NULL", [now, now, pid]):
        return False
    await db.upsert("removed_pois", {"id": pid, "removed_at": now}, ["removed_at"])  # delta sync báo app xoá POI
    return True


async def toggle_poi(pid: int, active: bool) -> dict | None:
    db = get_db()
    poi = await db.fetchone("SELECT id FROM poi WHERE id=%s AND deleted_at IS NULL", [pid])
    if not poi:
        return None
    if not active:
        await db.update("poi", pid, {"is_active": False, "activation_requested": False, "updated_at": _now()})
    else:
        en = await db.fetchone("SELECT id FROM poi_localizations WHERE poi_id=%s AND lang='en' AND audio_url IS NOT NULL", [pid])
        if en:
            await db.update("poi", pid, {"is_active": True, "activation_requested": False,
                                         "audio_status": "ready", "updated_at": _now()})
        else:  # chưa sẵn sàng → sinh lại trước rồi mới bật
            await db.update("poi", pid, {"activation_requested": True, "audio_status": "processing"})
            task_manager.enqueue(pid)
    return await db.fetchone("SELECT * FROM poi WHERE id=%s", [pid])
