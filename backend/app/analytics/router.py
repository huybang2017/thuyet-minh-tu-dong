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


def _csv_cell(v) -> str:
    """Chặn CSV/formula injection khi mở bằng Excel (tên quán do người dùng nhập)."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


@router.get("/export")
async def export_csv(days: int = Query(30, ge=1, le=365), _=Depends(require_permission("analytics:export"))):
    """CSV theo ngày × sự kiện × quán × ngôn ngữ (UTF-8 BOM để Excel đọc đúng tiếng Việt)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await get_db().fetchall(
        "SELECT DATE(DATE_ADD(e.ts, INTERVAL 7 HOUR)) AS day, e.event, e.poi_id, p.name, e.lang, "
        "COUNT(*) AS n, COUNT(DISTINCT e.device_id) AS devices "
        "FROM analytics_events e LEFT JOIN poi p ON p.id=e.poi_id WHERE e.ts >= %s "
        "GROUP BY day, e.event, e.poi_id, p.name, e.lang ORDER BY day, e.event, n DESC", [since])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["ngay", "su_kien", "poi_id", "ten_quan", "ngon_ngu", "so_luot", "so_thiet_bi"])
    for r in rows:
        w.writerow([_csv_cell(x) for x in (r["day"], r["event"], r["poi_id"], r["name"], r["lang"], r["n"], r["devices"])])
    fname = f"thong-ke_{datetime.now(timezone.utc):%Y%m%d}_{days}ngay.csv"
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


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
