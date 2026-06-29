"""
Bulk compliance audit endpoints — Phase 2 Feature F.

POST /api/bulk-audit           — accepts JSON list of JD texts
POST /api/bulk-audit/files     — accepts multipart file upload (txt / docx / pdf)
POST /api/bulk-audit/export.csv — same as /api/bulk-audit but returns CSV

All endpoints run the deterministic compliance detectors only (no LLM, no DB write).
Auth required (any authenticated user).
"""
from __future__ import annotations

import csv
import io
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from api.deps import get_current_user, write_audit, get_db
from db.models import User
from talentsync.compliance import (
    run_all_compliance_checks,
    gate_verdict,
    count_by_tier,
    RULE_CATALOGUE,
)

router = APIRouter(tags=["bulk-audit"])

# ── Request / response models ─────────────────────────────────────────────────

class BulkJd(BaseModel):
    label: str = ""
    text: str

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("JD text must not be empty")
        return v


class BulkAuditRequest(BaseModel):
    jds: list[BulkJd]

    @field_validator("jds")
    @classmethod
    def jds_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("jds list must contain at least one entry")
        if len(v) > 500:
            raise ValueError("Maximum 500 JDs per batch")
        return v


# ── Core audit logic (sync, runs in threadpool) ───────────────────────────────

def _audit_one(index: int, label: str, text: str) -> dict[str, Any]:
    findings = run_all_compliance_checks(text)
    counts = count_by_tier(findings)
    return {
        "index": index,
        "label": label or f"JD {index + 1}",
        "verdict": gate_verdict(findings),
        "high_risk_count": counts["high_risk"],
        "advisory_count": counts["advisory"],
        "findings": [
            {
                "rule_id": f.rule_id,
                "risk_tier": f.risk_tier,
                "result": f.result,
                "evidence_span": f.evidence_span,
                "citation": f.citation,
            }
            for f in findings
        ],
    }


def _build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    high_risk_jds = sum(1 for r in results if r["high_risk_count"] > 0)
    advisory_jds = sum(1 for r in results if r["advisory_count"] > 0 and r["high_risk_count"] == 0)
    clean_jds = sum(1 for r in results if r["high_risk_count"] == 0 and r["advisory_count"] == 0)
    at_risk_jds = total - clean_jds

    # Rule frequency across all JDs
    rules_triggered: dict[str, int] = {}
    for r in results:
        seen_rules: set[str] = set()
        for f in r["findings"]:
            base_rule = f["rule_id"].split(".")[0] + "." + f["rule_id"].split(".")[1] \
                if f["rule_id"].count(".") >= 2 else f["rule_id"]
            if base_rule not in seen_rules:
                seen_rules.add(base_rule)
                rules_triggered[base_rule] = rules_triggered.get(base_rule, 0) + 1

    if high_risk_jds == 0:
        verdict_summary = f"All {total} JD{'s' if total != 1 else ''} passed the high-risk filter check"
    elif high_risk_jds == total:
        verdict_summary = (
            f"All {total} JD{'s' if total != 1 else ''} carry high-risk filters — review required"
        )
    else:
        verdict_summary = (
            f"{high_risk_jds} of {total} JD{'s' if total != 1 else ''} "
            f"carry high-risk filters — immediate review recommended"
        )

    return {
        "total": total,
        "high_risk_jds": high_risk_jds,
        "advisory_only_jds": advisory_jds,
        "clean_jds": clean_jds,
        "at_risk_jds": at_risk_jds,
        "rules_triggered": rules_triggered,
        "verdict_summary": verdict_summary,
        "results": results,
    }


def _run_batch(jds: list[BulkJd]) -> dict[str, Any]:
    results = [_audit_one(i, jd.label, jd.text) for i, jd in enumerate(jds)]
    return _build_summary(results)


# ── CSV builder ───────────────────────────────────────────────────────────────

def _to_csv(summary: dict[str, Any]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow([
        "index", "label", "verdict", "high_risk_count", "advisory_count",
        "rule_id", "risk_tier", "evidence_span",
    ])
    for r in summary["results"]:
        if r["findings"]:
            for f in r["findings"]:
                writer.writerow([
                    r["index"],
                    r["label"],
                    r["verdict"],
                    r["high_risk_count"],
                    r["advisory_count"],
                    f["rule_id"],
                    f["risk_tier"],
                    (f["evidence_span"] or "").replace("\n", " "),
                ])
        else:
            writer.writerow([
                r["index"], r["label"], r["verdict"],
                r["high_risk_count"], r["advisory_count"],
                "", "", "",
            ])
    return buf.getvalue()


# ── File parser (reused from jobs.py logic) ───────────────────────────────────

async def _parse_upload(file: UploadFile) -> str:
    filename = file.filename or "unknown"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    raw = await file.read()

    if ext in ("txt", "md"):
        return raw.decode("utf-8", errors="replace").strip()
    elif ext == "docx":
        try:
            import io as _io
            from docx import Document
            doc = Document(_io.BytesIO(raw))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
        except Exception as exc:
            raise HTTPException(400, f"Could not parse {filename!r}: {exc}") from exc
    elif ext == "pdf":
        try:
            import io as _io
            import pdfplumber
            with pdfplumber.open(_io.BytesIO(raw)) as pdf:
                return "\n".join(
                    page.extract_text() or "" for page in pdf.pages
                ).strip()
        except ImportError as exc:
            raise HTTPException(
                400, "PDF support requires pdfplumber — run: pip install pdfplumber"
            ) from exc
        except Exception as exc:
            raise HTTPException(400, f"Could not parse {filename!r}: {exc}") from exc
    else:
        raise HTTPException(
            400,
            f"Unsupported file type '.{ext}' in '{filename}'. "
            "Upload .txt, .docx, or .pdf files.",
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/api/bulk-audit")
async def bulk_audit_json(
    req: BulkAuditRequest,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Batch compliance scan from JSON.
    Accepts up to 500 JDs as {"jds": [{"label": "...", "text": "..."}, ...]}.
    Returns executive summary + per-JD findings. No LLM calls; no DB write.
    """
    summary = await run_in_threadpool(_run_batch, req.jds)

    await write_audit(
        db,
        actor_id=user.id,
        action="compliance.bulk_audit",
        target_type=None,
        target_id=None,
        detail={
            "total": summary["total"],
            "high_risk_jds": summary["high_risk_jds"],
            "source": "json",
        },
        tenant_id=user.tenant_id,
    )

    return summary


@router.post("/api/bulk-audit/files")
async def bulk_audit_files(
    files: list[UploadFile] = File(...),
    db=Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Batch compliance scan from file uploads.
    Each file (txt / docx / pdf) is one JD. Up to 500 files per request.
    Returns executive summary + per-JD findings.
    """
    if not files:
        raise HTTPException(400, "No files uploaded")
    if len(files) > 500:
        raise HTTPException(400, "Maximum 500 files per batch")

    jds: list[BulkJd] = []
    for f in files:
        text = await _parse_upload(f)
        label = (f.filename or "").rsplit(".", 1)[0] if f.filename else f"File {len(jds)+1}"
        if len(text) < 20:
            raise HTTPException(
                400, f"File '{f.filename}' is too short to be a valid JD."
            )
        jds.append(BulkJd(label=label, text=text))

    summary = await run_in_threadpool(_run_batch, jds)

    await write_audit(
        db,
        actor_id=user.id,
        action="compliance.bulk_audit",
        target_type=None,
        target_id=None,
        detail={
            "total": summary["total"],
            "high_risk_jds": summary["high_risk_jds"],
            "source": "files",
        },
        tenant_id=user.tenant_id,
    )

    return summary


@router.post("/api/bulk-audit/export.csv")
async def bulk_audit_export_csv(
    req: BulkAuditRequest,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Same batch scan as /api/bulk-audit but returns a CSV file directly.
    One row per finding; JDs with no findings get a single clean row.
    """
    summary = await run_in_threadpool(_run_batch, req.jds)
    csv_text = _to_csv(summary)

    await write_audit(
        db,
        actor_id=user.id,
        action="compliance.bulk_audit_export",
        target_type=None,
        target_id=None,
        detail={"total": summary["total"], "high_risk_jds": summary["high_risk_jds"]},
        tenant_id=user.tenant_id,
    )

    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bulk_compliance_audit.csv"},
    )
