"""Tests for JD versioning, lineage, and dedup rules."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Job, JDVersion

pytestmark = pytest.mark.asyncio

JD_V1 = """
Software Engineer — Python Backend (Fresher)

We are looking for a fresher Python developer eager to grow.
Must know Python and SQL basics.
"""

JD_V2 = """
Software Engineer — Python Backend (Mid-Level)

Looking for a mid-level Python developer with 3-5 years of experience.
Strong Python, SQL, and REST API skills required. Salary: 10-15 LPA.
"""


async def test_each_upload_creates_separate_job(recruiter_client: AsyncClient, db: AsyncSession):
    """Two distinct JD uploads each create their own job row."""
    r1 = await recruiter_client.post("/api/extract", json={"text": JD_V1})
    r2 = await recruiter_client.post("/api/extract", json={"text": JD_V2})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] != r2.json()["id"]

    await db.commit()
    jobs_r = await db.execute(select(Job))
    jobs = jobs_r.scalars().all()
    assert len(jobs) >= 2


async def test_version_has_lineage_fields(recruiter_client: AsyncClient, db: AsyncSession):
    """Uploaded JD produces a jd_version with expected fields."""
    resp = await recruiter_client.post("/api/extract", json={"text": JD_V1})
    version_id = resp.json()["version_id"]

    await db.commit()
    import uuid
    ver_r = await db.execute(
        select(JDVersion).where(JDVersion.id == uuid.UUID(version_id))
    )
    ver = ver_r.scalar_one()
    assert ver.content_hash  # sha256 hash present
    assert ver.source.value == "upload"
    assert ver.change_note == "Initial upload"
    assert ver.parent_version_id is None  # first version has no parent
    assert ver.created_at is not None
    assert ver.tenant_id == "default"


async def test_job_current_version_pointer_set(recruiter_client: AsyncClient, db: AsyncSession):
    """After upload, job.current_version_id matches the version returned."""
    resp = await recruiter_client.post("/api/extract", json={"text": JD_V1})
    job_id = resp.json()["id"]
    version_id = resp.json()["version_id"]

    await db.commit()
    import uuid
    job_r = await db.execute(
        select(Job).where(Job.id == uuid.UUID(job_id))
    )
    job = job_r.scalar_one()
    assert str(job.current_version_id) == version_id


async def test_get_versions_returns_history(recruiter_client: AsyncClient):
    """GET /api/records/{id}/versions returns at least one version."""
    resp = await recruiter_client.post("/api/extract", json={"text": JD_V1})
    job_id = resp.json()["id"]

    vers_resp = await recruiter_client.get(f"/api/records/{job_id}/versions")
    assert vers_resp.status_code == 200
    versions = vers_resp.json()
    assert len(versions) == 1
    v = versions[0]
    assert "version_id" in v
    assert "content_hash" in v
    assert "source" in v
    assert v["source"] == "upload"
    assert v["parent_version_id"] is None


async def test_content_hash_is_deterministic(recruiter_client: AsyncClient):
    """Same text always produces the same content_hash."""
    import hashlib
    text = JD_V1
    expected_hash = hashlib.sha256(text.encode()).hexdigest()

    resp = await recruiter_client.post("/api/extract", json={"text": text})
    assert resp.json()["content_hash"] == expected_hash


async def test_different_text_produces_different_hash(recruiter_client: AsyncClient):
    r1 = await recruiter_client.post("/api/extract", json={"text": JD_V1})
    r2 = await recruiter_client.post("/api/extract", json={"text": JD_V2})
    assert r1.json()["content_hash"] != r2.json()["content_hash"]
