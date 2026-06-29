"""
Tests for audit_log correctness and append-only enforcement.

Every state change (upload, login, docx download) must produce an audit row with a real actor.
Append-only is enforced at the DB level (REVOKE UPDATE, DELETE from talentsync_app).
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from db.models import AuditLog, User

pytestmark = pytest.mark.asyncio

SAMPLE_JD = """
Junior Data Analyst

Seeking a fresher or 0-2 year experience data analyst.
Must know Excel, SQL, and basic Python. Salary not disclosed.
"""


async def test_login_writes_audit_row(admin_client: AsyncClient, db: AsyncSession):
    """A successful login writes an audit_log row with action='login'."""
    await db.commit()
    rows_r = await db.execute(
        select(AuditLog).where(AuditLog.action == "login")
    )
    rows = rows_r.scalars().all()
    assert len(rows) >= 1


async def test_upload_writes_audit_row(recruiter_client: AsyncClient, db: AsyncSession):
    """JD upload writes an audit_log row with action='jd.upload'."""
    await recruiter_client.post("/api/extract", json={"text": SAMPLE_JD})
    await db.commit()
    rows_r = await db.execute(
        select(AuditLog).where(AuditLog.action == "jd.upload")
    )
    rows = rows_r.scalars().all()
    assert len(rows) >= 1
    row = rows[-1]
    assert row.actor is not None
    assert row.target_type == "job"
    assert row.target_id is not None
    assert row.tenant_id == "default"
    assert "content_hash" in (row.detail or {})


async def test_audit_actor_matches_authenticated_user(
    recruiter_client: AsyncClient,
    recruiter_user: User,
    db: AsyncSession,
):
    """The actor in the audit row is the authenticated recruiter, not null."""
    await recruiter_client.post("/api/extract", json={"text": SAMPLE_JD})
    await db.commit()

    rows_r = await db.execute(
        select(AuditLog)
        .where(AuditLog.action == "jd.upload")
        .order_by(AuditLog.ts.desc())
    )
    rows = rows_r.scalars().all()
    assert len(rows) >= 1
    # Actor must be a real user UUID (not anonymous)
    assert rows[0].actor == recruiter_user.id


async def test_audit_log_has_timestamp(recruiter_client: AsyncClient, db: AsyncSession):
    await recruiter_client.post("/api/extract", json={"text": SAMPLE_JD})
    await db.commit()
    rows_r = await db.execute(select(AuditLog).where(AuditLog.action == "jd.upload"))
    rows = rows_r.scalars().all()
    assert all(r.ts is not None for r in rows)


async def test_approver_can_read_audit_log(
    admin_client: AsyncClient,
    approver_user: User,
    db: AsyncSession,
):
    """Approver/admin can read the audit log for a job."""
    upload_resp = await admin_client.post("/api/extract", json={"text": SAMPLE_JD})
    job_id = upload_resp.json()["id"]
    await db.commit()

    # Log in as approver
    resp = await admin_client.post("/api/auth/register", json={
        "email": "approver@test.local",
        "password": "testpass123",
        "role": "approver",
    })
    # May already exist from fixture — either 201 or 409
    assert resp.status_code in (201, 409)

    # Fresh login as approver
    login_resp = await admin_client.post("/api/auth/login", json={
        "email": "approver@test.local", "password": "testpass123"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    admin_client.headers["Authorization"] = f"Bearer {token}"

    audit_resp = await admin_client.get(f"/api/records/{job_id}/audit")
    assert audit_resp.status_code == 200
    entries = audit_resp.json()
    assert isinstance(entries, list)
    actions = [e["action"] for e in entries]
    assert "jd.upload" in actions


async def test_recruiter_cannot_read_audit_log(
    recruiter_client: AsyncClient,
    db: AsyncSession,
):
    """Recruiter cannot access the audit log endpoint."""
    upload_resp = await recruiter_client.post("/api/extract", json={"text": SAMPLE_JD})
    job_id = upload_resp.json()["id"]
    await db.commit()

    resp = await recruiter_client.get(f"/api/records/{job_id}/audit")
    assert resp.status_code == 403


async def test_audit_log_append_only_at_db_level(db: AsyncSession):
    """
    Verify that UPDATE and DELETE on audit_log are revoked from talentsync_app.
    We test this by checking the pg_roles / information_schema grants.
    """
    # Check that talentsync_app role exists
    role_r = await db.execute(
        text("SELECT rolname FROM pg_roles WHERE rolname = 'talentsync_app'")
    )
    roles = role_r.fetchall()
    assert len(roles) == 1, "talentsync_app role must exist after migration"

    # Check that UPDATE privilege on audit_log is NOT held by talentsync_app
    priv_r = await db.execute(text("""
        SELECT privilege_type
        FROM information_schema.role_table_grants
        WHERE grantee = 'talentsync_app'
          AND table_name = 'audit_log'
          AND privilege_type IN ('UPDATE', 'DELETE')
    """))
    forbidden_privs = [row[0] for row in priv_r.fetchall()]
    assert "UPDATE" not in forbidden_privs, "talentsync_app must NOT have UPDATE on audit_log"
    assert "DELETE" not in forbidden_privs, "talentsync_app must NOT have DELETE on audit_log"


async def test_register_writes_audit_row(admin_client: AsyncClient, db: AsyncSession):
    """User creation by admin writes an audit_log row."""
    await admin_client.post("/api/auth/register", json={
        "email": "newuser_audit@test.local",
        "password": "pass123",
        "role": "recruiter",
    })
    await db.commit()
    rows_r = await db.execute(
        select(AuditLog).where(AuditLog.action == "user.create")
    )
    rows = rows_r.scalars().all()
    assert len(rows) >= 1
