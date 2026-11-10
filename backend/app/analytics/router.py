import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
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


async def _poi_names(ids: list[str]) -> dict[str, str]:
    if not ids:
        return {}
    return {d["_id"]: d["name"] async for d in get_db().poi.find({"_id": {"$in": ids}}, {"name": 1})}


def _csv_cell(v) -> str:
    """Chặn CSV/formula injection khi mở bằng Excel (tên quán do người dùng nhập)."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


@router.get("/export")
async def export_csv(days: int = Query(30, ge=1, le=365), _=Depends(require_permission("analytics:export"))):
    """CSV theo ngày × sự kiện × quán × ngôn ngữ (UTF-8 BOM để Excel đọc đúng tiếng Việt)."""
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = [d async for d in db.analytics_events.aggregate([
        {"$match": {"ts": {"$gte": since}}},
        {"$group": {"_id": {"day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$ts", "timezone": "Asia/Ho_Chi_Minh"}},
                            "event": "$event", "poi_id": "$poi_id", "lang": "$lang"},
                    "count": {"$sum": 1}, "devices": {"$addToSet": "$device_id"}}},
        {"$sort": {"_id.day": 1, "_id.event": 1, "count": -1}},
    ])]
    names = await _poi_names(sorted({r["_id"]["poi_id"] for r in rows if r["_id"].get("poi_id")}))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ngay", "su_kien", "poi_id", "ten_quan", "ngon_ngu", "so_luot", "so_thiet_bi"])
    for r in rows:
        k = r["_id"]
        w.writerow([_csv_cell(x) for x in (k["day"], k["event"], k.get("poi_id"), names.get(k.get("poi_id")),
                                           k.get("lang"), r["count"], len(r["devices"]))])
    fname = f"thong-ke_{datetime.now(timezone.utc):%Y%m%d}_{days}ngay.csv"
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/summary")
async def summary(days: int = 7, _=Depends(require_permission("analytics:view"))):
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(days=min(days, 90))
    by_event = {d["_id"]: d["n"] async for d in db.analytics_events.aggregate(
        [{"$match": {"ts": {"$gte": since}}}, {"$group": {"_id": "$event", "n": {"$sum": 1}}}])}
    top = [{"poi_id": d["_id"], "plays": d["n"]} async for d in db.analytics_events.aggregate(
        [{"$match": {"ts": {"$gte": since}, "event": "narration_played", "poi_id": {"$ne": None}}},
         {"$group": {"_id": "$poi_id", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 5}])]
    names = await _poi_names([t["poi_id"] for t in top])
    for t in top:
        t["name"] = names.get(t["poi_id"])
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
