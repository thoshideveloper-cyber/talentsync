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
    engine = create_async_engine(DATABASE_URL, echo=False)
else:
    # asyncpg doesn't accept ssl/sslmode as URL params — pass via connect_args
    _connect_args: dict = {}
    _clean_url = DATABASE_URL
    for _param in ("ssl=require", "ssl=prefer", "sslmode=require", "sslmode=prefer"):
        if _param in _clean_url:
            _clean_url = _clean_url.replace(f"?{_param}", "").replace(f"&{_param}", "")
            _connect_args["ssl"] = "require"
    engine = create_async_engine(
        _clean_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        connect_args=_connect_args,
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
