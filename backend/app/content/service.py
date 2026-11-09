import hashlib
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

from ..db import get_db
from .seed import build_seed

_PRIVATE = {"_id", "owner_id", "activation_requested", "deleted_at"}


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
    if await db.scalar("SELECT COUNT(*) FROM poi") == 0:
        await db.insert_many("poi", build_seed())


async def dataset_version() -> str:
    db = get_db()
    latest = await db.fetchone("SELECT updated_at FROM poi ORDER BY updated_at DESC LIMIT 1")
    removed = await db.scalar("SELECT COUNT(*) FROM removed_pois")
    count = await db.scalar("SELECT COUNT(*) FROM poi WHERE deleted_at IS NULL")
    raw = f"{count}:{removed}:{latest['updated_at'].isoformat() if latest else ''}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


async def load_all(updated_after: datetime | None = None, lang: str = "vi") -> dict:
    """Full sync, hoặc delta sync khi có updated_after (kèm removed_poi_ids + sync_cursor)."""
    from ..localization import service as loc  # tránh import vòng

    db = get_db()
    cursor_now = datetime.now(timezone.utc)
    removed: list[int] = []
    if updated_after is None:
        docs = await db.fetchall("SELECT * FROM poi WHERE is_active=1 AND deleted_at IS NULL LIMIT 1000")
    else:
        changed_ids = await loc.localized_ids_changed_since(lang, updated_after) if lang != "vi" else []
        sql, args = "SELECT * FROM poi WHERE updated_at > %s", [updated_after]
        if changed_ids:
            sql += f" OR id IN ({','.join(['%s'] * len(changed_ids))})"
            args += changed_ids
        touched = await db.fetchall(sql + " LIMIT 1000", args)
        docs = [d for d in touched if d.get("is_active") and not d.get("deleted_at")]
        removed = [d["_id"] for d in touched if not d.get("is_active") or d.get("deleted_at")]
        removed += [d["id"] for d in await db.fetchall("SELECT id FROM removed_pois WHERE removed_at > %s", [updated_after])]
    return {
        "dataset_version": await dataset_version(),
        "sync_mode": "delta" if updated_after else "full",
        "removed_poi_ids": sorted(set(removed)),
        "sync_cursor": cursor_now.isoformat(),
        "pois": [public_poi(d) for d in docs],
    }


async def nearby(lat: float, lng: float, radius_m: int, limit: int = 20) -> list[dict]:
    """Haversine ngay trong MySQL (không cần spatial index), sắp theo khoảng cách."""
    rows = await get_db().fetchall(
        "SELECT *, (2 * 6371000 * ASIN(SQRT(POWER(SIN(RADIANS(lat - %s) / 2), 2) + "
        "COS(RADIANS(%s)) * COS(RADIANS(lat)) * POWER(SIN(RADIANS(lng - %s) / 2), 2)))) AS dist_m "
        "FROM poi WHERE is_active=1 AND deleted_at IS NULL HAVING dist_m <= %s ORDER BY dist_m LIMIT %s",
        [lat, lat, lng, radius_m, limit])
    for d in rows:
        d.pop("dist_m", None)
    return [{**public_poi(d), "distance_m": round(haversine_m(lat, lng, d["lat"], d["lng"]))} for d in rows]
