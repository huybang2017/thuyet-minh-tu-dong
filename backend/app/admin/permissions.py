PERMISSION_DOMAINS: dict[str, list[str]] = {
    "poi": ["read", "create", "update", "delete", "approve", "toggle"],
    "menu": ["read", "create", "update", "delete"],
    "user": ["read", "create", "update", "delete"],
    "role": ["read", "create", "update", "delete"],
    "analytics": ["view", "export", "view_own"],
    "audit": ["read", "manage"],
    "system": ["config", "logs", "backup"],
    "owner": ["register", "access", "submit_poi", "manage_own_poi"],
    "content": ["moderate", "publish"],
}
ALL_PERMISSIONS = [f"{d}:{a}" for d, acts in PERMISSION_DOMAINS.items() for a in acts]  # 32

DEFAULT_ROLES = [
    {"name": "super_admin", "priority": 0, "permissions": ALL_PERMISSIONS},
    {"name": "admin", "priority": 1, "permissions": (
        [f"poi:{a}" for a in PERMISSION_DOMAINS["poi"]]
        + [f"menu:{a}" for a in PERMISSION_DOMAINS["menu"]]
        + [f"user:{a}" for a in PERMISSION_DOMAINS["user"]]
        + ["analytics:view", "analytics:export", "audit:read", "content:moderate", "content:publish"])},
    {"name": "poi_owner", "priority": 10, "permissions": [
        "poi:read", "owner:access", "owner:submit_poi", "owner:manage_own_poi",
        "menu:read", "menu:create", "menu:update", "analytics:view_own"]},
    {"name": "user", "priority": 100, "permissions": ["poi:read", "menu:read", "owner:register"]},
]
