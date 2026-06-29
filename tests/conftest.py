"""
Pytest fixtures for TalentSync Phase 0 tests.

Uses a real test_talentsync PostgreSQL database (not SQLite, not mocks).
TALENTSYNC_STUB=1 prevents any LLM calls during tests.

Isolation strategy:
- Schema is dropped and recreated ONCE per session (apply_migrations).
- Each test uses the app's own session (HTTP via AsyncClient) — those commits persist.
- The direct `db` fixture provides a test-managed session that ROLLS BACK after each test.
- User fixtures commit once per fixture invocation; emails are unique per fixture instance
  using a counter so tests that create multiple user fixtures don't collide.
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

# psycopg3 async (used by LangGraph AsyncPostgresSaver) requires SelectorEventLoop on Windows.
# Set the policy at module level — before pytest-asyncio creates its session event loop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Set env vars BEFORE any project imports that read them
os.environ.setdefault("TALENTSYNC_STUB", "1")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres@localhost:5432/test_talentsync")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only-not-production")
os.environ.setdefault("ADMIN_EMAIL", "seed_admin@test.local")
os.environ.setdefault("ADMIN_PASSWORD", "testpass123")

from alembic import command
from alembic.config import Config

from db.models import PromptPreset, User, UserRole
from db.session import AsyncSessionLocal
from api.auth import hash_password

_TEST_DB_URL = os.environ["DATABASE_URL"]
_COUNTER = 0


def _unique_email(prefix: str) -> str:
    global _COUNTER
    _COUNTER += 1
    return f"{prefix}_{_COUNTER}@test.local"


# ── Session-level setup ───────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def apply_migrations():
    """Drop and recreate the test schema, then run Alembic migrations. Runs once."""
    async def _reset():
        eng = create_async_engine(_TEST_DB_URL, echo=False)
        async with eng.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
        await eng.dispose()

    asyncio.run(_reset())

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", _TEST_DB_URL)
    command.upgrade(cfg, "head")
    yield


@pytest_asyncio.fixture(scope="session", autouse=True)
async def seed_test_data(apply_migrations):
    """
    Seed the seed-admin user and the default 'Make Compliance-Pass' preset
    exactly once before all tests.

    This ensures preset-dependent tests work regardless of whether the FastAPI
    lifespan has run yet for a given client fixture instance.
    """
    from talentsync.prompts import COMPLIANCE_REWRITE_USER_TEMPLATE

    admin_email = os.environ.get("ADMIN_EMAIL", "seed_admin@test.local")
    admin_pass = os.environ.get("ADMIN_PASSWORD", "testpass123")

    async with AsyncSessionLocal() as session:
        # Seed the seed-admin user if absent
        admin_r = await session.execute(
            select(User).where(User.email == admin_email)
        )
        admin = admin_r.scalar_one_or_none()
        if admin is None:
            admin = User(
                email=admin_email,
                hashed_password=hash_password(admin_pass),
                role=UserRole.ADMIN,
                tenant_id="default",
            )
            session.add(admin)
            await session.flush()

        # Seed the default preset if absent
        preset_r = await session.execute(select(PromptPreset).limit(1))
        if preset_r.scalar_one_or_none() is None:
            preset = PromptPreset(
                name="Make Compliance-Pass",
                kind="transform",
                prompt_text=COMPLIANCE_REWRITE_USER_TEMPLATE,
                active=True,
                created_by_admin=admin.id,
            )
            session.add(preset)

        await session.commit()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_langgraph_saver(apply_migrations):
    """
    Initialise the AsyncPostgresSaver once per test session and inject it into
    the FastAPI app.state so refine endpoints can use it.
    The saver connection stays open for the whole session and is closed at teardown.
    """
    _db_url_sync = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://postgres@localhost:5432/test_talentsync"
    ).replace("postgresql+asyncpg://", "postgresql://")

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from api.main import app

        saver_cm = AsyncPostgresSaver.from_conn_string(_db_url_sync)
        saver = await saver_cm.__aenter__()
        await saver.setup()
        app.state.langgraph_saver = saver
        yield
        try:
            await saver_cm.__aexit__(None, None, None)
        except Exception:
            pass
    except Exception as exc:
        print(f"[test setup] LangGraph saver not available: {exc}")
        yield


# ── Per-test fixtures ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """Test-managed session that ROLLS BACK after each test.
    Suitable for direct DB assertions; use `await db.commit()` inside tests
    to make app-visible rows when needed."""
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession) -> User:
    email = _unique_email("admin")
    user = User(
        email=email,
        hashed_password=hash_password("testpass123"),
        role=UserRole.ADMIN,
        tenant_id="default",
    )
    db.add(user)
    await db.commit()   # commit so the app can see this user for login
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def recruiter_user(db: AsyncSession) -> User:
    email = _unique_email("recruiter")
    user = User(
        email=email,
        hashed_password=hash_password("testpass123"),
        role=UserRole.RECRUITER,
        tenant_id="default",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def approver_user(db: AsyncSession) -> User:
    email = _unique_email("approver")
    user = User(
        email=email,
        hashed_password=hash_password("testpass123"),
        role=UserRole.APPROVER,
        tenant_id="default",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def client():
    """AsyncClient using the FastAPI ASGI transport."""
    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient, admin_user: User) -> AsyncClient:
    """Pre-authenticated client as admin."""
    resp = await client.post("/api/auth/login", json={
        "email": admin_user.email,
        "password": "testpass123",
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest_asyncio.fixture
async def recruiter_client(client: AsyncClient, recruiter_user: User) -> AsyncClient:
    """Pre-authenticated client as recruiter."""
    resp = await client.post("/api/auth/login", json={
        "email": recruiter_user.email,
        "password": "testpass123",
    })
    assert resp.status_code == 200, f"Recruiter login failed: {resp.text}"
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
