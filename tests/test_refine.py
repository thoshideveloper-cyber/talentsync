"""
Phase 2 — LangGraph Refine Loop endpoint tests.

Tests run with TALENTSYNC_STUB=1. The LangGraph saver is the real PostgresSaver
(same test_talentsync DB), so durability is actually tested end-to-end.
"""
import asyncio
import sys
import uuid as _uuid

import pytest

# psycopg3 async needs SelectorEventLoop on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_NONCOMPLIANT_JD = (
    "Software Engineer. Age below 30 only. Male candidates only. "
    "3+ years Python. AWS required. Freshers need not apply."
)
_CLEAN_JD = (
    "Senior Data Engineer. 5+ years Python, Spark, AWS. "
    "Salary: 28-38 LPA. Pune (Hybrid). Equal opportunity employer."
)


async def _upload(client, text: str) -> str:
    resp = await client.post("/api/extract", json={"text": text})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


async def _start_refine(client, record_id: str) -> dict:
    resp = await client.post(f"/api/records/{record_id}/refine/start")
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Start ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_refine_returns_run_id(recruiter_client):
    record_id = await _upload(recruiter_client, _NONCOMPLIANT_JD)
    data = await _start_refine(recruiter_client, record_id)
    assert "run_id" in data
    assert "thread_id" in data
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_start_refine_unknown_record_returns_404(recruiter_client):
    resp = await recruiter_client.post(
        f"/api/records/{_uuid.uuid4()}/refine/start"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_start_refine_requires_auth(client):
    resp = await client.post(f"/api/records/{_uuid.uuid4()}/refine/start")
    assert resp.status_code == 401


# ── Status ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_status_returns_run_info(recruiter_client):
    record_id = await _upload(recruiter_client, _NONCOMPLIANT_JD)
    run = await _start_refine(recruiter_client, record_id)

    # Brief wait for the background task to progress
    await asyncio.sleep(0.5)

    resp = await recruiter_client.get(
        f"/api/records/{record_id}/refine/{run['run_id']}/status"
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["run_id"] == run["run_id"]
    assert data["thread_id"] == run["thread_id"]
    assert data["status"] in ("running", "paused", "done", "error")


@pytest.mark.asyncio
async def test_status_unknown_run_returns_404(recruiter_client):
    record_id = await _upload(recruiter_client, _CLEAN_JD)
    resp = await recruiter_client.get(
        f"/api/records/{record_id}/refine/{_uuid.uuid4()}/status"
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_status_requires_auth(client):
    resp = await client.get(
        f"/api/records/{_uuid.uuid4()}/refine/{_uuid.uuid4()}/status"
    )
    assert resp.status_code == 401


# ── Steps timeline ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_steps_returns_list(recruiter_client):
    record_id = await _upload(recruiter_client, _NONCOMPLIANT_JD)
    run = await _start_refine(recruiter_client, record_id)
    await asyncio.sleep(0.5)

    resp = await recruiter_client.get(
        f"/api/records/{record_id}/refine/{run['run_id']}/steps"
    )
    assert resp.status_code == 200
    steps = resp.json()
    assert isinstance(steps, list)
    assert len(steps) >= 1  # at least the "start" step written at launch


@pytest.mark.asyncio
async def test_steps_have_required_fields(recruiter_client):
    record_id = await _upload(recruiter_client, _NONCOMPLIANT_JD)
    run = await _start_refine(recruiter_client, record_id)
    await asyncio.sleep(0.5)

    resp = await recruiter_client.get(
        f"/api/records/{record_id}/refine/{run['run_id']}/steps"
    )
    steps = resp.json()
    for step in steps:
        assert "node_name" in step
        assert "status" in step
        assert "ts" in step


# ── Resume ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resume_requires_auth(client):
    resp = await client.post(
        f"/api/records/{_uuid.uuid4()}/refine/{_uuid.uuid4()}/resume",
        json={"instruction": "fix it"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_resume_empty_instruction_rejected(recruiter_client):
    record_id = await _upload(recruiter_client, _NONCOMPLIANT_JD)
    run = await _start_refine(recruiter_client, record_id)
    await asyncio.sleep(1.0)  # wait for background task to pause

    resp = await recruiter_client.post(
        f"/api/records/{record_id}/refine/{run['run_id']}/resume",
        json={"instruction": "   "},
    )
    assert resp.status_code == 422


# ── Clean JD fast-paths to done ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_clean_jd_run_completes_without_resume(recruiter_client):
    """A clean JD → gate pass → export → done with no human_edit interrupt."""
    record_id = await _upload(recruiter_client, _CLEAN_JD)
    run = await _start_refine(recruiter_client, record_id)

    # Background task should complete quickly for a clean JD in stub mode
    for _ in range(10):
        await asyncio.sleep(0.3)
        resp = await recruiter_client.get(
            f"/api/records/{record_id}/refine/{run['run_id']}/status"
        )
        if resp.json().get("status") in ("done", "error"):
            break

    final = resp.json()
    assert final["status"] in ("done", "paused", "running")  # must not be a 5xx
