"""
Phase 5 Channel A2 — Grounded Q&A endpoint tests.

All tests run with TALENTSYNC_STUB=1 (no LLM calls).
Stub mode returns a fixed answer string, so tests check shape not content.
"""
import pytest


_JD_TEXT = (
    "Senior Python Engineer. 6+ years experience. AWS required. "
    "Salary: 25-35 LPA. Bengaluru (Hybrid). Equal opportunity employer."
)


async def _upload_jd(client, text: str) -> str:
    resp = await client.post("/api/extract", json={"text": text})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


# ── Happy path ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ask_returns_answer(recruiter_client):
    record_id = await _upload_jd(recruiter_client, _JD_TEXT)
    resp = await recruiter_client.post(
        f"/api/records/{record_id}/ask",
        json={"question": "What is the salary range?"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "answer" in data
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0


@pytest.mark.asyncio
async def test_ask_returns_not_in_jd_flag(recruiter_client):
    record_id = await _upload_jd(recruiter_client, _JD_TEXT)
    resp = await recruiter_client.post(
        f"/api/records/{record_id}/ask",
        json={"question": "What is the salary range?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "not_in_jd" in data
    assert isinstance(data["not_in_jd"], bool)


@pytest.mark.asyncio
async def test_ask_returns_record_and_version_id(recruiter_client):
    record_id = await _upload_jd(recruiter_client, _JD_TEXT)
    resp = await recruiter_client.post(
        f"/api/records/{record_id}/ask",
        json={"question": "What experience is required?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["record_id"] == record_id
    assert data["version_id"]


@pytest.mark.asyncio
async def test_ask_is_read_only(recruiter_client):
    """Asking a question must not create a new version."""
    record_id = await _upload_jd(recruiter_client, _JD_TEXT)

    versions_before = (await recruiter_client.get(f"/api/records/{record_id}/versions")).json()

    await recruiter_client.post(
        f"/api/records/{record_id}/ask",
        json={"question": "What skills are needed?"},
    )

    versions_after = (await recruiter_client.get(f"/api/records/{record_id}/versions")).json()
    assert len(versions_before) == len(versions_after), (
        "Asking a question must not create a new JD version"
    )


@pytest.mark.asyncio
async def test_ask_multiple_questions_same_record(recruiter_client):
    """Multiple Q&A calls on the same record must all succeed."""
    record_id = await _upload_jd(recruiter_client, _JD_TEXT)
    questions = [
        "What is the location?",
        "Is remote work mentioned?",
        "What level is this role?",
    ]
    for q in questions:
        resp = await recruiter_client.post(
            f"/api/records/{record_id}/ask",
            json={"question": q},
        )
        assert resp.status_code == 200, f"Failed for question '{q}': {resp.text}"


# ── Validation errors ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ask_empty_question_rejected(recruiter_client):
    record_id = await _upload_jd(recruiter_client, _JD_TEXT)
    resp = await recruiter_client.post(
        f"/api/records/{record_id}/ask",
        json={"question": "   "},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ask_too_long_question_rejected(recruiter_client):
    record_id = await _upload_jd(recruiter_client, _JD_TEXT)
    resp = await recruiter_client.post(
        f"/api/records/{record_id}/ask",
        json={"question": "x" * 501},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_ask_nonexistent_record_returns_404(recruiter_client):
    import uuid
    resp = await recruiter_client.post(
        f"/api/records/{uuid.uuid4()}/ask",
        json={"question": "What is this?"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ask_invalid_record_id_returns_400(recruiter_client):
    resp = await recruiter_client.post(
        "/api/records/not-a-uuid/ask",
        json={"question": "What is this?"},
    )
    assert resp.status_code == 400


# ── Auth ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ask_requires_auth(client):
    # Auth check fires before record lookup, so a random UUID is sufficient
    import uuid as _uuid
    resp = await client.post(
        f"/api/records/{_uuid.uuid4()}/ask",
        json={"question": "What is this?"},
    )
    assert resp.status_code == 401
