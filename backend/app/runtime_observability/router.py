"""Lane vị trí runtime công khai, TÁCH BIỆT khỏi analytics consent: chỉ đếm theo ô lưới + giờ, không lưu device/user."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import cache
from ..admin.deps import require_permission
from ..db import get_db

router = APIRouter(prefix="/api/v1", tags=["runtime_observability"])


class Loc(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


@router.post("/runtime/location", status_code=202)
async def ingest(body: Loc, request: Request):
    ip = request.client.host if request.client else "anon"
    if await cache.rate_hit(f"loc:{ip}", 30, 60):
        raise HTTPException(429, "Quá nhiều yêu cầu")
    hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    cell = f"{round(body.lat, 3)}:{round(body.lng, 3)}"  # ~110 m, không định danh được cá nhân
    await get_db().runtime_location_hourly.update_one(
        {"hour": hour, "cell": cell},
        {"$inc": {"count": 1}, "$setOnInsert": {"lat": round(body.lat, 3), "lng": round(body.lng, 3)}}, upsert=True)
    return {"ok": True}


@router.get("/admin/observability")
async def window(hours: int = 24, _=Depends(require_permission("system:logs"))):
    since = datetime.now(timezone.utc) - timedelta(hours=min(hours, 168))
    docs = await get_db().runtime_location_hourly.find({"hour": {"$gte": since}}).to_list(2000)
    cells: dict[str, dict] = {}
    for d in docs:
        c = cells.setdefault(d["cell"], {"lat": d["lat"], "lng": d["lng"], "count": 0})
        c["count"] += d["count"]
    return {"window_hours": hours, "total": sum(c["count"] for c in cells.values()),
            "cells": sorted(cells.values(), key=lambda c: -c["count"])[:50]}
