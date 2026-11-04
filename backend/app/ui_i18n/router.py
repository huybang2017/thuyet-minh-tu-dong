import asyncio
import hashlib
import json
import re
import time
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..db import get_db
from .bundles import EN, NAMESPACE, STATIC

router = APIRouter(prefix="/api/v1/ui-bundles", tags=["ui_i18n"])
SOURCE_HASH = hashlib.md5(json.dumps(EN, sort_keys=True).encode()).hexdigest()[:12]
MAX_FAILED_RATIO = 0.25  # quá ngưỡng này thì coi là dịch thất bại, không cache là ready
RETRY_COOLDOWN_S = 300
_inflight: set[str] = set()
_retry_after: dict[str, float] = {}


async def _gtx_from_en(client: httpx.AsyncClient, text: str, target: str) -> str:
    r = await client.post("https://translate.googleapis.com/translate_a/single",
                          params={"client": "gtx", "sl": "en", "tl": target, "dt": "t"}, data={"q": text})
    r.raise_for_status()
    return "".join(seg[0] for seg in r.json()[0] if seg[0])


async def _mymemory_from_en(client: httpx.AsyncClient, text: str, target: str) -> str:
    r = await client.get("https://api.mymemory.translated.net/get", params={"q": text, "langpair": f"en|{target}"})
    r.raise_for_status()
    data = r.json()
    if data.get("responseStatus") != 200:
        raise RuntimeError("mymemory error")
    return data["responseData"]["translatedText"]


async def translate_bundle(locale: str) -> tuple[dict, int]:
    """Dịch từng chuỗi (Google gtx → MyMemory). Trả (strings, số chuỗi lỗi); chuỗi lỗi giữ tiếng Anh."""
    out, failed = {}, 0
    async with httpx.AsyncClient(timeout=15) as client:
        for k, v in EN.items():
            for prov in (_gtx_from_en, _mymemory_from_en):
                try:
                    out[k] = await prov(client, v, locale)
                    break
                except Exception:
                    continue
            else:
                out[k] = v
                failed += 1
            await asyncio.sleep(0.05)
    return out, failed


async def _translate_and_store(locale: str) -> None:
    key = {"namespace": NAMESPACE, "locale": locale, "source_hash": SOURCE_HASH}
    try:
        strings, failed = await translate_bundle(locale)
        if failed > len(EN) * MAX_FAILED_RATIO:
            _retry_after[locale] = time.monotonic() + RETRY_COOLDOWN_S  # thử lại sau, không lưu bản hỏng
            return
        await get_db().ui_translation_bundles.update_one(
            key, {"$set": {**key, "status": "ready", "strings": strings, "updated_at": datetime.now(timezone.utc)}}, upsert=True)
    finally:
        _inflight.discard(locale)


@router.get("/{locale}")
async def bundle(locale: str, tasks: BackgroundTasks):
    if not re.fullmatch(r"[a-z]{2,3}(-[A-Za-z]{2,4})?", locale):
        raise HTTPException(400, "Locale không hợp lệ")
    base = locale.split("-")[0]
    if base in STATIC:  # 5 ngôn ngữ top-level: bundle tĩnh, luôn ready
        return {"namespace": NAMESPACE, "locale": base, "status": "ready", "source_hash": SOURCE_HASH, "strings": STATIC[base]}
    cached = await get_db().ui_translation_bundles.find_one(
        {"namespace": NAMESPACE, "locale": locale, "source_hash": SOURCE_HASH, "status": "ready"})
    if cached:
        return {"namespace": NAMESPACE, "locale": locale, "status": "ready", "source_hash": SOURCE_HASH, "strings": cached["strings"]}
    if locale not in _inflight and time.monotonic() >= _retry_after.get(locale, 0):
        _inflight.add(locale)
        tasks.add_task(_translate_and_store, locale)
    # tiếng Anh fallback trong lúc server dịch nền (hoặc đang chờ thử lại)
    return {"namespace": NAMESPACE, "locale": locale, "status": "pending", "source_hash": SOURCE_HASH, "strings": EN}
