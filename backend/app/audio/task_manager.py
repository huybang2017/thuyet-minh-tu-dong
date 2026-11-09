"""AudioTaskManager: sinh bản dịch + audio nền cho POI, có pause/resume/cancel, snapshot MySQL, SSE."""
import asyncio
from datetime import datetime, timedelta, timezone

from ..db import get_db

PRIORITY_LANGS = ["en", "vi", "zh", "ja", "ko"]
HEARTBEAT_S = 5
STALE_AFTER = timedelta(minutes=5)
RETENTION = timedelta(days=14)

_tasks: dict[int, dict] = {}
_pause: dict[int, asyncio.Event] = {}
_cancel: set[int] = set()
_last_id = 0  # id task số tăng dần (task chạy trong tiến trình; khởi tạo từ MAX(id) trong DB khi khởi động)
_running: set[asyncio.Task] = set()


def _now():
    return datetime.now(timezone.utc)


def snapshot(t: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in t.items() if k != "_id"}


async def _save(t: dict) -> None:
    t["updated_at"] = _now()
    row = {k: t[k] for k in ("id", "poi_id", "langs", "status", "total", "done", "failed_langs", "error", "created_at", "updated_at")}
    await get_db().upsert("audio_tasks", row, [c for c in row if c not in ("id", "created_at")])


async def recover_after_restart() -> int:
    """Task đang queued/running trước khi restart được đánh dấu failed để admin chạy lại."""
    return await get_db().execute(
        "UPDATE audio_tasks SET status='failed', error='interrupted by restart', updated_at=%s "
        "WHERE status IN ('queued','running','paused')", [_now()])


async def ensure_indexes() -> None:
    """MySQL không có TTL index: dọn task cũ hơn RETENTION khi khởi động."""
    await get_db().execute("DELETE FROM audio_tasks WHERE updated_at < %s", [_now() - RETENTION])


async def load_recent(limit: int = 50) -> None:
    global _last_id
    _last_id = max(_last_id, int(await get_db().scalar("SELECT COALESCE(MAX(id), 0) FROM audio_tasks") or 0))
    for d in await get_db().fetchall("SELECT * FROM audio_tasks ORDER BY updated_at DESC LIMIT %s", [limit]):
        t = {k: v for k, v in d.items() if k != "_id"}
        _tasks.setdefault(t["id"], t)


def enqueue(poi_id: int, langs: list[str] | None = None) -> dict:
    global _last_id
    langs = langs or PRIORITY_LANGS
    _last_id += 1
    t = {"id": _last_id, "poi_id": poi_id, "langs": langs, "status": "queued",
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
        poi = await db.fetchone("SELECT * FROM poi WHERE id=%s AND deleted_at IS NULL", [t["poi_id"]])
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
            fresh = await db.fetchone("SELECT * FROM poi WHERE id=%s AND deleted_at IS NULL", [t["poi_id"]])
            if ok and fresh and fresh.get("activation_requested"):
                update.update({"is_active": True, "activation_requested": False, "updated_at": _now()})
            if fresh:
                await db.update("poi", t["poi_id"], update)
    except Exception as e:
        t["status"], t["error"] = "failed", str(e)[:200]
        await db.update("poi", t["poi_id"], {"audio_status": "failed"})
    finally:
        _cancel.discard(tid)
        await _save(t)


def control(tid: int, action: str) -> dict | None:
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
