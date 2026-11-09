import base64
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from .config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_token(payload: dict, kind: str) -> str:
    if kind == "access":
        ttl, secret = timedelta(minutes=settings.access_token_expire_min), settings.jwt_secret
    else:
        ttl, secret = timedelta(days=settings.refresh_token_expire_days), settings.refresh_token_secret
    data = {**payload, "type": kind, "exp": datetime.now(timezone.utc) + ttl}
    if "sub" in data:
        data["sub"] = str(data["sub"])  # claim `sub` phải là chuỗi; id người dùng là số
    return jwt.encode(data, secret, algorithm="HS256")


def decode_token(token: str, kind: str) -> dict | None:
    secret = settings.jwt_secret if kind == "access" else settings.refresh_token_secret
    try:
        data = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if data.get("type") != kind:
        return None
    try:
        data["sub"] = int(data["sub"])
    except (KeyError, TypeError, ValueError):
        return None
    return data


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
    return Fernet(key)


def encrypt_pii(value: str) -> str:
    return "v1:" + _fernet().encrypt(value.encode()).decode()


def decrypt_pii(value: str | None) -> str | None:
    """Trả None nếu lỗi — không bao giờ lộ dữ liệu hỏng."""
    if not value or not value.startswith("v1:"):
        return None
    try:
        return _fernet().decrypt(value[3:].encode()).decode()
    except (InvalidToken, ValueError):
        return None
