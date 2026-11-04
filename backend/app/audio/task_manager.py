"""AudioTaskManager: sinh bản dịch + audio nền cho POI, có pause/resume/cancel, snapshot Mongo, SSE."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from ..db import get_db

PRIORITY_LANGS = ["en", "vi", "zh", "ja", "ko"]
HEARTBEAT_S = 5
STALE_AFTER = timedelta(minutes=5)
RETENTION = timedelta(days=14)

_tasks: dict[str, dict] = {}
_pause: dict[str, asyncio.Event] = {}
_cancel: set[str] = set()
_running: set[asyncio.Task] = set()


def _now():
    return datetime.now(timezone.utc)


def snapshot(t: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in t.items() if k != "_id"}


async def _save(t: dict) -> None:
    t["updated_at"] = _now()
    await get_db().audio_tasks.update_one({"_id": t["id"]}, {"$set": {**t, "_id": t["id"]}}, upsert=True)


async def recover_after_restart() -> int:
    """Task đang queued/running trước khi restart được đánh dấu failed để admin chạy lại."""
    res = await get_db().audio_tasks.update_many(
        {"status": {"$in": ["queued", "running", "paused"]}},
        {"$set": {"status": "failed", "error": "interrupted by restart", "updated_at": _now()}},
    )
    return res.modified_count


async def ensure_indexes() -> None:
    await get_db().audio_tasks.create_index("updated_at", expireAfterSeconds=int(RETENTION.total_seconds()))


async def load_recent(limit: int = 50) -> None:
    async for d in get_db().audio_tasks.find({}).sort("updated_at", -1).limit(limit):
        t = {k: v for k, v in d.items() if k != "_id"}
        _tasks.setdefault(t["id"], t)


def enqueue(poi_id: str, langs: list[str] | None = None) -> dict:
    langs = langs or PRIORITY_LANGS
    t = {"id": uuid.uuid4().hex[:12], "poi_id": poi_id, "langs": langs, "status": "queued",
         "total": len(langs), "done": 0, "failed_langs": [], "error": None,
         "created_at": _now(), "updated_at": _now()}
    _tasks[t["id"]] = t
    ev = asyncio.Event()
    ev.set()
    _pause[t["id"]] = ev
    job = asyncio.create_task(_run(t))
    _running.add(job)
    job.add_done_callback(_running.discard)
    return t


async def _run(t: dict) -> None:
    from ..localization.service import ensure_localization  # tránh import vòng

    db = get_db()
    tid = t["id"]
    try:
        t["status"] = "running"
        await _save(t)
        poi = await db.poi.find_one({"_id": t["poi_id"]})
        if not poi:
            raise RuntimeError("POI không tồn tại")

        async def one(lang: str):
            await _pause[tid].wait()
            if tid in _cancel:
                return
            try:
                await ensure_localization(poi, lang)
            except Exception as e:  # một ngôn ngữ lỗi không làm hỏng cả task
                t["failed_langs"].append(lang)
                t["error"] = f"{lang}: {e}"[:200]
            t["done"] += 1
            await _save(t)

        # tiếng Anh trước vì gate public cần EN; các ngôn ngữ còn lại chạy song song
        first = [l for l in t["langs"] if l == "en"]
        rest = [l for l in t["langs"] if l != "en"]
        for l in first:
            await one(l)
        await asyncio.gather(*(one(l) for l in rest))

        if tid in _cancel:
            t["status"] = "cancelled"
        else:
            t["status"] = "failed" if "en" in t["failed_langs"] else "completed"
            ok = t["status"] == "completed"
            update = {"audio_status": "ready" if ok else "failed"}
            fresh = await db.poi.find_one({"_id": t["poi_id"]})
            if ok and fresh and fresh.get("activation_requested"):
                update.update({"is_active": True, "activation_requested": False, "updated_at": _now()})
            if fresh:
                await db.poi.update_one({"_id": t["poi_id"]}, {"$set": update})
    except Exception as e:
        t["status"], t["error"] = "failed", str(e)[:200]
        await db.poi.update_one({"_id": t["poi_id"]}, {"$set": {"audio_status": "failed"}})
    finally:
        _cancel.discard(tid)
        await _save(t)


def control(tid: str, action: str) -> dict | None:
    t = _tasks.get(tid)
    if not t:
        return None
    if action == "pause" and t["status"] == "running":
        _pause[tid].clear()
        t["status"] = "paused"
    elif action == "resume" and t["status"] == "paused":
        _pause[tid].set()
        t["status"] = "running"
    elif action == "cancel" and t["status"] in ("queued", "running", "paused"):
        _cancel.add(tid)
        _pause[tid].set()
    return t


def list_tasks() -> list[dict]:
    return sorted((snapshot(t) for t in _tasks.values()), key=lambda x: x["created_at"], reverse=True)


def has_active() -> bool:
    return any(t["status"] in ("queued", "running", "paused") for t in _tasks.values())
