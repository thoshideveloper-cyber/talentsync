"""
Dialect-adaptive column types.

The pilot targets PostgreSQL (JSONB + native UUID). For local/offline runs where
no Postgres server is available, the same models must also work on SQLite. These
helpers render the Postgres-native type on Postgres and a portable equivalent on
SQLite — no model changes required beyond importing from here.
"""
from sqlalchemy import JSON, Uuid
from sqlalchemy.dialects.postgresql import JSONB as _PG_JSONB
from sqlalchemy.dialects.postgresql import UUID as _PG_UUID


def UUID(as_uuid: bool = True):
    """Postgres UUID on Postgres; SQLAlchemy generic Uuid (CHAR-backed) on SQLite."""
    return _PG_UUID(as_uuid=as_uuid).with_variant(Uuid(as_uuid=as_uuid), "sqlite")


# Shared instance is safe to reuse across columns.
JSONB = _PG_JSONB().with_variant(JSON(), "sqlite")
