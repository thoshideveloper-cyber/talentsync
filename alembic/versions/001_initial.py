"""Initial schema: users, jobs, jd_versions, compliance_checks, prompt_presets, audit_log.

Revision ID: 001
Revises:
Create Date: 2026-06-28

Schema decisions preserved here for traceability:
- tenant_id on all tables: single-value "default" pilot; no RLS. Scale = backfill + RLS.
- Circular FK (jobs.current_version_id ↔ jd_versions.job_id): resolved by creating the column
  without a FK, creating jd_versions, then adding the FK via CREATE_FOREIGN_KEY (use_alter).
- audit_log append-only: enforced by REVOKING UPDATE/DELETE from the talentsync_app role.
  The app role is created here and used by the application (not the admin/migration role).
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(name: str, *values: str) -> postgresql.ENUM:
    """Return a pre-existing PostgreSQL enum (create_type=False keeps Alembic from auto-creating)."""
    return postgresql.ENUM(*values, name=name, create_type=False)


def upgrade() -> None:
    # ── Enum types — created before create_table so they already exist ────────
    # Using DO blocks so the migration is idempotent on partial re-runs.
    for stmt in [
        "DO $$ BEGIN CREATE TYPE userrole AS ENUM ('recruiter','approver','admin'); EXCEPTION WHEN duplicate_object THEN NULL; END $$",
        "DO $$ BEGIN CREATE TYPE jobstatus AS ENUM ('draft','active','published','archived'); EXCEPTION WHEN duplicate_object THEN NULL; END $$",
        "DO $$ BEGIN CREATE TYPE versionsource AS ENUM ('upload','draft','rewrite'); EXCEPTION WHEN duplicate_object THEN NULL; END $$",
        "DO $$ BEGIN CREATE TYPE checkresult AS ENUM ('pass','warn','fail'); EXCEPTION WHEN duplicate_object THEN NULL; END $$",
    ]:
        op.execute(sa.text(stmt))

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", _enum("userrole", "recruiter", "approver", "admin"),
                  nullable=False, server_default="recruiter"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="default"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    # ── jobs (current_version_id FK deferred — added after jd_versions) ──────
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("role", sa.String(512), nullable=False),
        sa.Column("input_format", sa.String(64), nullable=False, server_default="paste"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", _enum("jobstatus", "draft", "active", "published", "archived"),
                  nullable=False, server_default="active"),
    )
    op.create_index("ix_jobs_tenant_id", "jobs", ["tenant_id"])

    # ── jd_versions ───────────────────────────────────────────────────────────
    op.create_table(
        "jd_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("parent_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("raw_jd", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("ai_seniority", sa.String(64), nullable=True),
        sa.Column("native_label", sa.String(64), nullable=True),
        sa.Column("required_skills", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("bias_flags", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("pay_range_present", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("quality_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("score_breakdown", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("audit_mismatch", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("raw_text_justification", sa.Text, nullable=True),
        sa.Column("source", _enum("versionsource", "upload", "draft", "rewrite"),
                  nullable=False, server_default="upload"),
        sa.Column("change_note", sa.Text, nullable=True),
        sa.Column("status", sa.String(64), nullable=False, server_default="ok"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="default"),
    )
    op.create_index("ix_jd_versions_job_id", "jd_versions", ["job_id"])
    op.create_index("ix_jd_versions_content_hash", "jd_versions", ["content_hash"])
    op.create_index("ix_jd_versions_tenant_id", "jd_versions", ["tenant_id"])

    # Self-referential FK for parent_version_id
    op.create_foreign_key(
        "fk_jd_versions_parent",
        "jd_versions", "jd_versions",
        ["parent_version_id"], ["id"],
        ondelete="SET NULL",
    )

    # Deferred FK: jobs.current_version_id → jd_versions.id (use_alter pattern)
    op.create_foreign_key(
        "fk_jobs_current_version_id",
        "jobs", "jd_versions",
        ["current_version_id"], ["id"],
        ondelete="SET NULL",
    )

    # ── compliance_checks ─────────────────────────────────────────────────────
    op.create_table(
        "compliance_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "jd_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jd_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_id", sa.String(128), nullable=False),
        sa.Column("result", _enum("checkresult", "pass", "warn", "fail"), nullable=False),
        sa.Column("evidence_span", sa.Text, nullable=True),
        sa.Column("citation", sa.Text, nullable=True),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_compliance_checks_jd_version_id", "compliance_checks", ["jd_version_id"])

    # ── prompt_presets ────────────────────────────────────────────────────────
    op.create_table(
        "prompt_presets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False, server_default="transform"),
        sa.Column("prompt_text", sa.Text, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_by_admin",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # ── audit_log (append-only — enforced via DB grants below) ────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("detail", postgresql.JSONB, nullable=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="default"),
    )
    op.create_index("ix_audit_log_tenant_id", "audit_log", ["tenant_id"])
    op.create_index("ix_audit_log_target_id", "audit_log", ["target_id"])

    # ── App role + append-only enforcement ────────────────────────────────────
    # Creates talentsync_app role (if it doesn't exist) and locks audit_log.
    # The application connects as talentsync_app; migrations run as the superuser.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'talentsync_app') THEN
                CREATE ROLE talentsync_app WITH LOGIN PASSWORD 'talentsync_app_pass';
            END IF;
        END
        $$;
    """)
    op.execute(sa.text("DO $$ BEGIN EXECUTE 'GRANT CONNECT ON DATABASE ' || current_database() || ' TO talentsync_app'; EXCEPTION WHEN OTHERS THEN NULL; END $$"))
    op.execute("GRANT USAGE ON SCHEMA public TO talentsync_app")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO talentsync_app"
    )
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO talentsync_app")
    # Enforce append-only: app role cannot mutate or delete audit rows
    op.execute("REVOKE UPDATE, DELETE ON audit_log FROM talentsync_app")


def downgrade() -> None:
    # Restore full permissions before dropping tables
    op.execute(
        "GRANT UPDATE, DELETE ON audit_log TO talentsync_app"
    )
    op.drop_index("ix_audit_log_target_id", "audit_log")
    op.drop_index("ix_audit_log_tenant_id", "audit_log")
    op.drop_table("audit_log")
    op.drop_table("prompt_presets")
    op.drop_index("ix_compliance_checks_jd_version_id", "compliance_checks")
    op.drop_table("compliance_checks")
    op.drop_constraint("fk_jobs_current_version_id", "jobs", type_="foreignkey")
    op.drop_constraint("fk_jd_versions_parent", "jd_versions", type_="foreignkey")
    op.drop_index("ix_jd_versions_tenant_id", "jd_versions")
    op.drop_index("ix_jd_versions_content_hash", "jd_versions")
    op.drop_index("ix_jd_versions_job_id", "jd_versions")
    op.drop_table("jd_versions")
    op.drop_index("ix_jobs_tenant_id", "jobs")
    op.drop_table("jobs")
    op.drop_index("ix_users_tenant_id", "users")
    op.drop_index("ix_users_email", "users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS checkresult")
    op.execute("DROP TYPE IF EXISTS versionsource")
    op.execute("DROP TYPE IF EXISTS jobstatus")
    op.execute("DROP TYPE IF EXISTS userrole")
