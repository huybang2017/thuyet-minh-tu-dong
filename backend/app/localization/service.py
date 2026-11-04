import asyncio
import hashlib
from datetime import datetime, timezone

from .. import cache
from ..audio import service as audio
from ..db import get_db

ON_DEMAND_LIMIT = 30
ON_DEMAND_WINDOW_S = 600


async def check_rate_limit(client: str) -> int | None:
    """Trả về Retry-After (giây) nếu bị chặn, ngược lại None. Dùng Redis (shared-state)."""
    return await cache.rate_hit(f"ondemand:{client}", ON_DEMAND_LIMIT, ON_DEMAND_WINDOW_S)


async def ensure_localization(poi: dict, lang: str) -> dict:
    """Dịch + TTS cho (poi, lang), upsert vào poi_localizations."""
    db = get_db()
    key = {"poi_id": poi["_id"], "lang": lang}
    src_hash = hashlib.md5(f"{poi['name']}|{poi['description']}".encode()).hexdigest()
    existing = await db.poi_localizations.find_one(key)
    if existing and existing.get("audio_url") and existing.get("source_hash") == src_hash:
        return existing
    name, desc = await asyncio.gather(
        audio.translate_text(poi["name"], lang), audio.translate_text(poi["description"], lang)
    )
    path, _ = await audio.synthesize(f"{name}. {desc}", lang)
    doc = {
        **key, "name": name, "description": desc,
        "audio_url": audio.static_url(path),
        "source_hash": src_hash,
        "updated_at": datetime.now(timezone.utc),
    }
    await db.poi_localizations.update_one(key, {"$set": doc}, upsert=True)
    return doc


async def hydrate(pois: list[dict], lang: str) -> list[dict]:
    """3-tier fallback: target → en → vi. is_fallback báo cho frontend."""
    if lang == "vi":
        return [{**p, "lang": "vi", "is_fallback": False, "audio_url": None} for p in pois]
    db = get_db()
    ids = [p["id"] for p in pois]
    locs: dict[tuple, dict] = {}
    async for d in db.poi_localizations.find({"poi_id": {"$in": ids}, "lang": {"$in": [lang, "en"]}}):
        locs[(d["poi_id"], d["lang"])] = d
    out = []
    for p in pois:
        hit = locs.get((p["id"], lang))
        used, fallback = lang, False
        if not hit:
            hit, used, fallback = locs.get((p["id"], "en")), "en", True
        if hit:
            url = f"{hit['audio_url']}?v={p['updated_at']}&l={used}" if hit.get("audio_url") else None
            out.append({**p, "name": hit["name"], "description": hit["description"],
                        "lang": used, "is_fallback": fallback, "audio_url": url})
        else:  # tầng cuối: nguyên bản tiếng Việt
            out.append({**p, "lang": "vi", "is_fallback": True, "audio_url": None})
    return out


async def localized_ids_changed_since(lang: str, since: datetime) -> list[str]:
    db = get_db()
    cur = db.poi_localizations.find({"lang": {"$in": [lang, "en"]}, "updated_at": {"$gt": since}}, {"poi_id": 1})
    return list({d["poi_id"] async for d in cur})
