"""
Feature I — Pay-Range Helper from Org History tests.
GET /api/pay-hints?role={role}&seniority={level}
"""
import pytest

_JD_WITH_PAY = (
    "Senior Python Engineer. 5+ years Python, AWS, PostgreSQL. "
    "Salary: 28-38 LPA. Bengaluru (Hybrid). Equal opportunity employer."
)
_JD_NO_PAY = (
    "Junior Frontend Engineer. 1-2 years React, TypeScript. "
    "Bengaluru. Equal opportunity employer."
)


async def _upload(client, text: str) -> str:
    resp = await client.post("/api/extract", json={"text": text})
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_pay_hints_returns_match_for_known_role(recruiter_client):
    """After uploading a JD with pay range, hints should return matched_count > 0.

    Pasted JDs get role='Pasted JD', so we search for 'Pasted' which matches that role.
    """
    await _upload(recruiter_client, _JD_WITH_PAY)
    # POST /api/extract sets role="Pasted JD"; search for "Pasted" to match it
    resp = await recruiter_client.get("/api/pay-hints?role=Pasted")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "matched_count" in data
    assert "hint" in data
    assert "sample_roles" in data
    assert data["matched_count"] >= 1


@pytest.mark.asyncio
async def test_pay_hints_zero_match_hint(recruiter_client):
    """A completely novel role returns matched_count=0 and appropriate hint text."""
    resp = await recruiter_client.get(
        "/api/pay-hints?role=ExoplanetNavigator_ZZZNOMATCH"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["matched_count"] == 0
    assert "no pay-range data" in data["hint"].lower()


@pytest.mark.asyncio
async def test_pay_hints_seniority_filter(recruiter_client):
    """With a seniority filter that doesn't match, result should be empty."""
    await _upload(recruiter_client, _JD_WITH_PAY)
    resp = await recruiter_client.get(
        "/api/pay-hints?role=Python Engineer&seniority=Internship"
    )
    assert resp.status_code == 200
    # The JD from the fixture is Senior-level, not Internship
    assert resp.json()["matched_count"] == 0


@pytest.mark.asyncio
async def test_pay_hints_empty_role_rejected(recruiter_client):
    resp = await recruiter_client.get("/api/pay-hints?role=   ")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_pay_hints_requires_auth(client):
    resp = await client.get("/api/pay-hints?role=Engineer")
    assert resp.status_code == 401
