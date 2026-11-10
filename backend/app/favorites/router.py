import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from ..admin.deps import get_current_user
from ..content.service import public_poi
from ..db import get_db

router = APIRouter(prefix="/api/v1/favorites", tags=["favorites"])
_STOP_WORDS = {"quan", "quán", "mon", "món", "va", "và", "voi", "với", "cac", "các", "mot", "một", "tu", "từ", "cho", "cua", "của", "tai", "tại", "the", "thể", "nha", "nhà", "ngon", "đặc", "biệt"}


def _tokens(text: str) -> set[str]:
    return {word.casefold() for word in re.findall(r"[^\W_]+", text, flags=re.UNICODE) if len(word) > 2 and word.casefold() not in _STOP_WORDS}


async def _preferences(db, poi_ids: list[str]) -> set[str]:
    preferences: set[str] = set()
    async for poi in db.poi.find({"_id": {"$in": poi_ids}}):
        preferences |= _tokens(f"{poi.get('name', '')} {poi.get('description', '')}")
    async for item in db.menu_items.find({"poi_id": {"$in": poi_ids}}, {"name": 1, "description": 1}):
        preferences |= _tokens(f"{item.get('name', '')} {item.get('description') or ''}")
    return preferences


@router.get("")
async def list_favorites(user: dict = Depends(get_current_user)):
    db = get_db()
    docs = await db.favorites.find({"user_id": user["sub"]}).sort("created_at", -1).to_list(500)
    poi_ids = [doc["poi_id"] for doc in docs]
    pois = {doc["_id"]: doc async for doc in db.poi.find({"_id": {"$in": poi_ids}, "is_active": True})}
    return {"items": [public_poi(pois[d["poi_id"]]) | {"favorite_at": d["created_at"].isoformat()}
                      for d in docs if d["poi_id"] in pois]}


@router.post("/{poi_id}", status_code=201)
async def save_favorite(poi_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    poi = await db.poi.find_one({"_id": poi_id, "is_active": True}, {"_id": 1})
    if not poi:
        raise HTTPException(404, "Quán không tồn tại hoặc không còn được hiển thị")
    await db.favorites.update_one(
        {"_id": f"{user['sub']}:{poi_id}"},
        {"$setOnInsert": {"_id": f"{user['sub']}:{poi_id}", "user_id": user["sub"],
                          "poi_id": poi_id, "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"ok": True, "poi_id": poi_id}


@router.delete("/{poi_id}")
async def remove_favorite(poi_id: str, user: dict = Depends(get_current_user)):
    await get_db().favorites.delete_one({"_id": f"{user['sub']}:{poi_id}", "user_id": user["sub"]})
    return {"ok": True, "poi_id": poi_id}


@router.get("/recommendations")
async def recommendations(user: dict = Depends(get_current_user)):
    db = get_db()
    favorites = await db.favorites.find({"user_id": user["sub"]}).to_list(500)
    favorite_ids = [doc["poi_id"] for doc in favorites]
    if not favorite_ids:
        return {"items": [], "message": "Lưu vài quán yêu thích để nhận gợi ý phù hợp."}

    preferences = await _preferences(db, favorite_ids)
    candidates = await db.poi.find({"is_active": True, "_id": {"$nin": favorite_ids}}).to_list(1000)
    menu_names: dict[str, list[str]] = {}
    async for item in db.menu_items.find({"poi_id": {"$in": [p["_id"] for p in candidates]}}, {"poi_id": 1, "name": 1}):
        menu_names.setdefault(item["poi_id"], []).append(item.get("name", ""))

    scored = []
    for poi in candidates:
        terms = _tokens(f"{poi.get('name', '')} {poi.get('description', '')} {' '.join(menu_names.get(poi['_id'], []))}")
        overlap = preferences & terms
        if overlap:
            scored.append((len(overlap) / max(len(terms), 1), poi, sorted(overlap, key=len, reverse=True)[:3]))
    scored.sort(key=lambda entry: (entry[0], entry[1].get("name", "")), reverse=True)
    return {"items": [public_poi(poi) | {"recommendation_reason": "Có điểm chung: " + ", ".join(terms)}
                       for _, poi, terms in scored[:10]]}
