import hashlib
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

from ..db import get_db
from .seed import build_seed

_PRIVATE = {"_id", "location", "owner_id", "activation_requested"}


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    r = 6371000
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lng2 - lng1) / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


def public_poi(doc: dict) -> dict:
    out = {k: _iso(v) for k, v in doc.items() if k not in _PRIVATE}
    out["id"] = doc["_id"]
    return out


_public = public_poi


async def seed_if_empty() -> None:
    db = get_db()
    if await db.poi.estimated_document_count() == 0:
        await db.poi.insert_many(build_seed())


async def dataset_version() -> str:
    db = get_db()
    latest = await db.poi.find_one({}, sort=[("updated_at", -1)], projection={"updated_at": 1})
    removed = await db.removed_pois.count_documents({})
    count = await db.poi.count_documents({})
    raw = f"{count}:{removed}:{latest['updated_at'].isoformat() if latest else ''}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


async def load_all(updated_after: datetime | None = None, lang: str = "vi") -> dict:
    """Full sync, hoặc delta sync khi có updated_after (kèm removed_poi_ids + sync_cursor)."""
    from ..localization import service as loc  # tránh import vòng

    db = get_db()
    cursor_now = datetime.now(timezone.utc)
    removed: list[str] = []
    if updated_after is None:
        docs = await db.poi.find({"is_active": True}).to_list(length=1000)
    else:
        changed_ids = await loc.localized_ids_changed_since(lang, updated_after) if lang != "vi" else []
        q = {"$or": [{"updated_at": {"$gt": updated_after}}, {"_id": {"$in": changed_ids}}]}
        touched = await db.poi.find(q).to_list(length=1000)
        docs = [d for d in touched if d.get("is_active")]
        removed = [d["_id"] for d in touched if not d.get("is_active")]
        removed += [d["_id"] async for d in db.removed_pois.find({"removed_at": {"$gt": updated_after}})]
    return {
        "dataset_version": await dataset_version(),
        "sync_mode": "delta" if updated_after else "full",
        "removed_poi_ids": sorted(set(removed)),
        "sync_cursor": cursor_now.isoformat(),
        "pois": [public_poi(d) for d in docs],
    }


async def nearby(lat: float, lng: float, radius_m: int, limit: int = 20) -> list[dict]:
    db = get_db()
    try:
        cursor = db.poi.find({
            "is_active": True,
            "location": {"$nearSphere": {
                "$geometry": {"type": "Point", "coordinates": [lng, lat]},
                "$maxDistance": radius_m,
            }},
        }).limit(limit)
        docs = await cursor.to_list(length=limit)
    except Exception:
        # fallback Haversine in-memory
        all_docs = await db.poi.find({"is_active": True}).to_list(length=1000)
        docs = sorted(
            (d for d in all_docs if haversine_m(lat, lng, d["lat"], d["lng"]) <= radius_m),
            key=lambda d: haversine_m(lat, lng, d["lat"], d["lng"]),
        )[:limit]
    return [{**public_poi(d), "distance_m": round(haversine_m(lat, lng, d["lat"], d["lng"]))} for d in docs]
