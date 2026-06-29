import os
from pathlib import Path

# Load .env before anything reads os.environ — must run before SQLAlchemy engine creation
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(Path(__file__).parent.parent / ".env", override=False)
except ImportError:
    pass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Default to a local file-based SQLite DB so the backend runs with no separate
# database server. For the Postgres pilot, set DATABASE_URL, e.g.
#   postgresql+asyncpg://postgres@localhost:5432/talentsync
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./talentsync.db",
)

IS_SQLITE = DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    # SQLite's default pool doesn't accept pool_size/max_overflow.
    engine = create_async_engine(DATABASE_URL, echo=False)
else:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
