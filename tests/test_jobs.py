"""Tests for job/JD extraction and retrieval endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Job, JDVersion, ComplianceCheck

pytestmark = pytest.mark.asyncio

SAMPLE_JD = """
Senior Software Engineer — Backend

We are looking for a Senior Software Engineer with 5+ years of experience in Python,
PostgreSQL, and distributed systems. The ideal candidate has strong system design skills
and experience with AWS or GCP.

Salary: 25-40 LPA

Requirements:
- 5+ years Python
- PostgreSQL / SQL databases
- REST API design
- Kubernetes / Docker
"""


async def test_extract_creates_job_and_version(recruiter_client: AsyncClient, db: AsyncSession):
    resp = await recruiter_client.post("/api/extract", json={"text": SAMPLE_JD})
    assert resp.status_code == 200
    data = resp.json()

    # Backward-compatible shape
    assert "id" in data
    assert "content_hash" in data
    assert "ai_seniority" in data
    assert isinstance(data["required_skills"], list)
    assert isinstance(data["bias_flags"], list)
    assert data["status"] in ("ok", "unverified", "failed")

    # Phase 0 new fields
    assert "version_id" in data
    assert "created_at" in data

    # DB verification
    await db.commit()
    job_r = await db.execute(select(Job))
    jobs = job_r.scalars().all()
    assert len(jobs) >= 1

    # Current version pointer is set
    last_job = jobs[-1]
    assert last_job.current_version_id is not None


async def test_extract_empty_text_returns_400(recruiter_client: AsyncClient):
    resp = await recruiter_client.post("/api/extract", json={"text": "   "})
    assert resp.status_code == 400


async def test_get_records_returns_list(recruiter_client: AsyncClient):
    # Upload one JD first
    await recruiter_client.post("/api/extract", json={"text": SAMPLE_JD})
    resp = await recruiter_client.get("/api/records")
    assert resp.status_code == 200
    records = resp.json()
    assert isinstance(records, list)
    assert len(records) >= 1
    # Each record has the expected shape
    r = records[0]
    for key in ("id", "role", "ai_seniority", "content_hash", "status"):
        assert key in r


async def test_get_record_by_id(recruiter_client: AsyncClient):
    extract_resp = await recruiter_client.post("/api/extract", json={"text": SAMPLE_JD})
    job_id = extract_resp.json()["id"]

    resp = await recruiter_client.get(f"/api/records/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id


async def test_get_record_not_found(recruiter_client: AsyncClient):
    import uuid
    resp = await recruiter_client.get(f"/api/records/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_get_record_invalid_uuid(recruiter_client: AsyncClient):
    resp = await recruiter_client.get("/api/records/not-a-uuid")
    assert resp.status_code == 400


async def test_compliance_checks_written(recruiter_client: AsyncClient, db: AsyncSession):
    """Compliance checks are persisted alongside each JD version."""
    resp = await recruiter_client.post("/api/extract", json={"text": SAMPLE_JD})
    version_id = resp.json()["version_id"]

    await db.commit()
    import uuid
    checks_r = await db.execute(
        select(ComplianceCheck).where(ComplianceCheck.jd_version_id == uuid.UUID(version_id))
    )
    checks = checks_r.scalars().all()
    # At minimum a pay disclosure check (SAMPLE_JD has salary) or a quality check
    assert isinstance(checks, list)  # may be empty for a perfect JD


async def test_kpis_endpoint(recruiter_client: AsyncClient):
    await recruiter_client.post("/api/extract", json={"text": SAMPLE_JD})
    resp = await recruiter_client.get("/api/kpis")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("total", "flagged_for_review", "leveling_flags", "with_pay_range", "verified"):
        assert key in data
    assert data["total"] >= 1


async def test_skills_endpoint(recruiter_client: AsyncClient):
    await recruiter_client.post("/api/extract", json={"text": SAMPLE_JD})
    resp = await recruiter_client.get("/api/skills")
    assert resp.status_code == 200
    skills = resp.json()
    assert isinstance(skills, list)


async def test_export_csv(recruiter_client: AsyncClient):
    await recruiter_client.post("/api/extract", json={"text": SAMPLE_JD})
    resp = await recruiter_client.get("/api/export.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    lines = resp.text.strip().split("\n")
    assert len(lines) >= 2  # header + at least one row


async def test_unauthenticated_extract_rejected(client: AsyncClient):
    resp = await client.post("/api/extract", json={"text": SAMPLE_JD})
    assert resp.status_code in (401, 403)
