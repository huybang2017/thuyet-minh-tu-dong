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
    poi_id: int | None = Field(default=None, ge=1)
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
    await db.upsert("analytics_devices", {"device_id": body.device_id, "first_seen": now, "last_seen": now}, ["last_seen"])
    await db.insert("analytics_events", {"device_id": body.device_id, "session_id": body.session_id, "event": body.event,
                                          "poi_id": body.poi_id, "lang": body.lang, "ts": now})
    return {"ok": True}


@router.get("/summary")
async def summary(days: int = 7, _=Depends(require_permission("analytics:view"))):
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(days=min(days, 90))
    by_event = {d["event"]: d["n"] for d in await db.fetchall(
        "SELECT event, COUNT(*) AS n FROM analytics_events WHERE ts >= %s GROUP BY event", [since])}
    top = [{"poi_id": d["poi_id"], "name": d["name"], "plays": d["n"]} for d in await db.fetchall(
        "SELECT e.poi_id, p.name, COUNT(*) AS n FROM analytics_events e LEFT JOIN poi p ON p.id=e.poi_id "
        "WHERE e.ts >= %s AND e.event='narration_played' AND e.poi_id IS NOT NULL "
        "GROUP BY e.poi_id, p.name ORDER BY n DESC LIMIT 5", [since])]
    by_lang = {(d["lang"] or "unknown"): d["n"] for d in await db.fetchall(
        "SELECT lang, COUNT(*) AS n FROM analytics_events WHERE ts >= %s AND event='language_changed' GROUP BY lang", [since])}
    return {
        "window_days": days,
        # số anonymous device đã consent còn trong cửa sổ trượt — không phải tổng traffic
        "tracked_online_users": await cache.presence_count(),
        "devices": await db.scalar("SELECT COUNT(*) FROM analytics_devices WHERE last_seen >= %s", [since]),
        "events": by_event, "top_pois": top, "languages": by_lang,
        "redis": await cache.redis_ok(),
    }
