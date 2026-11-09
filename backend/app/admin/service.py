from datetime import datetime, timedelta, timezone

from ..config import settings
from ..db import get_db
from ..security import hash_password
from .permissions import ALL_PERMISSIONS, DEFAULT_ROLES


def now():
    return datetime.now(timezone.utc)


async def ensure_roles() -> None:
    db = get_db()
    for r in DEFAULT_ROLES:
        await db.execute("INSERT IGNORE INTO roles (name, priority, permissions, is_default) VALUES (%s,%s,%s,1)",
                         [r["name"], r.get("priority", 50), r["permissions"]])
    # super_admin luôn có đủ quyền kể cả khi danh sách quyền mở rộng
    await db.execute("UPDATE roles SET permissions=%s WHERE name='super_admin'", [ALL_PERMISSIONS])


async def ensure_super_admin() -> None:
    db = get_db()
    if await db.fetchone("SELECT id FROM admin_users WHERE username=%s", [settings.superadmin_username]):
        return
    await db.insert("admin_users", {
        "username": settings.superadmin_username, "email": None,
        "password_hash": hash_password(settings.bootstrap_password), "role": "super_admin",
        "display_name": "Super Admin", "is_active": True, "is_verified": True,
        "is_poi_owner_verified": False, "created_at": now(),
    })


async def permissions_for(role: str) -> list[str]:
    r = await get_db().fetchone("SELECT permissions FROM roles WHERE name=%s AND deleted_at IS NULL", [role])
    return list(r["permissions"]) if r else []


async def audit(user: dict | None, action: str, resource: str, detail: str = "") -> None:
    await get_db().insert("audit_logs", {
        "action": action, "resource": str(resource), "detail": detail[:300],
        "user_id": user["sub"] if user else None, "username": user.get("username") if user else None,
        "timestamp": now(),
    })


async def notify_owner(owner_id: int, title: str, body: str) -> None:
    await get_db().insert("owner_notifications", {
        "owner_id": owner_id, "title": title, "body": body,
        "read": False, "created_at": now(),
    })


async def redact_expired_pii() -> int:
    """Sau PII_RETENTION_DAYS ngày CCCD được redact tự động."""
    cutoff = now() - timedelta(days=settings.pii_retention_days)
    return await get_db().execute(
        "UPDATE poi_owner_registrations SET cccd_encrypted=NULL, pii_redacted_at=%s "
        "WHERE cccd_encrypted IS NOT NULL AND created_at < %s", [now(), cutoff])


def public_user(u: dict) -> dict:
    return {"id": u.get("_id", u.get("id")), "username": u["username"], "email": u.get("email"), "role": u["role"],
            "display_name": u.get("display_name"), "is_active": u.get("is_active", True),
            "is_verified": u.get("is_verified", False),
            "is_poi_owner_verified": u.get("is_poi_owner_verified", False),
            "created_at": u["created_at"].isoformat() if u.get("created_at") else None}


def ser(doc: dict) -> dict:
    out = {}
    for k, v in doc.items():
        if k == "_id":
            out["id"] = v
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out
