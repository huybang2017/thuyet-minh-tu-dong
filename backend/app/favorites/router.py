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


async def _preferences(db, poi_ids: list[int]) -> set[str]:
    preferences: set[str] = set()
    if not poi_ids:
        return preferences
    placeholders = ",".join(["%s"] * len(poi_ids))
    rows = await db.fetchall(f"SELECT * FROM poi WHERE id IN ({placeholders})", poi_ids)
    for poi in rows:
        preferences |= _tokens(f"{poi.get('name', '')} {poi.get('description', '')}")
    rows = await db.fetchall(f"SELECT * FROM menu_items WHERE poi_id IN ({placeholders})", poi_ids)
    for item in rows:
        preferences |= _tokens(f"{item.get('name', '')} {item.get('description') or ''}")
    return preferences


@router.get("")
async def list_favorites(user: dict = Depends(get_current_user)):
    db = get_db()
    docs = await db.fetchall(
        "SELECT * FROM favorites WHERE user_id=%s ORDER BY created_at DESC LIMIT 500", [user["sub"]])
    poi_ids = [doc["poi_id"] for doc in docs]
    if poi_ids:
        placeholders = ",".join(["%s"] * len(poi_ids))
        rows = await db.fetchall(
            f"SELECT * FROM poi WHERE id IN ({placeholders}) AND is_active=1 AND deleted_at IS NULL", poi_ids)
        pois = {d["id"]: d for d in rows}
    else:
        pois = {}
    return {"items": [public_poi(pois[d["poi_id"]]) | {"favorite_at": d["created_at"].isoformat()}
                      for d in docs if d["poi_id"] in pois]}


@router.post("/{poi_id}", status_code=201)
async def save_favorite(poi_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    poi = await db.fetchone("SELECT id FROM poi WHERE id=%s AND is_active=1 AND deleted_at IS NULL", [poi_id])
    if not poi:
        raise HTTPException(404, "Quán không tồn tại hoặc không còn được hiển thị")
    fav_id = f"{user['sub']}:{poi_id}"
    existing = await db.fetchone("SELECT name FROM favorites WHERE name=%s", [fav_id])
    if not existing:
        await db.insert("favorites", {
            "name": fav_id, "user_id": user["sub"], "poi_id": poi_id,
            "created_at": datetime.now(timezone.utc),
        })
    return {"ok": True, "poi_id": poi_id}


@router.delete("/{poi_id}")
async def remove_favorite(poi_id: int, user: dict = Depends(get_current_user)):
    await db.execute(
        "DELETE FROM favorites WHERE name=%s AND user_id=%s", [f"{user['sub']}:{poi_id}", user["sub"]])
    return {"ok": True, "poi_id": poi_id}


@router.get("/recommendations")
async def recommendations(user: dict = Depends(get_current_user)):
    db = get_db()
    favorites = await db.fetchall("SELECT * FROM favorites WHERE user_id=%s", [user["sub"]])
    favorite_ids = [doc["poi_id"] for doc in favorites]
    if not favorite_ids:
        return {"items": [], "message": "Lưu vài quán yêu thích để nhận gợi ý phù hợp."}

    preferences = await _preferences(db, favorite_ids)
    placeholders = ",".join(["%s"] * len(favorite_ids))
    candidates = await db.fetchall(
        f"SELECT * FROM poi WHERE is_active=1 AND deleted_at IS NULL AND id NOT IN ({placeholders}) LIMIT 1000",
        favorite_ids)
    menu_names: dict[int, list[str]] = {}
    if candidates:
        cand_ids = [p["id"] for p in candidates]
        cand_placeholders = ",".join(["%s"] * len(cand_ids))
        rows = await db.fetchall(
            f"SELECT * FROM menu_items WHERE poi_id IN ({cand_placeholders})", cand_ids)
        for item in rows:
            menu_names.setdefault(item["poi_id"], []).append(item.get("name", ""))

    scored = []
    for poi in candidates:
        terms = _tokens(f"{poi.get('name', '')} {poi.get('description', '')} {' '.join(menu_names.get(poi['id'], []))}")
        overlap = preferences & terms
        if overlap:
            scored.append((len(overlap) / max(len(terms), 1), poi, sorted(overlap, key=len, reverse=True)[:3]))
    scored.sort(key=lambda entry: (entry[0], entry[1].get("name", "")), reverse=True)
    return {"items": [public_poi(poi) | {"recommendation_reason": "Có điểm chung: " + ", ".join(terms)}
                       for _, poi, terms in scored[:10]]}
