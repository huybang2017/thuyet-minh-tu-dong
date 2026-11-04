import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..audio.service import VOICES
from ..db import get_db
from . import service

router = APIRouter(prefix="/api/v1/localizations", tags=["localization"])


class OnDemand(BaseModel):
    poi_id: str
    lang: str


async def _warm(lang: str):
    pois = await get_db().poi.find({"is_active": True}).to_list(1000)
    for p in pois:
        try:
            await service.ensure_localization(p, lang)
        except Exception:
            pass  # warmup best-effort; on-demand sẽ thử lại


@router.post("/on-demand")
async def on_demand(body: OnDemand, request: Request):
    """Tier 1.5: dịch + TTS ngay cho 1 POI, trả audio_url mới."""
    if body.lang not in VOICES:
        raise HTTPException(400, "Ngôn ngữ không được hỗ trợ")
    retry = await service.check_rate_limit(request.client.host if request.client else "anon")
    if retry:
        return JSONResponse({"detail": "Quá nhiều yêu cầu"}, status_code=429, headers={"Retry-After": str(retry)})
    poi = await get_db().poi.find_one({"_id": body.poi_id})
    if not poi:
        raise HTTPException(404, "POI không tồn tại")
    loc = await service.ensure_localization(poi, body.lang)
    return {"poi_id": body.poi_id, "lang": body.lang, "name": loc["name"],
            "description": loc["description"], "audio_url": f"{loc['audio_url']}?l={body.lang}"}


@router.post("/warmup")
async def warmup(lang: str, tasks: BackgroundTasks):
    if lang not in VOICES:
        raise HTTPException(400, "Ngôn ngữ không được hỗ trợ")
    tasks.add_task(_warm, lang)
    return {"status": "started", "lang": lang}
