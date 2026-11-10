import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, Response

from ..audio import service as audio_service
from ..db import get_db
from ..localization import service as localization_service
from . import service

router = APIRouter(prefix="/api/v1/poi", tags=["content"])


@router.get("/load-all")
async def load_all(request: Request, response: Response, updated_after: datetime | None = None, lang: str = "vi"):
    version = await service.dataset_version()
    # ETag phụ thuộc cả ngôn ngữ và số bản dịch đã có
    n_loc = await get_db().poi_localizations.count_documents({"lang": lang}) if lang != "vi" else 0
    etag = f'"{version}-{lang}-{n_loc}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    data = await service.load_all(updated_after, lang)
    data["pois"] = await localization_service.hydrate(data["pois"], lang)
    return data


@router.get("/nearby")
async def nearby(lat: float, lng: float, radius: int = Query(1500, le=5000)):
    return {"pois": await service.nearby(lat, lng, radius)}


MENU_TRANSLATE_TIMEOUT_S = 6
_bg: set[asyncio.Task] = set()


def _settle(t: asyncio.Task) -> None:
    _bg.discard(t)
    if not t.cancelled():
        t.exception()  # đánh dấu đã xử lý, tránh cảnh báo "exception was never retrieved"


async def _translated(text: str | None, lang: str) -> str | None:
    """Dịch best-effort (có cache DB); quá hạn hoặc lỗi → None, frontend hiển thị bản gốc.
    Quá hạn thì việc dịch vẫn chạy tiếp dưới nền để lần mở sau có sẵn trong cache."""
    if not text or lang == "vi":
        return None
    task = asyncio.ensure_future(audio_service.translate_text(text, lang))
    _bg.add(task)
    task.add_done_callback(_settle)
    try:
        return await asyncio.wait_for(asyncio.shield(task), MENU_TRANSLATE_TIMEOUT_S)
    except Exception:
        return None


@router.get("/{poi_id}/menu")
async def poi_menu(poi_id: str, lang: str = "vi"):
    """Thực đơn cho du khách: chỉ quán đang public; tên/mô tả món kèm bản dịch nếu có."""
    db = get_db()
    if not await db.poi.find_one({"_id": poi_id, "is_active": True}, {"_id": 1}):
        raise HTTPException(404, "Quán không tồn tại")
    if lang not in audio_service.VOICES:
        lang = "vi"
    items = await db.menu_items.find({"poi_id": poi_id}).sort([("price", 1), ("name", 1)]).to_list(200)
    names = await asyncio.gather(*(_translated(i["name"], lang) for i in items))
    descs = await asyncio.gather(*(_translated(i.get("description"), lang) for i in items))
    return {"lang": lang, "items": [
        {"id": i["_id"], "poi_id": i["poi_id"], "name": i["name"], "price": i.get("price"),
         "description": i.get("description"), "name_translated": n, "description_translated": d}
        for i, n, d in zip(items, names, descs)]}
