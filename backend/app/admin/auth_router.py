import logging
import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from .. import cache, mailer
from ..config import settings
from ..db import get_db
from ..security import (create_token, decode_token, encrypt_pii, hash_password, hash_reset_token, issued_before,
                        new_reset_token, verify_password)
from . import service
from .deps import get_current_user

router = APIRouter(prefix="/api/v1/admin/auth", tags=["auth"])
log = logging.getLogger("auth")
FORGOT_MSG = "Nếu tài khoản tồn tại và có email, một liên kết đặt lại mật khẩu đã được gửi."


class Login(BaseModel):
    username: str
    password: str


class ChangePassword(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=72)


class ForgotPassword(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)  # username hoặc email


class ResetPassword(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=8, max_length=72)


class RegisterOwner(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    display_name: str = Field(min_length=1, max_length=80)
    shop_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(pattern=r"^[0-9+ ]{8,15}$")


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
    if issued_before(payload, user.get("password_changed_at")):
        raise HTTPException(401, "Mật khẩu đã thay đổi, vui lòng đăng nhập lại")
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
async def change_password(body: ChangePassword, response: Response, user: dict = Depends(get_current_user)):
    db = get_db()
    u = await db.fetchone("SELECT * FROM admin_users WHERE id=%s AND deleted_at IS NULL", [user["sub"]])
    if not u or not verify_password(body.old_password, u["password_hash"]):
        raise HTTPException(400, "Mật khẩu cũ không đúng")
    await db.update("admin_users", u["id"], {"password_hash": hash_password(body.new_password),
                                              "password_changed_at": service.now()})
    # phiên ở thiết bị khác bị vô hiệu khi refresh; phiên hiện tại được cấp token mới
    claims = await _claims(u)
    _set_cookies(response, create_token(claims, "access"), create_token({"sub": u["id"]}, "refresh"))
    await service.audit(user, "change_password", "auth")
    return {"ok": True}


@router.post("/forgot-password")
async def forgot_password(body: ForgotPassword, request: Request):
    """Luôn trả cùng một thông điệp để không lộ tài khoản nào tồn tại (trừ dev: trả link để thử)."""
    ip = request.client.host if request.client else "anon"
    ident = body.identifier.strip()
    if await cache.rate_hit(f"forgot:{ip}", 5, 900) or await cache.rate_hit(f"forgot:id:{ident.lower()}", 3, 900):
        raise HTTPException(429, "Quá nhiều yêu cầu, thử lại sau")
    db = get_db()
    user = await db.fetchone(
        "SELECT * FROM admin_users WHERE deleted_at IS NULL AND (username=%s OR email=%s) LIMIT 1", [ident, ident.lower()])
    out = {"ok": True, "message": FORGOT_MSG}
    if not user or not user.get("is_active", True):
        return out
    dev = settings.app_env == "dev"
    if not user.get("email") and not dev:
        return out  # không có kênh gửi → không phát hành token
    raw, digest = new_reset_token()
    await db.execute("DELETE FROM password_resets WHERE user_id=%s AND used=0", [user["id"]])
    await db.insert("password_resets", {
        "token_hash": digest, "user_id": user["id"], "used": False, "created_at": service.now(),
        "expires_at": service.now() + timedelta(minutes=settings.password_reset_expire_min)})
    url = f"{settings.public_base_url.rstrip('/')}/reset-password?token={raw}"
    sent = bool(user.get("email")) and await mailer.send(
        user["email"], "Đặt lại mật khẩu — Thuyết Minh Tự Động",
        f"Xin chào {user.get('display_name') or user['username']},\n\n"
        f"Mở liên kết sau để đặt mật khẩu mới (hết hạn sau {settings.password_reset_expire_min} phút):\n{url}\n\n"
        "Nếu bạn không yêu cầu, hãy bỏ qua email này.")
    await service.audit({"sub": user["id"], "username": user["username"]}, "password_reset.request", "auth",
                        "email" if sent else "dev-link")
    if dev and not sent:
        log.warning("[dev] Link đặt lại mật khẩu cho %s: %s", user["username"], url)
        out["dev_reset_url"] = url  # chỉ ở dev, khi chưa cấu hình SMTP
    return out


@router.post("/reset-password")
async def reset_password(body: ResetPassword, request: Request):
    ip = request.client.host if request.client else "anon"
    if await cache.rate_hit(f"reset:{ip}", 10, 900):
        raise HTTPException(429, "Quá nhiều yêu cầu, thử lại sau")
    db = get_db()
    # đánh dấu đã dùng nguyên tử (UPDATE có điều kiện) → token chỉ dùng được một lần
    digest = hash_reset_token(body.token)
    rec = await db.fetchone("SELECT * FROM password_resets WHERE token_hash=%s", [digest])
    if not rec or not await db.execute(
            "UPDATE password_resets SET used=1, used_at=%s WHERE token_hash=%s AND used=0 AND expires_at > %s",
            [service.now(), digest, service.now()]):
        raise HTTPException(400, "Liên kết không hợp lệ hoặc đã hết hạn")
    user = await db.fetchone("SELECT * FROM admin_users WHERE id=%s AND deleted_at IS NULL", [rec["user_id"]])
    if not user or not user.get("is_active", True):
        raise HTTPException(400, "Tài khoản không khả dụng")
    await db.update("admin_users", user["id"], {"password_hash": hash_password(body.new_password),
                                                 "password_changed_at": service.now()})
    await service.audit({"sub": user["id"], "username": user["username"]}, "password_reset.complete", "auth")
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
        "status": "pending", "admin_note": None, "created_at": service.now(),
    })
    return {"ok": True, "status": "pending"}
