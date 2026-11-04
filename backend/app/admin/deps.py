from fastapi import Depends, HTTPException, Request

from ..security import decode_token


def get_current_user(request: Request) -> dict:
    """Dual-mode: cookie httpOnly (browser) hoặc Bearer header (API/mobile)."""
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    payload = decode_token(token, "access") if token else None
    if not payload:
        raise HTTPException(401, "Chưa đăng nhập hoặc phiên hết hạn")
    return payload


def require_permission(perm: str):
    def dep(user: dict = Depends(get_current_user)) -> dict:
        if perm not in user.get("permissions", []):
            raise HTTPException(403, f"Thiếu quyền {perm}")
        return user
    return dep


def require_owner(user: dict = Depends(get_current_user)) -> dict:
    """Owner gate: không chỉ role poi_owner mà còn phải is_poi_owner_verified."""
    if "owner:access" not in user.get("permissions", []):
        raise HTTPException(403, "Thiếu quyền owner:access")
    if not user.get("is_poi_owner_verified"):
        raise HTTPException(403, "Tài khoản chủ quán chưa được xác minh")
    return user
