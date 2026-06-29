"""
SQLAlchemy ORM models for TalentSync Phase 0.

Schema decisions (documented per engineering guardrail):
- tenant_id: String "default" on all tables; no RLS in pilot. Scale migration = backfill + add RLS.
- Version identity: dedup on (job_id, content_hash) on UPLOAD path only. Rewrites always create
  a new version even if they revert to an ancestor hash (preserves transformation chain).
- Hash strategy: sha256 of raw text. Whitespace change = new version. Intentional for audit trail.
- Circular FK (jobs.current_version_id ↔ jd_versions.job_id): handled via use_alter=True so the
  FK is added after both tables exist. Insert pattern: job(null) → jd_version → update pointer.
- audit_log: append-only enforced via DB GRANT (REVOKE UPDATE, DELETE FROM talentsync_app),
  not application convention.
"""
import uuid
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)

def _pg_enum(enum_cls: type, name: str) -> Enum:
    """SQLAlchemy Enum that stores .value (lowercase) in an existing PG enum type."""
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda obj: [e.value for e in obj],
        create_type=False,
    )
from .types import JSONB, UUID  # dialect-adaptive: Postgres-native or SQLite-portable
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base

DEFAULT_TENANT = "default"


# ── Enumerations ──────────────────────────────────────────────────────────────

class UserRole(str, PyEnum):
    RECRUITER = "recruiter"
    APPROVER = "approver"
    ADMIN = "admin"


class JobStatus(str, PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class VersionSource(str, PyEnum):
    UPLOAD = "upload"
    DRAFT = "draft"
    REWRITE = "rewrite"


class CheckResult(str, PyEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


# ── Tables ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(_pg_enum(UserRole, "userrole"), nullable=False, default=UserRole.RECRUITER)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    tenant_id = Column(String(64), nullable=False, default=DEFAULT_TENANT, index=True)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(64), nullable=False, default=DEFAULT_TENANT, index=True)
    role = Column(String(512), nullable=False)
    input_format = Column(String(64), nullable=False, default="paste")
    created_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # FK added post-creation via use_alter to break the circular dependency with jd_versions
    current_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "jd_versions.id",
            use_alter=True,
            name="fk_jobs_current_version_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    status = Column(_pg_enum(JobStatus, "jobstatus"), nullable=False, default=JobStatus.ACTIVE)

    creator = relationship("User", foreign_keys=[created_by])
    current_version = relationship(
        "JDVersion", foreign_keys=[current_version_id], post_update=True
    )


class JDVersion(Base):
    __tablename__ = "jd_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jd_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    raw_jd = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    summary = Column(Text, nullable=True)
    ai_seniority = Column(String(64), nullable=True)
    native_label = Column(String(64), nullable=True)
    required_skills = Column(JSONB, nullable=False, default=list)
    bias_flags = Column(JSONB, nullable=False, default=list)
    pay_range_present = Column(Boolean, nullable=False, default=False)
    quality_score = Column(Integer, nullable=False, default=0)
    score_breakdown = Column(JSONB, nullable=False, default=list)
    is_verified = Column(Boolean, nullable=False, default=False)
    audit_mismatch = Column(Boolean, nullable=False, default=False)
    raw_text_justification = Column(Text, nullable=True)
    source = Column(
        _pg_enum(VersionSource, "versionsource"), nullable=False, default=VersionSource.UPLOAD
    )
    change_note = Column(Text, nullable=True)
    status = Column(String(64), nullable=False, default="ok")
    created_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    tenant_id = Column(String(64), nullable=False, default=DEFAULT_TENANT, index=True)

    job = relationship("Job", foreign_keys=[job_id])
    creator = relationship("User", foreign_keys=[created_by])
    parent = relationship("JDVersion", foreign_keys=[parent_version_id], remote_side=[id])


class ComplianceCheck(Base):
    __tablename__ = "compliance_checks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jd_version_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jd_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id = Column(String(128), nullable=False)
    result = Column(_pg_enum(CheckResult, "checkresult"), nullable=False)
    evidence_span = Column(Text, nullable=True)
    citation = Column(Text, nullable=True)
    checked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PromptPreset(Base):
    __tablename__ = "prompt_presets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    kind = Column(String(64), nullable=False, default="transform")
    prompt_text = Column(Text, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_by_admin = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentRun(Base):
    """One LangGraph refine run (start → done/error/paused)."""
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    thread_id = Column(String(128), nullable=False, unique=True)
    status = Column(String(32), nullable=False, default="running")  # running/paused/done/error
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    actor = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    tenant_id = Column(String(64), nullable=False, default=DEFAULT_TENANT, index=True)

    job = relationship("Job", foreign_keys=[job_id])
    actor_user = relationship("User", foreign_keys=[actor])


class AgentStep(Base):
    """One node execution within an AgentRun."""
    __tablename__ = "agent_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    node_name = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False)  # ok/error/interrupted
    input_ref = Column(JSONB, nullable=True)
    output_ref = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)
    ts = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    run = relationship("AgentRun", foreign_keys=[run_id])


class AuditLog(Base):
    """Append-only audit trail. UPDATE/DELETE revoked at DB level from talentsync_app role."""
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action = Column(String(128), nullable=False)
    target_type = Column(String(64), nullable=True)
    target_id = Column(UUID(as_uuid=True), nullable=True)
    ts = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    detail = Column(JSONB, nullable=True)
    tenant_id = Column(String(64), nullable=False, default=DEFAULT_TENANT, index=True)

    actor_user = relationship("User", foreign_keys=[actor])
