"""
Phase 3 — JD Intake → Compliant First Draft.

Guided intake form (role, level, must-haves, location, pay band) → LLM draft →
Phase 1 compliance engine → saved as jd_version (source=draft).

DONE-WHEN: recruiter answers the intake form and gets a versioned, compliance-passing
first draft with a compliance summary.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, VersionSource
from api.deps import get_db, get_current_user, write_audit
from talentsync.llm import generate
from talentsync.compliance import run_all_compliance_checks, gate_verdict, count_by_tier
from talentsync.prompts import INTAKE_SYSTEM, INTAKE_USER_TEMPLATE
from api.routers.jobs import _create_job_and_version, _version_to_record

router = APIRouter(tags=["intake"])

_VALID_LEVELS = {"Internship", "Entry-Level", "Mid-Level", "Senior", "Executive"}


class IntakeRequest(BaseModel):
    role: str
    level: str
    must_haves: list[str]
    location: str
    pay_band: str
    notes: str = ""

    @field_validator("role", "level", "location", "pay_band", mode="before")
    @classmethod
    def strip_required(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("field must not be empty")
        return v

    @field_validator("level")
    @classmethod
    def valid_level(cls, v: str) -> str:
        if v not in _VALID_LEVELS:
            raise ValueError(f"level must be one of {sorted(_VALID_LEVELS)}")
        return v

    @field_validator("must_haves")
    @classmethod
    def must_haves_not_empty(cls, v: list[str]) -> list[str]:
        v = [s.strip() for s in v if s.strip()]
        if not v:
            raise ValueError("must_haves must contain at least one non-empty item")
        return v


@router.post("/api/intake")
async def intake_draft(
    req: IntakeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Generate a compliance-passing JD first draft from a guided intake form.

    1. Build prompt from intake fields
    2. Call LLM to generate draft JD text
    3. Run the extraction + compliance pipeline (same as upload)
    4. Persist as a new job + jd_version (source=draft)
    5. Return record with inline compliance summary
    """
    prompt = INTAKE_USER_TEMPLATE.format(
        role=req.role,
        level=req.level,
        must_haves=", ".join(req.must_haves),
        location=req.location,
        pay_band=req.pay_band,
        notes=req.notes.strip() or "None",
    )

    draft_text = await run_in_threadpool(generate, prompt, INTAKE_SYSTEM)
    if not draft_text:
        raise HTTPException(
            503,
            "LLM generation failed — no API keys available or all quota exhausted. "
            "Set at least one GOOGLE_API_KEY or GROQ_API_KEY in .env.",
        )

    job, version, record = await _create_job_and_version(
        db,
        text=draft_text,
        role=req.role,
        input_format="intake",
        source=VersionSource.DRAFT,
        change_note=f"Intake draft: {req.level} · {req.location} · {req.pay_band}",
        parent_version_id=None,
        created_by=user.id,
        tenant_id=user.tenant_id,
    )

    await write_audit(
        db,
        actor_id=user.id,
        action="jd.intake_draft",
        target_type="job",
        target_id=job.id,
        detail={
            "role": req.role,
            "level": req.level,
            "location": req.location,
            "pay_band": req.pay_band,
            "version_id": str(version.id),
        },
        tenant_id=user.tenant_id,
    )

    # Inline compliance summary (detectors re-run on the draft text; no extra DB round-trip)
    findings = run_all_compliance_checks(draft_text)
    counts = count_by_tier(findings)

    resp = _version_to_record(job, version)
    resp["compliance_summary"] = {
        "verdict": gate_verdict(findings),
        "high_risk_count": counts.get("high_risk", 0),
        "advisory_count": counts.get("advisory", 0),
    }
    resp["intake_meta"] = {
        "level": req.level,
        "location": req.location,
        "pay_band": req.pay_band,
        "must_haves": req.must_haves,
    }
    return resp
