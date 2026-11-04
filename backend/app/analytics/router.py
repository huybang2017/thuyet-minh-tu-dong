from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import cache
from ..admin.deps import require_permission
from ..db import get_db

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])
EVENTS = {"app_open", "language_changed", "narration_played", "poi_viewed"}


class Collect(BaseModel):
    consent: bool
    device_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    session_id: str | None = Field(default=None, max_length=64)
    event: str
    poi_id: str | None = Field(default=None, max_length=80)
    lang: str | None = Field(default=None, max_length=8)


@router.post("/collect", status_code=202)
async def collect(body: Collect, request: Request):
    """Chỉ ingest khi user đã consent; nếu không → 403, không ghi gì cả."""
    if not body.consent:
        raise HTTPException(403, "Cần đồng ý thu thập dữ liệu")
    if body.event not in EVENTS:
        raise HTTPException(422, "Sự kiện không hợp lệ")
    ip = request.client.host if request.client else "anon"
    if await cache.rate_hit(f"collect:{ip}", 120, 60):
        raise HTTPException(429, "Quá nhiều sự kiện")
    now = datetime.now(timezone.utc)
    db = get_db()
    await cache.presence_touch(body.device_id)
    await db.analytics_devices.update_one({"_id": body.device_id}, {"$set": {"last_seen": now}, "$setOnInsert": {"first_seen": now}}, upsert=True)
    await db.analytics_events.insert_one({"device_id": body.device_id, "session_id": body.session_id, "event": body.event,
                                          "poi_id": body.poi_id, "lang": body.lang, "ts": now})
    return {"ok": True}


@router.get("/summary")
async def summary(days: int = 7, _=Depends(require_permission("analytics:view"))):
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(days=min(days, 90))
    by_event = {d["_id"]: d["n"] async for d in db.analytics_events.aggregate(
        [{"$match": {"ts": {"$gte": since}}}, {"$group": {"_id": "$event", "n": {"$sum": 1}}}])}
    top = [{"poi_id": d["_id"], "plays": d["n"]} async for d in db.analytics_events.aggregate(
        [{"$match": {"ts": {"$gte": since}, "event": "narration_played", "poi_id": {"$ne": None}}},
         {"$group": {"_id": "$poi_id", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 5}])]
    by_lang = {d["_id"] or "unknown": d["n"] async for d in db.analytics_events.aggregate(
        [{"$match": {"ts": {"$gte": since}, "event": "language_changed"}}, {"$group": {"_id": "$lang", "n": {"$sum": 1}}}])}
    return {
        "window_days": days,
        # số anonymous device đã consent còn trong cửa sổ trượt — không phải tổng traffic
        "tracked_online_users": await cache.presence_count(),
        "devices": await db.analytics_devices.count_documents({"last_seen": {"$gte": since}}),
        "events": by_event, "top_pois": top, "languages": by_lang,
        "redis": await cache.redis_ok(),
    }
