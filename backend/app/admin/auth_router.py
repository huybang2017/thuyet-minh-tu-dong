import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from .. import cache
from ..config import settings
from ..db import get_db
from ..security import create_token, decode_token, encrypt_pii, hash_password, verify_password
from . import service
from .deps import get_current_user

router = APIRouter(prefix="/api/v1/admin/auth", tags=["auth"])


class Login(BaseModel):
    username: str
    password: str


class ChangePassword(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=72)


class RegisterOwner(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    display_name: str = Field(min_length=1, max_length=80)
    shop_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(pattern=r"^[0-9+ ]{8,15}$")
    cccd: str = Field(pattern=r"^[0-9]{9,12}$")


async def _claims(user: dict) -> dict:
    return {"sub": user["_id"], "username": user["username"], "role": user["role"],
            "permissions": await service.permissions_for(user["role"]),
            "is_poi_owner_verified": bool(user.get("is_poi_owner_verified"))}


def _set_cookies(resp: Response, access: str, refresh: str) -> None:
    kw = {"httponly": True, "samesite": "lax", "secure": settings.secure_cookies, "path": "/"}
    resp.set_cookie("access_token", access, max_age=settings.access_token_expire_min * 60, **kw)
    resp.set_cookie("refresh_token", refresh, max_age=settings.refresh_token_expire_days * 86400, **kw)


@router.post("/login")
async def login(body: Login, request: Request, response: Response):
    ip = request.client.host if request.client else "anon"
    if await cache.rate_hit(f"login:{ip}:{body.username}", 10, 300):
        raise HTTPException(429, "Đăng nhập sai quá nhiều lần, thử lại sau")
    user = await get_db().fetchone("SELECT * FROM admin_users WHERE username=%s AND deleted_at IS NULL", [body.username])
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    if not user.get("is_active", True):
        raise HTTPException(403, "Tài khoản đã bị khoá")
    claims = await _claims(user)
    _set_cookies(response, create_token(claims, "access"), create_token({"sub": user["_id"]}, "refresh"))
    await service.audit(claims, "login", "auth")
    return {"user": service.public_user(user), "permissions": claims["permissions"]}


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    payload = decode_token(request.cookies.get("refresh_token", ""), "refresh")
    if not payload:
        raise HTTPException(401, "Refresh token không hợp lệ")
    user = await get_db().fetchone("SELECT * FROM admin_users WHERE id=%s AND deleted_at IS NULL", [payload["sub"]])
    if not user or not user.get("is_active", True):
        raise HTTPException(401, "Tài khoản không khả dụng")
    claims = await _claims(user)  # đọc lại DB → role/verified mới nhất
    _set_cookies(response, create_token(claims, "access"), create_token({"sub": user["_id"]}, "refresh"))
    return {"user": service.public_user(user), "permissions": claims["permissions"]}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    u = await get_db().fetchone("SELECT * FROM admin_users WHERE id=%s AND deleted_at IS NULL", [user["sub"]])
    if not u:
        raise HTTPException(401, "Tài khoản không tồn tại")
    return {"user": service.public_user(u), "permissions": user["permissions"]}


@router.post("/change-password")
async def change_password(body: ChangePassword, user: dict = Depends(get_current_user)):
    db = get_db()
    u = await db.fetchone("SELECT * FROM admin_users WHERE id=%s AND deleted_at IS NULL", [user["sub"]])
    if not u or not verify_password(body.old_password, u["password_hash"]):
        raise HTTPException(400, "Mật khẩu cũ không đúng")
    await db.update("admin_users", u["_id"], {"password_hash": hash_password(body.new_password)})
    await service.audit(user, "change_password", "auth")
    return {"ok": True}


@router.post("/register-owner", status_code=201)
async def register_owner(body: RegisterOwner, request: Request):
    db = get_db()
    ip = request.client.host if request.client else "anon"
    if await cache.rate_hit(f"regowner:{ip}", 5, 3600):
        raise HTTPException(429, "Quá nhiều đăng ký từ địa chỉ này")
    if await db.fetchone("SELECT id FROM admin_users WHERE username=%s OR email=%s", [body.username, body.email]):
        raise HTTPException(409, "Tên đăng nhập hoặc email đã tồn tại")
    uid = await db.insert("admin_users", {
        "username": body.username, "email": body.email,
        "password_hash": hash_password(body.password), "role": "poi_owner",
        "display_name": body.display_name, "is_active": True, "is_verified": False,
        "is_poi_owner_verified": False, "created_at": service.now(),
    })
    await db.insert("poi_owner_registrations", {
        "user_id": uid, "shop_name": body.shop_name, "phone": body.phone,
        "cccd_encrypted": encrypt_pii(body.cccd),  # Fernet, không bao giờ trả ra API
        "status": "pending", "admin_note": None, "created_at": service.now(),
    })
    return {"ok": True, "status": "pending"}
