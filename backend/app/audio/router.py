from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import service

router = APIRouter(prefix="/api/v1/audio", tags=["audio"])


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    lang: str = "vi"


@router.get("/languages")
async def languages():
    return {"languages": [{"code": c, "voice": v} for c, v in service.VOICES.items()]}


@router.post("/tts")
async def tts(body: TTSRequest):
    """Tier 2: Edge-TTS stream MP3 (text đã đúng ngôn ngữ)."""
    if body.lang not in service.VOICES:
        raise HTTPException(400, "Ngôn ngữ không được hỗ trợ")
    path, hit = await service.synthesize(body.text, body.lang)
    return FileResponse(
        path, media_type="audio/mpeg",
        headers={"X-Cache": "HIT" if hit else "MISS", "X-Static-Url": service.static_url(path)},
    )
