from datetime import datetime

from fastapi import APIRouter, Query, Request, Response

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


@router.get("/{poi_id}/menu")
async def poi_menu(poi_id: str):
    items = await get_db().menu_items.find({"poi_id": poi_id}).to_list(200)
    return {"items": [{**{k: v for k, v in i.items() if k != "_id"}, "id": i["_id"]} for i in items]}
