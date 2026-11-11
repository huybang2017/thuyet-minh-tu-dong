import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from ..audio import task_manager
from ..content import ops
from ..content.service import public_poi
from ..db import get_db
from ..media.router import IMAGE_URL_RE
from ..security import hash_password
from . import service
from .deps import require_permission
from .permissions import ALL_PERMISSIONS, PERMISSION_DOMAINS

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
ser = service.ser


# ---------- models ----------
class _Images(BaseModel):
    images: list[str] | None = None

    @field_validator("images")
    @classmethod
    def _uploaded_only(cls, v):
        """Chỉ nhận ảnh đã tải lên qua /api/v1/media/images (không nhúng URL bên ngoài)."""
        if v is not None:
            if len(v) > ops.MAX_POI_IMAGES:
                raise ValueError(f"Tối đa {ops.MAX_POI_IMAGES} ảnh")
            bad = [u for u in v if not IMAGE_URL_RE.match(u)]
            if bad:
                raise ValueError(f"URL ảnh không hợp lệ: {bad[:3]}")
            v = list(dict.fromkeys(v))  # bỏ trùng, giữ thứ tự
        return v


class PoiIn(_Images):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=3000)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    trigger_radius: int | None = Field(default=None, ge=5, le=500)
    audio_priority: int | None = Field(default=None, ge=1, le=9)
    address: str | None = Field(default=None, max_length=200)
    area: str | None = Field(default=None, max_length=60)


class PoiPatch(_Images):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=3000)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    trigger_radius: int | None = Field(default=None, ge=5, le=500)
    audio_priority: int | None = Field(default=None, ge=1, le=9)
    address: str | None = Field(default=None, max_length=200)
    area: str | None = Field(default=None, max_length=60)


class Toggle(BaseModel):
    active: bool


class MenuIn(BaseModel):
    poi_id: int
    name: str = Field(min_length=1, max_length=120)
    price: float = Field(ge=0, le=100_000_000)
    description: str | None = Field(default=None, max_length=300)


class MenuPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    price: float | None = Field(default=None, ge=0, le=100_000_000)
    description: str | None = Field(default=None, max_length=300)


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=72)
    role: str
    email: str | None = None
    display_name: str | None = None


class UserPatch(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    display_name: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)


class RoleIn(BaseModel):
    name: str = Field(min_length=2, max_length=32, pattern=r"^[a-z0-9_]+$")
    priority: int = Field(default=50, ge=2, le=1000)
    permissions: list[str]


class RolePatch(BaseModel):
    priority: int | None = Field(default=None, ge=2, le=1000)
    permissions: list[str] | None = None


class Review(BaseModel):
    admin_note: str | None = Field(default=None, max_length=500)


def _check_perms(perms: list[str]):
    bad = [p for p in perms if p not in ALL_PERMISSIONS]
    if bad:
        raise HTTPException(422, f"Quyền không hợp lệ: {bad}")


# ---------- POI ----------
@router.get("/pois")
async def list_pois(_=Depends(require_permission("poi:read"))):
    docs = await get_db().fetchall("SELECT * FROM poi WHERE deleted_at IS NULL ORDER BY updated_at DESC LIMIT 1000")
    return {"items": [{**public_poi(d), "owner_id": d.get("owner_id"), "activation_requested": d.get("activation_requested", False)} for d in docs]}


@router.post("/pois", status_code=201)
async def create_poi(body: PoiIn, user=Depends(require_permission("poi:create"))):
    doc = await ops.create_poi(body.model_dump(exclude_none=True))
    await service.audit(user, "poi.create", doc["_id"], doc["name"])
    return public_poi(doc)


@router.put("/pois/{pid}")
async def update_poi(pid: int, body: PoiPatch, user=Depends(require_permission("poi:update"))):
    doc = await ops.update_poi(pid, body.model_dump(exclude_none=True))
    if not doc:
        raise HTTPException(404, "POI không tồn tại")
    await service.audit(user, "poi.update", pid)
    return public_poi(doc)


@router.delete("/pois/{pid}")
async def delete_poi(pid: int, user=Depends(require_permission("poi:delete"))):
    if not await ops.delete_poi(pid):
        raise HTTPException(404, "POI không tồn tại")
    await service.audit(user, "poi.delete", pid)
    return {"ok": True}


@router.post("/pois/{pid}/toggle")
async def toggle_poi(pid: int, body: Toggle, user=Depends(require_permission("poi:toggle"))):
    doc = await ops.toggle_poi(pid, body.active)
    if not doc:
        raise HTTPException(404, "POI không tồn tại")
    await service.audit(user, "poi.toggle", pid, str(body.active))
    return public_poi(doc) | {"activation_requested": doc.get("activation_requested", False)}


@router.post("/pois/{pid}/regenerate-audio", status_code=202)
async def regenerate(pid: int, user=Depends(require_permission("poi:update"))):
    db = get_db()
    if not await db.fetchone("SELECT id FROM poi WHERE id=%s AND deleted_at IS NULL", [pid]):
        raise HTTPException(404, "POI không tồn tại")
    await db.execute("DELETE FROM poi_localizations WHERE poi_id=%s", [pid])
    await db.update("poi", pid, {"audio_status": "processing"})
    t = task_manager.enqueue(pid)
    await service.audit(user, "poi.regenerate_audio", pid)
    return task_manager.snapshot(t)


# ---------- Menu ----------
@router.get("/menus")
async def list_menus(poi_id: int | None = None, _=Depends(require_permission("menu:read"))):
    db = get_db()
    rows = (await db.fetchall("SELECT * FROM menu_items WHERE poi_id=%s AND deleted_at IS NULL LIMIT 500", [poi_id]) if poi_id
            else await db.fetchall("SELECT * FROM menu_items WHERE deleted_at IS NULL LIMIT 500"))
    return {"items": [ser(d) for d in rows]}


@router.post("/menus", status_code=201)
async def create_menu(body: MenuIn, user=Depends(require_permission("menu:create"))):
    if not await get_db().fetchone("SELECT id FROM poi WHERE id=%s AND deleted_at IS NULL", [body.poi_id]):
        raise HTTPException(404, "POI không tồn tại")
    doc = {**body.model_dump(), "created_at": service.now()}
    doc["id"] = await get_db().insert("menu_items", doc)
    await service.audit(user, "menu.create", doc["id"], body.name)
    return ser(doc)


@router.put("/menus/{mid}")
async def update_menu(mid: int, body: MenuPatch, user=Depends(require_permission("menu:update"))):
    upd = body.model_dump(exclude_none=True)
    if not await get_db().fetchone("SELECT id FROM menu_items WHERE id=%s AND deleted_at IS NULL", [mid]):
        raise HTTPException(404, "Món không tồn tại")
    await get_db().update("menu_items", mid, upd)
    await service.audit(user, "menu.update", mid)
    return ser(await get_db().fetchone("SELECT * FROM menu_items WHERE id=%s", [mid]))


@router.delete("/menus/{mid}")
async def delete_menu(mid: int, user=Depends(require_permission("menu:delete"))):
    if not await get_db().execute("UPDATE menu_items SET deleted_at=%s WHERE id=%s AND deleted_at IS NULL",
                                  [service.now(), mid]):
        raise HTTPException(404, "Món không tồn tại")
    await service.audit(user, "menu.delete", mid)
    return {"ok": True}


# ---------- Users ----------
@router.get("/users")
async def list_users(_=Depends(require_permission("user:read"))):
    return {"items": [service.public_user(u) for u in await get_db().fetchall("SELECT * FROM admin_users WHERE deleted_at IS NULL LIMIT 1000")]}


@router.post("/users", status_code=201)
async def create_user(body: UserIn, user=Depends(require_permission("user:create"))):
    db = get_db()
    role = await db.fetchone("SELECT name FROM roles WHERE name=%s AND deleted_at IS NULL", [body.role])
    if not role:
        raise HTTPException(422, "Role không tồn tại")
    if role["name"] == "super_admin" and "super_admin" != user["role"]:
        raise HTTPException(403, "Chỉ super_admin mới tạo được super_admin")
    if await db.fetchone("SELECT id FROM admin_users WHERE username=%s", [body.username]):
        raise HTTPException(409, "Tên đăng nhập đã tồn tại")
    doc = {"username": body.username, "email": body.email or None,
           "password_hash": hash_password(body.password), "role": body.role,
           "display_name": body.display_name, "is_active": True, "is_verified": True,
           "is_poi_owner_verified": body.role == "poi_owner", "created_at": service.now()}
    doc["id"] = await db.insert("admin_users", doc)
    await service.audit(user, "user.create", doc["id"], body.username)
    return service.public_user(doc)


@router.put("/users/{uid}")
async def update_user(uid: int, body: UserPatch, user=Depends(require_permission("user:update"))):
    db = get_db()
    target = await db.fetchone("SELECT * FROM admin_users WHERE id=%s AND deleted_at IS NULL", [uid])
    if not target:
        raise HTTPException(404, "User không tồn tại")
    if (target["role"] == "super_admin" or body.role == "super_admin") and user["role"] != "super_admin":
        raise HTTPException(403, "Chỉ super_admin mới sửa được super_admin")
    upd = {}
    if body.role is not None:
        if not await db.fetchone("SELECT name FROM roles WHERE name=%s AND deleted_at IS NULL", [body.role]):
            raise HTTPException(422, "Role không tồn tại")
        upd["role"] = body.role
    if body.is_active is not None:
        if uid == user["sub"] and not body.is_active:
            raise HTTPException(400, "Không thể tự khoá chính mình")
        upd["is_active"] = body.is_active
    if body.display_name is not None:
        upd["display_name"] = body.display_name
    if body.password:
        upd["password_hash"] = hash_password(body.password)
        upd["password_changed_at"] = service.now()
    if upd:
        await db.update("admin_users", uid, upd)
    await service.audit(user, "user.update", uid, ",".join("password" if k == "password_hash" else k for k in upd if k != "password_changed_at"))
    return service.public_user(await db.fetchone("SELECT * FROM admin_users WHERE id=%s", [uid]))


@router.delete("/users/{uid}")
async def delete_user(uid: int, user=Depends(require_permission("user:delete"))):
    db = get_db()
    target = await db.fetchone("SELECT * FROM admin_users WHERE id=%s AND deleted_at IS NULL", [uid])
    if not target:
        raise HTTPException(404, "User không tồn tại")
    if uid == user["sub"]:
        raise HTTPException(400, "Không thể tự xoá chính mình")
    if target["role"] == "super_admin" and user["role"] != "super_admin":
        raise HTTPException(403, "Chỉ super_admin mới xoá được super_admin")
    await db.execute("UPDATE admin_users SET deleted_at=%s, is_active=0 WHERE id=%s", [service.now(), uid])
    # dữ liệu cá nhân gắn với tài khoản (đơn đăng ký, thông báo, token đặt lại) xoá theo
    await db.execute("DELETE FROM poi_owner_registrations WHERE user_id=%s", [uid])
    await db.execute("DELETE FROM owner_notifications WHERE owner_id=%s", [uid])
    await db.execute("DELETE FROM password_resets WHERE user_id=%s", [uid])
    await service.audit(user, "user.delete", uid, target["username"])
    return {"ok": True}


# ---------- Roles ----------
@router.get("/permissions")
async def permissions(_=Depends(require_permission("role:read"))):
    return {"domains": PERMISSION_DOMAINS, "all": ALL_PERMISSIONS}


@router.get("/roles")
async def list_roles(_=Depends(require_permission("role:read"))):
    return {"items": [ser(r) for r in await get_db().fetchall("SELECT * FROM roles WHERE deleted_at IS NULL ORDER BY priority LIMIT 100")]}


@router.post("/roles", status_code=201)
async def create_role(body: RoleIn, user=Depends(require_permission("role:create"))):
    _check_perms(body.permissions)
    old = await get_db().fetchone("SELECT name, deleted_at FROM roles WHERE name=%s", [body.name])
    if old and not old["deleted_at"]:
        raise HTTPException(409, "Role đã tồn tại")
    if old:  # tên role (khoá chính) đang bị xoá mềm → dùng lại bản ghi đó
        await get_db().update("roles", body.name, {"priority": body.priority, "permissions": body.permissions,
                                                   "is_default": False, "deleted_at": None}, key="name")
    else:
        await get_db().insert("roles", {"name": body.name, "priority": body.priority,
                                        "permissions": body.permissions, "is_default": False})
    await service.audit(user, "role.create", body.name)
    return {"name": body.name, "priority": body.priority, "permissions": body.permissions}


@router.put("/roles/{name}")
async def update_role(name: str, body: RolePatch, user=Depends(require_permission("role:update"))):
    if name == "super_admin":
        raise HTTPException(400, "Không sửa được super_admin")
    upd = body.model_dump(exclude_none=True)
    if "permissions" in upd:
        _check_perms(upd["permissions"])
    if not await get_db().fetchone("SELECT name FROM roles WHERE name=%s AND deleted_at IS NULL", [name]):
        raise HTTPException(404, "Role không tồn tại")
    await get_db().update("roles", name, upd, key="name")
    await service.audit(user, "role.update", name)
    return ser(await get_db().fetchone("SELECT * FROM roles WHERE name=%s", [name]))


@router.delete("/roles/{name}")
async def delete_role(name: str, user=Depends(require_permission("role:delete"))):
    db = get_db()
    r = await db.fetchone("SELECT * FROM roles WHERE name=%s AND deleted_at IS NULL", [name])
    if not r:
        raise HTTPException(404, "Role không tồn tại")
    if r.get("is_default"):
        raise HTTPException(400, "Không xoá được role mặc định")
    if await db.fetchone("SELECT id FROM admin_users WHERE role=%s AND deleted_at IS NULL LIMIT 1", [name]):
        raise HTTPException(409, "Role đang được gán cho user")
    await db.execute("UPDATE roles SET deleted_at=%s WHERE name=%s", [service.now(), name])
    await service.audit(user, "role.delete", name)
    return {"ok": True}


# ---------- Owner registrations ----------
@router.get("/registrations")
async def list_registrations(status: str | None = None, _=Depends(require_permission("poi:approve"))):
    db = get_db()
    sql = ("SELECT r.*, u.username FROM poi_owner_registrations r LEFT JOIN admin_users u ON u.id=r.user_id "
           + ("WHERE r.status=%s " if status else "") + "ORDER BY r.created_at DESC LIMIT 500")
    out = []
    for r in await db.fetchall(sql, [status] if status else []):
        out.append({"id": r["id"], "user_id": r["user_id"], "username": r["username"],
                    "shop_name": r["shop_name"], "phone": r["phone"], "status": r["status"],
                    "admin_note": r.get("admin_note"),
                    "created_at": r["created_at"].isoformat()})
    return {"items": out}


async def _review_registration(rid: int, approve: bool, body: Review, user: dict):
    db = get_db()
    reg = await db.fetchone("SELECT * FROM poi_owner_registrations WHERE id=%s", [rid])
    if not reg:
        raise HTTPException(404, "Đơn không tồn tại")
    if reg["status"] != "pending":
        raise HTTPException(409, "Đơn đã được xử lý")
    status = "approved" if approve else "rejected"
    await db.update("poi_owner_registrations", rid, {
        "status": status, "admin_note": body.admin_note, "reviewed_by": user["sub"], "reviewed_at": service.now()})
    if approve:
        await db.update("admin_users", reg["user_id"], {"is_verified": True, "is_poi_owner_verified": True})
    await service.notify_owner(
        reg["user_id"], "Đơn đăng ký chủ quán " + ("đã được duyệt" if approve else "bị từ chối"),
        body.admin_note or ("Chào mừng bạn! Hãy đăng nhập lại để vào cổng chủ quán." if approve else "Vui lòng liên hệ quản trị viên."))
    await service.audit(user, f"registration.{status}", rid)
    return {"ok": True, "status": status}


@router.post("/registrations/{rid}/approve")
async def approve_registration(rid: int, body: Review = Review(), user=Depends(require_permission("poi:approve"))):
    return await _review_registration(rid, True, body, user)


@router.post("/registrations/{rid}/reject")
async def reject_registration(rid: int, body: Review = Review(), user=Depends(require_permission("poi:approve"))):
    return await _review_registration(rid, False, body, user)


# ---------- Owner submissions ----------
@router.get("/submissions")
async def list_submissions(status: str | None = None, _=Depends(require_permission("poi:approve"))):
    db = get_db()
    rows = (await db.fetchall("SELECT * FROM poi_submissions WHERE status=%s ORDER BY created_at DESC LIMIT 500", [status]) if status
            else await db.fetchall("SELECT * FROM poi_submissions ORDER BY created_at DESC LIMIT 500"))
    return {"items": [ser(d) for d in rows]}


async def _review_submission(sid: int, approve: bool, body: Review, user: dict):
    db = get_db()
    sub = await db.fetchone("SELECT * FROM poi_submissions WHERE id=%s", [sid])
    if not sub:
        raise HTTPException(404, "Submission không tồn tại")
    if sub["status"] != "pending":
        raise HTTPException(409, "Submission đã được xử lý")
    if approve:
        if sub["type"] == "create":
            poi = await ops.create_poi(sub["data"], owner_id=sub["owner_id"])
            await db.update("poi_submissions", sid, {"poi_id": poi["id"]})
        else:
            if not await ops.update_poi(sub["poi_id"], sub["data"]):
                raise HTTPException(409, "POI gốc không còn tồn tại")
    status = "approved" if approve else "rejected"
    await db.update("poi_submissions", sid, {
        "status": status, "admin_note": body.admin_note, "reviewed_by": user["sub"], "reviewed_at": service.now()})
    await service.notify_owner(sub["owner_id"], f"Bài gửi \"{sub['data'].get('name', sub.get('poi_id'))}\" " + ("đã được duyệt" if approve else "bị từ chối"),
                               body.admin_note or "")
    await service.audit(user, f"submission.{status}", sid)
    return {"ok": True, "status": status}


@router.post("/submissions/{sid}/approve")
async def approve_submission(sid: int, body: Review = Review(), user=Depends(require_permission("poi:approve"))):
    return await _review_submission(sid, True, body, user)


@router.post("/submissions/{sid}/reject")
async def reject_submission(sid: int, body: Review = Review(), user=Depends(require_permission("poi:approve"))):
    return await _review_submission(sid, False, body, user)


# ---------- Audit ----------
@router.get("/audit-logs")
async def audit_logs(limit: int = Query(100, le=500), _=Depends(require_permission("audit:read"))):
    docs = await get_db().fetchall("SELECT * FROM audit_logs ORDER BY `timestamp` DESC LIMIT %s", [limit])
    return {"items": [ser(d) for d in docs]}


# ---------- Audio tasks ----------
@router.get("/audio-tasks")
async def audio_tasks(_=Depends(require_permission("poi:read"))):
    return {"items": task_manager.list_tasks()}


@router.post("/audio-tasks/{tid}/{action}")
async def audio_task_control(tid: int, action: str, user=Depends(require_permission("poi:update"))):
    if action not in ("pause", "resume", "cancel"):
        raise HTTPException(400, "Hành động không hợp lệ")
    t = task_manager.control(tid, action)
    if not t:
        raise HTTPException(404, "Task không tồn tại")
    await service.audit(user, f"audio_task.{action}", tid)
    return task_manager.snapshot(t)


@router.get("/audio-tasks-stream")
async def audio_tasks_stream(_=Depends(require_permission("poi:read"))):
    """SSE: đẩy snapshot task mỗi giây trong khi có task hoạt động (+ vài nhịp cuối)."""
    async def gen():
        idle = 0
        while idle < 4:
            yield f"data: {json.dumps(task_manager.list_tasks())}\n\n"
            idle = 0 if task_manager.has_active() else idle + 1
            await asyncio.sleep(1)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
