import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import cache
from .admin import auth_router, router as admin_router
from .admin import service as admin_service
from .ai_advisor import router as ai_router
from .analytics import router as analytics_router
from .audio import router as audio_router
from .audio import task_manager
from .config import settings
from .content import router as content_router
from .content import service as content_service
from .db import close_db, connect_db, get_db
from .localization import router as localization_router
from .owner import router as owner_router
from .runtime_observability import router as observability_router
from .ui_i18n import router as ui_i18n_router

STATIC_DIR = Path(__file__).parent / "static"


async def _maintenance_loop():
    while True:
        try:
            await admin_service.redact_expired_pii()
        except Exception:
            pass
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Tầng 1: security guard — sai cấu hình thì fail-fast
    settings.assert_secure()
    # Tầng 2: database
    await connect_db()
    # Tầng 3: seeding + runtime prep
    await admin_service.ensure_roles()
    await admin_service.ensure_super_admin()
    await content_service.seed_if_empty()
    # Tầng 4: recovery + workers
    await task_manager.ensure_indexes()
    await task_manager.recover_after_restart()
    await task_manager.load_recent()
    maintenance = asyncio.create_task(_maintenance_loop())
    yield
    maintenance.cancel()
    await close_db()


app = FastAPI(title="Thuyết Minh Tự Động", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["ETag", "Retry-After", "X-Cache", "X-Static-Url"],
)
for r in (content_router, audio_router, localization_router, auth_router, admin_router, owner_router,
          ai_router, analytics_router, observability_router, ui_i18n_router):
    app.include_router(r.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/ready")
async def ready():
    await get_db().command("ping")
    return {"status": "ready", "redis": await cache.redis_ok(), "routers": 9}
