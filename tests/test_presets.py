"""
Phase 5 Channel B — Preset CRUD + transform endpoint tests.

All tests run with TALENTSYNC_STUB=1 (no LLM calls).
"""
import pytest


_PRESET_PAYLOAD = {
    "name": "Test Rewrite Preset",
    "kind": "transform",
    "prompt_text": "Rewrite this JD: {raw_jd}\n\nIssues: {findings}",
}

_NONCOMPLIANT_JD = (
    "Software Engineer. Age below 30 preferred. Male candidates only. "
    "3+ years Python. AWS experience. Freshers need not apply."
)


# ── Preset CRUD ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_presets_recruiter(recruiter_client):
    resp = await recruiter_client.get("/api/presets")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_presets_includes_seeded_preset(recruiter_client):
    """The startup seed should have created 'Make Compliance-Pass'."""
    resp = await recruiter_client.get("/api/presets")
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()]
    assert "Make Compliance-Pass" in names, f"Seeded preset missing; got: {names}"


@pytest.mark.asyncio
async def test_create_preset_admin_can_create(admin_client):
    resp = await admin_client.post("/api/presets", json=_PRESET_PAYLOAD)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == _PRESET_PAYLOAD["name"]
    assert data["active"] is True


@pytest.mark.asyncio
async def test_create_preset_recruiter_forbidden(recruiter_client):
    resp = await recruiter_client.post("/api/presets", json=_PRESET_PAYLOAD)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_preset_unauthenticated(client):
    resp = await client.post("/api/presets", json=_PRESET_PAYLOAD)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_preset_empty_name_rejected(admin_client):
    resp = await admin_client.post("/api/presets", json={**_PRESET_PAYLOAD, "name": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_preset_invalid_kind_rejected(admin_client):
    resp = await admin_client.post("/api/presets", json={**_PRESET_PAYLOAD, "kind": "unknown"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_deactivate_preset(admin_client):
    # Create
    create_resp = await admin_client.post("/api/presets", json=_PRESET_PAYLOAD)
    assert create_resp.status_code == 201
    preset_id = create_resp.json()["id"]

    # Deactivate
    del_resp = await admin_client.delete(f"/api/presets/{preset_id}")
    assert del_resp.status_code == 200

    # No longer listed
    list_resp = await admin_client.get("/api/presets")
    ids = [p["id"] for p in list_resp.json()]
    assert preset_id not in ids


@pytest.mark.asyncio
async def test_deactivate_already_inactive_returns_409(admin_client):
    create_resp = await admin_client.post("/api/presets", json=_PRESET_PAYLOAD)
    assert create_resp.status_code == 201
    preset_id = create_resp.json()["id"]

    await admin_client.delete(f"/api/presets/{preset_id}")
    resp2 = await admin_client.delete(f"/api/presets/{preset_id}")
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_deactivate_nonexistent_preset(admin_client):
    import uuid
    resp = await admin_client.delete(f"/api/presets/{uuid.uuid4()}")
    assert resp.status_code == 404


# ── Transform endpoint ────────────────────────────────────────────────────────

async def _upload_jd(client, jd_text: str) -> str:
    resp = await client.post("/api/extract", json={"text": jd_text})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_transform_creates_new_version(recruiter_client, admin_client):
    record_id = await _upload_jd(recruiter_client, _NONCOMPLIANT_JD)

    # Get the seeded preset id
    presets = await recruiter_client.get("/api/presets")
    preset_id = next(p["id"] for p in presets.json() if p["name"] == "Make Compliance-Pass")

    resp = await recruiter_client.post(
        f"/api/records/{record_id}/transform",
        json={"preset_id": preset_id},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == record_id
    assert data["version_id"]  # new version
    assert data["compliance_summary"]["verdict"] in ("pass", "warn")


@pytest.mark.asyncio
async def test_transform_response_has_transform_meta(recruiter_client):
    record_id = await _upload_jd(recruiter_client, _NONCOMPLIANT_JD)
    presets = await recruiter_client.get("/api/presets")
    preset_id = next(p["id"] for p in presets.json() if p["name"] == "Make Compliance-Pass")

    resp = await recruiter_client.post(
        f"/api/records/{record_id}/transform",
        json={"preset_id": preset_id},
    )
    assert resp.status_code == 200
    meta = resp.json()["transform_meta"]
    assert meta["preset_name"] == "Make Compliance-Pass"
    assert meta["preset_id"] == preset_id
    assert meta["parent_version_id"]


@pytest.mark.asyncio
async def test_transform_version_source_is_rewrite(recruiter_client):
    record_id = await _upload_jd(recruiter_client, _NONCOMPLIANT_JD)
    presets = await recruiter_client.get("/api/presets")
    preset_id = next(p["id"] for p in presets.json() if p["name"] == "Make Compliance-Pass")

    await recruiter_client.post(
        f"/api/records/{record_id}/transform",
        json={"preset_id": preset_id},
    )
    versions_resp = await recruiter_client.get(f"/api/records/{record_id}/versions")
    versions = versions_resp.json()
    sources = [v["source"] for v in versions]
    assert "rewrite" in sources


@pytest.mark.asyncio
async def test_transform_preserves_version_chain(recruiter_client):
    record_id = await _upload_jd(recruiter_client, _NONCOMPLIANT_JD)
    presets = await recruiter_client.get("/api/presets")
    preset_id = next(p["id"] for p in presets.json() if p["name"] == "Make Compliance-Pass")

    original_version_resp = await recruiter_client.get(f"/api/records/{record_id}/versions")
    original_version_id = original_version_resp.json()[0]["version_id"]

    await recruiter_client.post(
        f"/api/records/{record_id}/transform",
        json={"preset_id": preset_id},
    )
    versions = (await recruiter_client.get(f"/api/records/{record_id}/versions")).json()
    assert len(versions) == 2
    rewrite_version = next(v for v in versions if v["source"] == "rewrite")
    assert rewrite_version["parent_version_id"] == original_version_id


@pytest.mark.asyncio
async def test_transform_compliance_is_persisted(recruiter_client):
    record_id = await _upload_jd(recruiter_client, _NONCOMPLIANT_JD)
    presets = await recruiter_client.get("/api/presets")
    preset_id = next(p["id"] for p in presets.json() if p["name"] == "Make Compliance-Pass")

    await recruiter_client.post(
        f"/api/records/{record_id}/transform",
        json={"preset_id": preset_id},
    )
    comp = await recruiter_client.get(f"/api/records/{record_id}/compliance")
    assert comp.status_code == 200
    assert "checks" in comp.json()


@pytest.mark.asyncio
async def test_transform_unknown_record_returns_404(recruiter_client):
    import uuid
    presets = await recruiter_client.get("/api/presets")
    preset_id = presets.json()[0]["id"]

    resp = await recruiter_client.post(
        f"/api/records/{uuid.uuid4()}/transform",
        json={"preset_id": preset_id},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_transform_inactive_preset_returns_404(recruiter_client, admin_client):
    # Create + immediately deactivate a preset
    create_resp = await admin_client.post("/api/presets", json=_PRESET_PAYLOAD)
    assert create_resp.status_code == 201
    preset_id = create_resp.json()["id"]
    await admin_client.delete(f"/api/presets/{preset_id}")

    record_id = await _upload_jd(recruiter_client, _NONCOMPLIANT_JD)
    resp = await recruiter_client.post(
        f"/api/records/{record_id}/transform",
        json={"preset_id": preset_id},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_transform_requires_auth(client):
    # Auth check fires before record/preset lookup — random UUIDs are fine
    import uuid as _uuid
    resp = await client.post(
        f"/api/records/{_uuid.uuid4()}/transform",
        json={"preset_id": str(_uuid.uuid4())},
    )
    assert resp.status_code == 401
