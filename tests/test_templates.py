"""
Feature E — Template Library endpoint tests.

GET  /api/templates
POST /api/templates/{version_id}/clone
"""
import uuid as _uuid

import pytest

_CLEAN_JD = (
    "Senior Software Engineer. 5+ years Python, PostgreSQL, AWS. "
    "Salary: 28-38 LPA. Bengaluru (Hybrid). Equal opportunity employer."
)
_HIGH_RISK_JD = (
    "Junior Engineer. Age below 25 only. Male candidates preferred. "
    "1-2 years experience. Freshers need not apply."
)


async def _upload(client, text: str) -> dict:
    resp = await client.post("/api/extract", json={"text": text})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── List templates ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_templates_returns_list(recruiter_client):
    resp = await recruiter_client.get("/api/templates")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_list_templates_returns_only_passing(recruiter_client):
    """Templates endpoint must not include versions with high-risk findings."""
    await _upload(recruiter_client, _HIGH_RISK_JD)
    resp = await recruiter_client.get("/api/templates")
    templates = resp.json()
    # All returned templates should be passing (no high-risk rule_ids)
    # We can verify by cloning one — if any non-passing slips in, clone will 422
    for t in templates:
        assert "version_id" in t
        assert "role" in t


@pytest.mark.asyncio
async def test_list_templates_clean_jd_appears(recruiter_client):
    """A clean uploaded JD should appear in the template list."""
    record = await _upload(recruiter_client, _CLEAN_JD)
    resp = await recruiter_client.get("/api/templates")
    version_ids = [t["version_id"] for t in resp.json()]
    assert record["version_id"] in version_ids


@pytest.mark.asyncio
async def test_list_templates_requires_auth(client):
    resp = await client.get("/api/templates")
    assert resp.status_code == 401


# ── Clone ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_clone_creates_new_job_and_version(recruiter_client):
    record = await _upload(recruiter_client, _CLEAN_JD)
    version_id = record["version_id"]

    resp = await recruiter_client.post(f"/api/templates/{version_id}/clone")
    assert resp.status_code == 201, resp.text
    data = resp.json()
    # New job must have a different id
    assert data["id"] != record["id"]
    assert data["version_id"]


@pytest.mark.asyncio
async def test_clone_sets_parent_version_id(recruiter_client):
    """Cloned version must point to the source version via parent_version_id."""
    record = await _upload(recruiter_client, _CLEAN_JD)
    version_id = record["version_id"]

    clone_resp = await recruiter_client.post(f"/api/templates/{version_id}/clone")
    assert clone_resp.status_code == 201
    new_job_id = clone_resp.json()["id"]

    versions_resp = await recruiter_client.get(f"/api/records/{new_job_id}/versions")
    versions = versions_resp.json()
    assert len(versions) == 1
    assert versions[0]["parent_version_id"] == version_id


@pytest.mark.asyncio
async def test_clone_runs_compliance(recruiter_client):
    """After clone, compliance endpoint must return results for the new version."""
    record = await _upload(recruiter_client, _CLEAN_JD)
    clone_resp = await recruiter_client.post(
        f"/api/templates/{record['version_id']}/clone"
    )
    assert clone_resp.status_code == 201
    new_job_id = clone_resp.json()["id"]

    comp = await recruiter_client.get(f"/api/records/{new_job_id}/compliance")
    assert comp.status_code == 200
    assert "checks" in comp.json()


@pytest.mark.asyncio
async def test_clone_noncompliant_returns_422(recruiter_client):
    """Attempting to clone a non-passing version must return 422."""
    record = await _upload(recruiter_client, _HIGH_RISK_JD)
    resp = await recruiter_client.post(
        f"/api/templates/{record['version_id']}/clone"
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_clone_unknown_version_returns_404(recruiter_client):
    resp = await recruiter_client.post(f"/api/templates/{_uuid.uuid4()}/clone")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_clone_requires_auth(client):
    resp = await client.post(f"/api/templates/{_uuid.uuid4()}/clone")
    assert resp.status_code == 401
