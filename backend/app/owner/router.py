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
    reg = await db.fetchone("SELECT * FROM poi_owner_registrations WHERE user_id=%s ORDER BY created_at DESC LIMIT 1", [user["sub"]])
    u = await db.fetchone("SELECT * FROM admin_users WHERE id=%s", [user["sub"]])
    if not reg:
        raise HTTPException(404, "Không có đơn đăng ký")
    return {"status": reg["status"], "admin_note": reg.get("admin_note"), "shop_name": reg["shop_name"],
            "is_poi_owner_verified": bool(u and u.get("is_poi_owner_verified"))}


@router.get("/pois")
async def my_pois(user: dict = Depends(require_owner)):
    docs = await get_db().fetchall("SELECT * FROM poi WHERE owner_id=%s AND deleted_at IS NULL LIMIT 200", [user["sub"]])
    return {"items": [public_poi(d) | {"audio_status": d.get("audio_status")} for d in docs]}


@router.post("/pois", status_code=201)
async def submit_new_poi(body: PoiIn, user: dict = Depends(require_owner)):
    if "owner:submit_poi" not in user["permissions"]:
        raise HTTPException(403, "Thiếu quyền owner:submit_poi")
    sub = {"owner_id": user["sub"], "type": "create", "poi_id": None,
           "data": body.model_dump(exclude_none=True), "status": "pending", "admin_note": None,
           "created_at": service.now()}
    sub["id"] = await get_db().insert("poi_submissions", sub)
    return ser(sub)


@router.put("/pois/{pid}")
async def submit_update(pid: int, body: PoiPatch, user: dict = Depends(require_owner)):
    """Owner chỉ sửa được quán của mình; thay đổi chờ admin duyệt mới lên app."""
    if "owner:manage_own_poi" not in user["permissions"]:
        raise HTTPException(403, "Thiếu quyền owner:manage_own_poi")
    poi = await get_db().fetchone("SELECT * FROM poi WHERE id=%s AND deleted_at IS NULL", [pid])
    if not poi or poi.get("owner_id") != user["sub"]:
        raise HTTPException(404, "Không tìm thấy quán của bạn")
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(422, "Không có thay đổi")
    sub = {"owner_id": user["sub"], "type": "update", "poi_id": pid,
           "data": {**data, "name": data.get("name", poi["name"])}, "status": "pending",
           "admin_note": None, "created_at": service.now()}
    sub["id"] = await get_db().insert("poi_submissions", sub)
    return ser(sub)


@router.get("/submissions")
async def my_submissions(user: dict = Depends(require_owner)):
    docs = await get_db().fetchall("SELECT * FROM poi_submissions WHERE owner_id=%s ORDER BY created_at DESC LIMIT 200", [user["sub"]])
    return {"items": [ser(d) for d in docs]}


@router.get("/notifications")
async def notifications(user: dict = Depends(get_current_user)):
    """Owner xem thông báo kể cả khi chưa verified (để biết kết quả duyệt đơn)."""
    docs = await get_db().fetchall("SELECT * FROM owner_notifications WHERE owner_id=%s ORDER BY created_at DESC LIMIT 100", [user["sub"]])
    return {"items": [ser(d) for d in docs], "unread": sum(1 for d in docs if not d["read"])}


@router.get("/notifications/{nid}")
async def notification_detail(nid: int, user: dict = Depends(get_current_user)):
    n = await get_db().fetchone("SELECT * FROM owner_notifications WHERE id=%s AND owner_id=%s", [nid, user["sub"]])
    if not n:
        raise HTTPException(404, "Không tìm thấy thông báo")
    return ser(n)


@router.post("/notifications/{nid}/read")
async def mark_read(nid: int, user: dict = Depends(get_current_user)):
    if not await get_db().execute("UPDATE owner_notifications SET `read`=1 WHERE id=%s AND owner_id=%s", [nid, user["sub"]]):
        raise HTTPException(404, "Không tìm thấy thông báo")
    return {"ok": True}


@router.get("/analytics")
async def my_analytics(user: dict = Depends(require_owner)):
    """analytics:view_own — lượt nghe thuyết minh các quán của chính owner."""
    if "analytics:view_own" not in user["permissions"]:
        raise HTTPException(403, "Thiếu quyền analytics:view_own")
    db = get_db()
    rows = await db.fetchall(
        "SELECT e.poi_id, COUNT(*) AS plays FROM analytics_events e JOIN poi p ON p.id = e.poi_id "
        "WHERE p.owner_id=%s AND e.event='narration_played' GROUP BY e.poi_id", [user["sub"]])
    return {"items": [{"poi_id": d["poi_id"], "plays": d["plays"]} for d in rows]}
