from fastapi import APIRouter, Depends, HTTPException

from ..admin import service
from ..admin.deps import get_current_user, require_owner
from ..admin.router import PoiIn, PoiPatch
from ..content.service import public_poi
from ..db import get_db

router = APIRouter(prefix="/api/v1/owner", tags=["owner"])
ser = service.ser


@router.get("/registration-status")
async def registration_status(user: dict = Depends(get_current_user)):
    """Lane duy nhất owner chưa xác minh được dùng."""
    db = get_db()
    reg = await db.poi_owner_registrations.find_one({"user_id": user["sub"]}, sort=[("created_at", -1)])
    u = await db.admin_users.find_one({"_id": user["sub"]})
    if not reg:
        raise HTTPException(404, "Không có đơn đăng ký")
    return {"status": reg["status"], "admin_note": reg.get("admin_note"), "shop_name": reg["shop_name"],
            "is_poi_owner_verified": bool(u and u.get("is_poi_owner_verified"))}


@router.get("/pois")
async def my_pois(user: dict = Depends(require_owner)):
    docs = await get_db().poi.find({"owner_id": user["sub"]}).to_list(200)
    return {"items": [public_poi(d) | {"audio_status": d.get("audio_status")} for d in docs]}


@router.post("/pois", status_code=201)
async def submit_new_poi(body: PoiIn, user: dict = Depends(require_owner)):
    if "owner:submit_poi" not in user["permissions"]:
        raise HTTPException(403, "Thiếu quyền owner:submit_poi")
    sub = {"_id": service.new_id(), "owner_id": user["sub"], "type": "create", "poi_id": None,
           "data": body.model_dump(exclude_none=True), "status": "pending", "admin_note": None,
           "created_at": service.now()}
    await get_db().poi_submissions.insert_one(sub)
    return ser(sub)


@router.put("/pois/{pid}")
async def submit_update(pid: str, body: PoiPatch, user: dict = Depends(require_owner)):
    """Owner chỉ sửa được quán của mình; thay đổi chờ admin duyệt mới lên app."""
    if "owner:manage_own_poi" not in user["permissions"]:
        raise HTTPException(403, "Thiếu quyền owner:manage_own_poi")
    poi = await get_db().poi.find_one({"_id": pid})
    if not poi or poi.get("owner_id") != user["sub"]:
        raise HTTPException(404, "Không tìm thấy quán của bạn")
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(422, "Không có thay đổi")
    sub = {"_id": service.new_id(), "owner_id": user["sub"], "type": "update", "poi_id": pid,
           "data": {**data, "name": data.get("name", poi["name"])}, "status": "pending",
           "admin_note": None, "created_at": service.now()}
    await get_db().poi_submissions.insert_one(sub)
    return ser(sub)


@router.get("/submissions")
async def my_submissions(user: dict = Depends(require_owner)):
    docs = await get_db().poi_submissions.find({"owner_id": user["sub"]}).sort("created_at", -1).to_list(200)
    return {"items": [ser(d) for d in docs]}


@router.get("/notifications")
async def notifications(user: dict = Depends(get_current_user)):
    """Owner xem thông báo kể cả khi chưa verified (để biết kết quả duyệt đơn)."""
    docs = await get_db().owner_notifications.find({"owner_id": user["sub"]}).sort("created_at", -1).to_list(100)
    return {"items": [ser(d) for d in docs], "unread": sum(1 for d in docs if not d["read"])}


@router.get("/notifications/{nid}")
async def notification_detail(nid: str, user: dict = Depends(get_current_user)):
    n = await get_db().owner_notifications.find_one({"_id": nid, "owner_id": user["sub"]})
    if not n:
        raise HTTPException(404, "Không tìm thấy thông báo")
    return ser(n)


@router.post("/notifications/{nid}/read")
async def mark_read(nid: str, user: dict = Depends(get_current_user)):
    res = await get_db().owner_notifications.update_one({"_id": nid, "owner_id": user["sub"]}, {"$set": {"read": True}})
    if not res.matched_count:
        raise HTTPException(404, "Không tìm thấy thông báo")
    return {"ok": True}


@router.get("/analytics")
async def my_analytics(user: dict = Depends(require_owner)):
    """analytics:view_own — lượt nghe thuyết minh các quán của chính owner."""
    if "analytics:view_own" not in user["permissions"]:
        raise HTTPException(403, "Thiếu quyền analytics:view_own")
    db = get_db()
    ids = [d["_id"] async for d in db.poi.find({"owner_id": user["sub"]}, {"_id": 1})]
    pipeline = [{"$match": {"event": "narration_played", "poi_id": {"$in": ids}}},
                {"$group": {"_id": "$poi_id", "plays": {"$sum": 1}}}]
    return {"items": [{"poi_id": d["_id"], "plays": d["plays"]} async for d in db.analytics_events.aggregate(pipeline)]}
