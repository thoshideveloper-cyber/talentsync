"""
Feature G — Compliance Posture Dashboard tests.
GET /api/dashboard/posture
"""
import pytest

_HIGH_RISK_JD = (
    "Software Engineer. Age below 30 only. Male candidates only. "
    "3+ years Python. AWS. Salary: 18-25 LPA."
)
_CLEAN_JD = (
    "Senior Data Analyst. 4+ years SQL, Python. "
    "Salary: 15-22 LPA. Mumbai (Hybrid). Equal opportunity employer."
)


async def _upload(client, text: str) -> str:
    resp = await client.post("/api/extract", json={"text": text})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_dashboard_returns_expected_shape(recruiter_client):
    resp = await recruiter_client.get("/api/dashboard/posture")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "overall_pass_rate" in data
    assert "total_versions_checked" in data
    assert "top_rules" in data
    assert "trend" in data
    assert "recent_overrides" in data


@pytest.mark.asyncio
async def test_dashboard_pass_rate_decreases_with_high_risk(recruiter_client):
    """Uploading a high-risk JD should lower the pass rate vs. a clean one."""
    # Upload a clean JD first, get baseline
    await _upload(recruiter_client, _CLEAN_JD)
    resp1 = await recruiter_client.get("/api/dashboard/posture")
    rate_before = resp1.json()["overall_pass_rate"]

    # Upload a high-risk JD
    await _upload(recruiter_client, _HIGH_RISK_JD)
    resp2 = await recruiter_client.get("/api/dashboard/posture")
    rate_after = resp2.json()["overall_pass_rate"]

    # Pass rate must not increase when we add a failing JD
    assert rate_after <= rate_before


@pytest.mark.asyncio
async def test_dashboard_top_rules_sorted_desc(recruiter_client):
    """top_rules must be sorted by count descending."""
    resp = await recruiter_client.get("/api/dashboard/posture")
    rules = resp.json()["top_rules"]
    counts = [r["count"] for r in rules]
    assert counts == sorted(counts, reverse=True)


@pytest.mark.asyncio
async def test_dashboard_trend_has_8_weeks(recruiter_client):
    resp = await recruiter_client.get("/api/dashboard/posture")
    trend = resp.json()["trend"]
    assert len(trend) == 8
    for entry in trend:
        assert "week" in entry
        assert "pass_rate" in entry


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client):
    resp = await client.get("/api/dashboard/posture")
    assert resp.status_code == 401
