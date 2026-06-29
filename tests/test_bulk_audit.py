"""
Integration tests for the Phase 2 bulk audit endpoints.

Tests:
- POST /api/bulk-audit (JSON)
- POST /api/bulk-audit/files (multipart)
- POST /api/bulk-audit/export.csv
- Auth enforcement
- Response shape: summary + per-JD results
- High-risk detection in batch
"""
import io
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

CLEAN_JD = """
Senior Software Engineer — Backend

We are seeking a Senior Software Engineer with 5+ years experience in Python and AWS.
Salary: 25-40 LPA. Equal opportunity employer. All backgrounds welcome.
"""

HIGH_RISK_JD = """
Marketing Executive

Male candidates only. Age below 30 preferred. Must be single.
3+ years marketing experience. No salary disclosed.
"""

ADVISORY_JD = """
Rockstar Developer

We need a ninja coder with killer instinct and hustler mindset.
Fast-paced startup culture. 3+ years Python.
"""


async def test_bulk_audit_json_returns_summary(recruiter_client: AsyncClient):
    resp = await recruiter_client.post("/api/bulk-audit", json={
        "jds": [
            {"label": "Clean JD", "text": CLEAN_JD},
            {"label": "High Risk JD", "text": HIGH_RISK_JD},
        ]
    })
    assert resp.status_code == 200
    data = resp.json()

    # Top-level shape
    assert data["total"] == 2
    assert "high_risk_jds" in data
    assert "clean_jds" in data
    assert "verdict_summary" in data
    assert "results" in data
    assert len(data["results"]) == 2


async def test_bulk_audit_detects_high_risk(recruiter_client: AsyncClient):
    resp = await recruiter_client.post("/api/bulk-audit", json={
        "jds": [{"label": "High Risk", "text": HIGH_RISK_JD}]
    })
    assert resp.status_code == 200
    data = resp.json()

    assert data["high_risk_jds"] >= 1
    result = data["results"][0]
    assert result["high_risk_count"] >= 1
    assert result["verdict"] == "warn"
    # At least one finding with evidence span
    hr_findings = [f for f in result["findings"] if f["risk_tier"] == "high_risk"]
    assert len(hr_findings) >= 1
    for f in hr_findings:
        assert f["evidence_span"]
        assert f["citation"]
        assert f["rule_id"]


async def test_bulk_audit_clean_jd_passes(recruiter_client: AsyncClient):
    resp = await recruiter_client.post("/api/bulk-audit", json={
        "jds": [{"label": "Clean", "text": CLEAN_JD}]
    })
    assert resp.status_code == 200
    data = resp.json()
    result = data["results"][0]
    assert result["high_risk_count"] == 0
    # Clean JD with pay info should have no high_risk findings
    hr = [f for f in result["findings"] if f["risk_tier"] == "high_risk"]
    assert not hr


async def test_bulk_audit_advisory_flagged(recruiter_client: AsyncClient):
    resp = await recruiter_client.post("/api/bulk-audit", json={
        "jds": [{"label": "Advisory", "text": ADVISORY_JD}]
    })
    assert resp.status_code == 200
    data = resp.json()
    result = data["results"][0]
    assert result["advisory_count"] >= 1
    advisory = [f for f in result["findings"] if f["risk_tier"] == "advisory"]
    assert advisory


async def test_bulk_audit_verdict_summary_string(recruiter_client: AsyncClient):
    resp = await recruiter_client.post("/api/bulk-audit", json={
        "jds": [
            {"label": "A", "text": HIGH_RISK_JD},
            {"label": "B", "text": CLEAN_JD},
            {"label": "C", "text": CLEAN_JD},
        ]
    })
    assert resp.status_code == 200
    data = resp.json()
    # "1 of 3 JDs carry high-risk filters"
    assert "1" in data["verdict_summary"] or "high-risk" in data["verdict_summary"].lower()


async def test_bulk_audit_rules_triggered_map(recruiter_client: AsyncClient):
    resp = await recruiter_client.post("/api/bulk-audit", json={
        "jds": [{"label": "HR", "text": HIGH_RISK_JD}]
    })
    data = resp.json()
    assert "rules_triggered" in data
    assert isinstance(data["rules_triggered"], dict)


async def test_bulk_audit_label_auto_assigned(recruiter_client: AsyncClient):
    resp = await recruiter_client.post("/api/bulk-audit", json={
        "jds": [{"text": CLEAN_JD}]  # no label
    })
    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert result["label"]  # auto-assigned "JD 1"


async def test_bulk_audit_unauthenticated_rejected(client: AsyncClient):
    resp = await client.post("/api/bulk-audit", json={
        "jds": [{"label": "test", "text": CLEAN_JD}]
    })
    assert resp.status_code in (401, 403)


async def test_bulk_audit_empty_jds_rejected(recruiter_client: AsyncClient):
    resp = await recruiter_client.post("/api/bulk-audit", json={"jds": []})
    assert resp.status_code == 422


async def test_bulk_audit_empty_text_rejected(recruiter_client: AsyncClient):
    resp = await recruiter_client.post("/api/bulk-audit", json={
        "jds": [{"label": "empty", "text": "   "}]
    })
    assert resp.status_code == 422


async def test_bulk_audit_export_csv(recruiter_client: AsyncClient):
    resp = await recruiter_client.post("/api/bulk-audit/export.csv", json={
        "jds": [
            {"label": "High Risk", "text": HIGH_RISK_JD},
            {"label": "Clean", "text": CLEAN_JD},
        ]
    })
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    lines = resp.text.strip().split("\n")
    assert len(lines) >= 2  # header + at least one data row
    # Header row
    header = lines[0]
    assert "rule_id" in header
    assert "risk_tier" in header
    assert "evidence_span" in header


async def test_bulk_audit_files_upload(recruiter_client: AsyncClient):
    content = b"Male candidates only. Age below 30. Freshers only. Python experience."
    files = [("files", ("test_jd.txt", io.BytesIO(content), "text/plain"))]
    resp = await recruiter_client.post("/api/bulk-audit/files", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["high_risk_jds"] >= 1
    result = data["results"][0]
    assert result["label"] == "test_jd"


async def test_bulk_audit_files_unauthenticated(client: AsyncClient):
    content = b"Test JD content"
    files = [("files", ("test.txt", io.BytesIO(content), "text/plain"))]
    resp = await client.post("/api/bulk-audit/files", files=files)
    assert resp.status_code in (401, 403)


async def test_bulk_audit_multiple_high_risk_counted(recruiter_client: AsyncClient):
    """3 high-risk JDs out of 4 → high_risk_jds = 3."""
    resp = await recruiter_client.post("/api/bulk-audit", json={
        "jds": [
            {"label": "HR1", "text": "Male candidates only. Age below 30."},
            {"label": "HR2", "text": "Freshers only. Must be unmarried."},
            {"label": "HR3", "text": "Brahmin candidates preferred."},
            {"label": "Clean", "text": CLEAN_JD},
        ]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["high_risk_jds"] == 3
    assert data["clean_jds"] >= 1
