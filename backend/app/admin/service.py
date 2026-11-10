import uuid
from datetime import datetime, timedelta, timezone

from ..config import settings
from ..db import get_db
from ..security import hash_password
from .permissions import ALL_PERMISSIONS, DEFAULT_ROLES


def now():
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


async def ensure_roles() -> None:
    db = get_db()
    for r in DEFAULT_ROLES:
        await db.roles.update_one({"_id": r["name"]}, {"$setOnInsert": {**r, "is_default": True}}, upsert=True)
    # super_admin luôn có đủ 32 quyền kể cả khi danh sách quyền mở rộng
    await db.roles.update_one({"_id": "super_admin"}, {"$set": {"permissions": ALL_PERMISSIONS}})
    await db.admin_users.create_index("username", unique=True)
    # email duy nhất nhưng cho phép nhiều user không có email: partial index thay vì sparse (sparse vẫn tính null)
    try:
        await db.admin_users.drop_index("email_1")
    except Exception:
        pass
    await db.admin_users.create_index("email", unique=True, name="email_unique_partial",
                                      partialFilterExpression={"email": {"$type": "string"}})
    # token đặt lại mật khẩu tự xoá khi hết hạn
    await db.password_resets.create_index("expires_at", expireAfterSeconds=0)


async def ensure_super_admin() -> None:
    db = get_db()
    if await db.admin_users.find_one({"username": settings.superadmin_username}):
        return
    await db.admin_users.insert_one({
        "_id": new_id(), "username": settings.superadmin_username, "email": None,
        "password_hash": hash_password(settings.bootstrap_password), "role": "super_admin",
        "display_name": "Super Admin", "is_active": True, "is_verified": True,
        "is_poi_owner_verified": False, "created_at": now(),
    })


async def permissions_for(role: str) -> list[str]:
    r = await get_db().roles.find_one({"_id": role})
    return list(r["permissions"]) if r else []


async def audit(user: dict | None, action: str, resource: str, detail: str = "") -> None:
    await get_db().audit_logs.insert_one({
        "action": action, "resource": resource, "detail": detail[:300],
        "user_id": user["sub"] if user else None, "username": user.get("username") if user else None,
        "timestamp": now(),
    })


async def notify_owner(owner_id: str, title: str, body: str) -> None:
    await get_db().owner_notifications.insert_one({
        "_id": new_id(), "owner_id": owner_id, "title": title, "body": body,
        "read": False, "created_at": now(),
    })


async def redact_expired_pii() -> int:
    """Sau PII_RETENTION_DAYS ngày CCCD được redact tự động."""
    cutoff = now() - timedelta(days=settings.pii_retention_days)
    res = await get_db().poi_owner_registrations.update_many(
        {"cccd_encrypted": {"$ne": None}, "created_at": {"$lt": cutoff}},
        {"$set": {"cccd_encrypted": None, "pii_redacted_at": now()}},
    )
    return res.modified_count


def public_user(u: dict) -> dict:
    return {"id": u["_id"], "username": u["username"], "email": u.get("email"), "role": u["role"],
            "display_name": u.get("display_name"), "is_active": u.get("is_active", True),
            "is_verified": u.get("is_verified", False),
            "is_poi_owner_verified": u.get("is_poi_owner_verified", False),
            "created_at": u["created_at"].isoformat() if u.get("created_at") else None}


def ser(doc: dict) -> dict:
    out = {}
    for k, v in doc.items():
        if k == "_id":
            out["id"] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out
