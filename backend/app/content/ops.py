"""Nghiệp vụ ghi POI dùng chung cho admin và duyệt submission của owner."""
import re
import unicodedata
from datetime import datetime, timezone

from ..audio import task_manager
from ..db import get_db

MAX_POI_IMAGES = 8
EDITABLE = {"name", "description", "lat", "lng", "trigger_radius", "audio_priority", "images", "address"}


def _now():
    return datetime.now(timezone.utc)


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFD", name.replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "poi"


def _clean(data: dict) -> dict:
    out = {k: v for k, v in data.items() if k in EDITABLE and v is not None}
    if "images" in out:
        out["images"] = list(out["images"])[:MAX_POI_IMAGES]
    return out


async def create_poi(data: dict, owner_id: str | None = None, activate: bool = True) -> dict:
    db = get_db()
    d = _clean(data)
    base = f"poi-{slugify(d['name'])}"
    pid, n = base, 1
    while await db.poi.find_one({"_id": pid}, {"_id": 1}):
        n += 1
        pid = f"{base}-{n}"
    doc = {
        "_id": pid, "images": [], "trigger_radius": 30, "audio_priority": 3, **d,
        "location": {"type": "Point", "coordinates": [d["lng"], d["lat"]]},
        "owner_id": owner_id,
        # text lưu trước; chỉ public khi EN + audio sẵn sàng (activation gate)
        "is_active": False, "activation_requested": activate, "audio_status": "processing",
        "updated_at": _now(),
    }
    await db.poi.insert_one(doc)
    task_manager.enqueue(pid)
    return doc


async def update_poi(pid: str, data: dict) -> dict | None:
    db = get_db()
    old = await db.poi.find_one({"_id": pid})
    if not old:
        return None
    d = _clean(data)
    upd = {**d, "updated_at": _now()}
    if "lat" in d or "lng" in d:
        upd["location"] = {"type": "Point", "coordinates": [d.get("lng", old["lng"]), d.get("lat", old["lat"])]}
    text_changed = ("description" in d and d["description"] != old["description"]) or \
                   ("name" in d and d["name"] != old["name"])
    if text_changed:
        # xoá audio cũ, khoá public tới khi sinh lại xong, nhớ ý định kích hoạt
        await db.poi_localizations.delete_many({"poi_id": pid})
        upd.update({"audio_status": "processing", "activation_requested": bool(old.get("is_active") or old.get("activation_requested")),
                    "is_active": False})
    await db.poi.update_one({"_id": pid}, {"$set": upd})
    if text_changed:
        task_manager.enqueue(pid)
    return await db.poi.find_one({"_id": pid})


async def delete_poi(pid: str) -> bool:
    db = get_db()
    res = await db.poi.delete_one({"_id": pid})
    if not res.deleted_count:
        return False
    await db.poi_localizations.delete_many({"poi_id": pid})
    await db.menu_items.delete_many({"poi_id": pid})
    await db.removed_pois.update_one({"_id": pid}, {"$set": {"removed_at": _now()}}, upsert=True)
    return True


async def toggle_poi(pid: str, active: bool) -> dict | None:
    db = get_db()
    poi = await db.poi.find_one({"_id": pid})
    if not poi:
        return None
    if not active:
        await db.poi.update_one({"_id": pid}, {"$set": {"is_active": False, "activation_requested": False, "updated_at": _now()}})
    else:
        en = await db.poi_localizations.find_one({"poi_id": pid, "lang": "en", "audio_url": {"$ne": None}})
        if en:
            await db.poi.update_one({"_id": pid}, {"$set": {"is_active": True, "activation_requested": False,
                                                            "audio_status": "ready", "updated_at": _now()}})
        else:  # chưa sẵn sàng → sinh lại trước rồi mới bật
            await db.poi.update_one({"_id": pid}, {"$set": {"activation_requested": True, "audio_status": "processing"}})
            task_manager.enqueue(pid)
    return await db.poi.find_one({"_id": pid})
