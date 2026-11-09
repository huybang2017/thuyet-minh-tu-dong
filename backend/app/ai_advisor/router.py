from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..admin.deps import get_current_user
from ..config import settings
from ..db import get_db

router = APIRouter(prefix="/api/v1/ai", tags=["ai_advisor"])

PROMPT = (
    "Bạn là biên tập viên du lịch ẩm thực. Viết lại mô tả quán sau thành 200-300 từ tiếng Việt, giọng văn hấp dẫn. "
    "TUYỆT ĐỐI KHÔNG bịa thêm món, giá, địa chỉ hay sự kiện không có trong dữ liệu; "
    "chỉ được thêm tính từ tích cực và cách diễn đạt hay.\n\nTên quán: {name}\nMô tả gốc: {description}"
)


class Enhance(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=3000)


def _unlimited(user: dict) -> bool:
    return user["role"] in ("super_admin", "admin")


def _allowed(user: dict) -> bool:
    p = user.get("permissions", [])
    return "owner:access" in p or "poi:update" in p


async def _used_today(user_id: int) -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    d = await get_db().fetchone("SELECT `count` FROM ai_usage_limits WHERE user_id=%s AND `date`=%s", [user_id, today])
    return d["count"] if d else 0


@router.get("/usage")
async def usage(user: dict = Depends(get_current_user)):
    if not _allowed(user):
        raise HTTPException(403, "Không có quyền dùng AI Advisor")
    if _unlimited(user):
        return {"limit": None, "used": await _used_today(user["sub"]), "remaining": None}
    used = await _used_today(user["sub"])
    return {"limit": settings.owner_daily_limit, "used": used, "remaining": max(settings.owner_daily_limit - used, 0)}


@router.post("/enhance-description")
async def enhance(body: Enhance, user: dict = Depends(get_current_user)):
    if not _allowed(user):
        raise HTTPException(403, "Không có quyền dùng AI Advisor")
    if not _unlimited(user) and await _used_today(user["sub"]) >= settings.owner_daily_limit:
        raise HTTPException(429, f"Đã dùng hết {settings.owner_daily_limit} lượt hôm nay")
    if not settings.gemini_api_key:
        # lỗi rõ ràng theo provider để UI hiển thị, không tốn quota
        raise HTTPException(503, detail={"code": "provider_unconfigured", "message": "GEMINI_API_KEY chưa được cấu hình"})
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, headers={"x-goog-api-key": settings.gemini_api_key},
                                  json={"contents": [{"parts": [{"text": PROMPT.format(**body.model_dump())}]}]})
    except httpx.TimeoutException:
        raise HTTPException(504, detail={"code": "provider_timeout", "message": "Gemini phản hồi quá 30 giây"})
    except httpx.HTTPError:
        raise HTTPException(502, detail={"code": "provider_unreachable", "message": "Không kết nối được Gemini"})
    if r.status_code != 200:
        raise HTTPException(502, detail={"code": "provider_error", "message": f"Gemini trả về {r.status_code}"})
    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, ValueError):
        raise HTTPException(502, detail={"code": "provider_bad_response", "message": "Phản hồi Gemini không hợp lệ"})
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await get_db().execute("INSERT INTO ai_usage_limits (user_id, `date`, `count`) VALUES (%s,%s,1) ON DUPLICATE KEY UPDATE `count`=`count`+1", [user["sub"], today])
    return {"description": text}
