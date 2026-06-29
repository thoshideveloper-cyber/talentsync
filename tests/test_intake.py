"""
Phase 3 — JD Intake endpoint tests.

All tests run with TALENTSYNC_STUB=1 (no LLM calls).
"""
import pytest


VALID_INTAKE = {
    "role": "Senior Software Engineer",
    "level": "Senior",
    "must_haves": ["Python", "PostgreSQL", "AWS"],
    "location": "Bengaluru (Hybrid)",
    "pay_band": "₹28-38 LPA",
    "notes": "B2B SaaS product team",
}


# ── Happy path ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_intake_creates_record(recruiter_client):
    resp = await recruiter_client.post("/api/intake", json=VALID_INTAKE)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"]
    assert data["version_id"]
    assert data["role"] == "Senior Software Engineer"


@pytest.mark.asyncio
async def test_intake_response_has_compliance_summary(recruiter_client):
    resp = await recruiter_client.post("/api/intake", json=VALID_INTAKE)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    cs = data["compliance_summary"]
    assert cs["verdict"] in ("pass", "warn")
    assert isinstance(cs["high_risk_count"], int)
    assert isinstance(cs["advisory_count"], int)


@pytest.mark.asyncio
async def test_intake_response_has_intake_meta(recruiter_client):
    resp = await recruiter_client.post("/api/intake", json=VALID_INTAKE)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    meta = data["intake_meta"]
    assert meta["level"] == "Senior"
    assert meta["location"] == "Bengaluru (Hybrid)"
    assert meta["pay_band"] == "₹28-38 LPA"
    assert "Python" in meta["must_haves"]


@pytest.mark.asyncio
async def test_intake_draft_is_retrievable(recruiter_client):
    """The created job should be accessible via GET /api/records/{id}."""
    resp = await recruiter_client.post("/api/intake", json=VALID_INTAKE)
    assert resp.status_code == 200, resp.text
    record_id = resp.json()["id"]

    get_resp = await recruiter_client.get(f"/api/records/{record_id}")
    assert get_resp.status_code == 200, get_resp.text
    assert get_resp.json()["id"] == record_id


@pytest.mark.asyncio
async def test_intake_draft_source_is_draft(recruiter_client):
    """Version source must be 'draft' so it's distinguishable from uploaded JDs."""
    resp = await recruiter_client.post("/api/intake", json=VALID_INTAKE)
    assert resp.status_code == 200, resp.text
    record_id = resp.json()["id"]

    versions_resp = await recruiter_client.get(f"/api/records/{record_id}/versions")
    assert versions_resp.status_code == 200
    versions = versions_resp.json()
    assert len(versions) == 1
    assert versions[0]["source"] == "draft"


@pytest.mark.asyncio
async def test_intake_all_levels_accepted(recruiter_client):
    for level in ("Internship", "Entry-Level", "Mid-Level", "Senior", "Executive"):
        resp = await recruiter_client.post("/api/intake", json={**VALID_INTAKE, "level": level})
        assert resp.status_code == 200, f"Level '{level}' failed: {resp.text}"


@pytest.mark.asyncio
async def test_intake_notes_optional(recruiter_client):
    payload = {k: v for k, v in VALID_INTAKE.items() if k != "notes"}
    resp = await recruiter_client.post("/api/intake", json=payload)
    assert resp.status_code == 200, resp.text


# ── Validation errors ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_intake_empty_role_rejected(recruiter_client):
    resp = await recruiter_client.post("/api/intake", json={**VALID_INTAKE, "role": "  "})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_intake_invalid_level_rejected(recruiter_client):
    resp = await recruiter_client.post("/api/intake", json={**VALID_INTAKE, "level": "Staff"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_intake_empty_must_haves_rejected(recruiter_client):
    resp = await recruiter_client.post("/api/intake", json={**VALID_INTAKE, "must_haves": []})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_intake_whitespace_only_must_haves_rejected(recruiter_client):
    resp = await recruiter_client.post("/api/intake", json={**VALID_INTAKE, "must_haves": ["  ", ""]})
    assert resp.status_code == 422


# ── Auth ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_intake_requires_auth(client):
    resp = await client.post("/api/intake", json=VALID_INTAKE)
    assert resp.status_code == 401


# ── Compliance auto-check ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_intake_compliance_persisted(recruiter_client):
    """After intake, the compliance endpoint for the new record must return checks."""
    resp = await recruiter_client.post("/api/intake", json=VALID_INTAKE)
    assert resp.status_code == 200
    record_id = resp.json()["id"]

    comp = await recruiter_client.get(f"/api/records/{record_id}/compliance")
    assert comp.status_code == 200, comp.text
    data = comp.json()
    assert "verdict" in data
    assert "checks" in data
