"""Upload ảnh quán. Nhận body nhị phân (Content-Type: image/*), không cần multipart.

Ảnh được nhận diện bằng magic bytes (không tin Content-Type/đuôi file), đặt tên theo sha256
nên upload trùng không tạo file mới. Chỉ JPEG/PNG/WebP — không nhận SVG (có thể chứa script).
"""
import hashlib
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import cache
from ..admin import service
from ..admin.deps import get_current_user
from ..config import settings
from ..db import get_db

router = APIRouter(prefix="/api/v1/media", tags=["media"])
IMAGE_DIR = Path(__file__).resolve().parent.parent / "static" / "images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_URL_RE = re.compile(r"^/static/images/[a-f0-9]{24}\.(jpg|png|webp)$")


def sniff(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def can_upload(user: dict) -> bool:
    p = user.get("permissions", [])
    return "poi:update" in p or "poi:create" in p or ("owner:access" in p and user.get("is_poi_owner_verified"))


@router.post("/images", status_code=201)
async def upload_image(request: Request, user: dict = Depends(get_current_user)):
    if not can_upload(user):
        raise HTTPException(403, "Không có quyền tải ảnh")
    if await cache.rate_hit(f"upload:{user['sub']}", 60, 3600):
        raise HTTPException(429, "Tải ảnh quá nhiều, thử lại sau")
    limit = settings.max_image_bytes
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(413, f"Ảnh vượt quá {limit // 1024} KB")
    buf = bytearray()
    async for chunk in request.stream():
        buf.extend(chunk)
        if len(buf) > limit:
            raise HTTPException(413, f"Ảnh vượt quá {limit // 1024} KB")
    if not buf:
        raise HTTPException(422, "Không có dữ liệu ảnh")
    ext = sniff(bytes(buf[:16]))
    if not ext:
        raise HTTPException(415, "Chỉ nhận ảnh JPEG, PNG hoặc WebP")
    name = f"{hashlib.sha256(buf).hexdigest()[:24]}.{ext}"
    path = IMAGE_DIR / name
    if not path.exists():
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(buf)
        tmp.replace(path)
    await get_db().execute(
        "INSERT INTO media (name, uploaded_by, size, created_at) VALUES (%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE uploaded_by=VALUES(uploaded_by), size=VALUES(size), created_at=VALUES(created_at)",
        [name, user["sub"], len(buf), service.now()])
    return {"url": f"/static/images/{name}", "size": len(buf)}
