"""
FastAPI application entry point.

Changes from MVP:
- results.json store removed; Postgres (via SQLAlchemy async) is the source of truth.
- CORS locked: no wildcard origin. Add origins via CORS_ORIGINS env var (comma-separated).
- JWT auth required on every endpoint (except /api/auth/login).
- Startup: seeds a default admin user if the users table is empty, and seeds the
  "Make Compliance-Pass" preset if the prompt_presets table is empty.
"""
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# psycopg3 async (used by AsyncPostgresSaver) requires SelectorEventLoop on Windows.
# This MUST be set at module level — before uvicorn creates the event loop.
if sys.platform == "win32":
    import asyncio as _asyncio
    _asyncio.set_event_loop_policy(_asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from db.models import PromptPreset, User, UserRole
from db.session import AsyncSessionLocal
from api.auth import hash_password
from api.routers.auth import router as auth_router
from api.routers.jobs import router as jobs_router
from api.routers.bulk import router as bulk_router
from api.routers.intake import router as intake_router
from api.routers.presets import router as presets_router
from api.routers.chat import router as chat_router
from api.routers.refine import router as refine_router
from api.routers.dashboard import router as dashboard_router
from api.routers.templates import router as templates_router
from api.routers.pay_hints import router as pay_hints_router
from talentsync.prompts import COMPLIANCE_REWRITE_USER_TEMPLATE


# ── Allowed origins (no wildcard in production) ──────────────────────────────
_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
_CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if o.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
    - Apply any pending Alembic migrations (prevents schema-drift 500s)
    - Verify DB connectivity
    - Seed admin user and default preset
    - Initialise AsyncPostgresSaver (LangGraph checkpointer) and stash in app.state
    """
    import sys

    from db.session import engine as _engine, IS_SQLITE

    # ── Schema setup ─────────────────────────────────────────────────────────
    if IS_SQLITE:
        # Alembic migrations are Postgres-specific (JSONB/ENUM DDL). On SQLite,
        # build the schema straight from the ORM metadata instead.
        from db.base import Base
        import db.models  # noqa: F401  (ensures all tables are registered)
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[startup] SQLite schema created via metadata.create_all")
    else:
        # Auto-migrate: runs alembic in a thread so it can call asyncio.run() safely
        # (alembic's env.py uses asyncio.run which can't nest inside the running loop).
        try:
            import concurrent.futures
            from alembic import command as alembic_command
            from alembic.config import Config as AlembicConfig
            alembic_cfg = AlembicConfig(str(ROOT / "alembic.ini"))
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(alembic_command.upgrade, alembic_cfg, "head")
                future.result(timeout=60)
            print("[startup] Alembic migrations: up to date")
        except Exception as exc:
            print(f"[startup] WARNING: Alembic upgrade failed ({exc}). Continuing anyway.")

    # ── DB check + seed ───────────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT 1"))

        admin_email = os.environ.get("ADMIN_EMAIL", "admin@talentsync.local")
        admin_pass = os.environ.get("ADMIN_PASSWORD", "changeme123")

        admin_r = await db.execute(select(User).where(User.email == admin_email))
        admin = admin_r.scalar_one_or_none()
        if admin is None:
            admin = User(
                email=admin_email,
                hashed_password=hash_password(admin_pass),
                role=UserRole.ADMIN,
                tenant_id="default",
            )
            db.add(admin)
            await db.flush()
            print(f"[startup] Seeded admin user: {admin_email}")

        hr_email = os.environ.get("HR_EMAIL", "hr@talentsync.local")
        hr_pass = os.environ.get("HR_PASSWORD", "hr123456")
        hr_r = await db.execute(select(User).where(User.email == hr_email))
        if hr_r.scalar_one_or_none() is None:
            db.add(User(
                email=hr_email,
                hashed_password=hash_password(hr_pass),
                role=UserRole.RECRUITER,
                tenant_id="default",
            ))
            print(f"[startup] Seeded HR recruiter: {hr_email}")

        preset_r = await db.execute(select(PromptPreset).limit(1))
        if preset_r.scalar_one_or_none() is None:
            preset = PromptPreset(
                name="Make Compliance-Pass",
                kind="transform",
                prompt_text=COMPLIANCE_REWRITE_USER_TEMPLATE,
                active=True,
                created_by_admin=admin.id,
            )
            db.add(preset)
            print("[startup] Seeded default preset: Make Compliance-Pass")

        await db.commit()

    # ── LangGraph checkpointer (owned here, never per-request) ───────────────
    _db_url_sync = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://postgres@localhost:5432/talentsync"
    ).replace("postgresql+asyncpg://", "postgresql://")

    saver_cm = None
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        saver_cm = AsyncPostgresSaver.from_conn_string(_db_url_sync)
        app.state.langgraph_saver = await saver_cm.__aenter__()
        await app.state.langgraph_saver.setup()
        print("[startup] LangGraph AsyncPostgresSaver initialised (durable)")
    except Exception as exc:
        print(f"[startup] AsyncPostgresSaver unavailable ({exc}); falling back to MemorySaver")
        from langgraph.checkpoint.memory import MemorySaver
        app.state.langgraph_saver = MemorySaver()
        saver_cm = None  # nothing to close on shutdown

    yield  # ← app runs here

    # ── Shutdown: close saver ─────────────────────────────────────────────────
    if saver_cm is not None:
        try:
            await saver_cm.__aexit__(None, None, None)
        except Exception:
            pass


app = FastAPI(title="TalentSync API", version="2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(bulk_router)
app.include_router(intake_router)
app.include_router(presets_router)
app.include_router(chat_router)
app.include_router(refine_router)
app.include_router(dashboard_router)
app.include_router(templates_router)
app.include_router(pay_hints_router)

from api.routers.bulk_autofix import router as bulk_autofix_router
app.include_router(bulk_autofix_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
