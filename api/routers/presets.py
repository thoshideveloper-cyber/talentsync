"""
Phase 5 Channel B — Transformation Presets.

Admin-authored, recruiter select-only. Each preset contains a prompt template
that rewrites the current JD into a new jd_version (source=rewrite).

Routes:
  GET    /api/presets               — list active presets (any authenticated user)
  POST   /api/presets               — create a preset (admin only)
  DELETE /api/presets/{id}          — deactivate a preset (admin only)
  POST   /api/records/{id}/transform — apply a preset → new jd_version + compliance check

DONE-WHEN: recruiter selects "Make Compliance-Pass" → gets a new passing version + DOCX.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    AuditLog, ComplianceCheck, CheckResult,
    Job, JDVersion, PromptPreset, User, UserRole, VersionSource,
)
from api.deps import get_db, get_current_user, require_role, write_audit
from talentsync.llm import generate
from talentsync.compliance import (
    run_all_compliance_checks, gate_verdict, count_by_tier, get_risk_tier,
)
from talentsync.prompts import COMPLIANCE_REWRITE_SYSTEM
from api.routers.jobs import _create_version, _version_to_record, _write_compliance_checks

router = APIRouter(tags=["presets"])


# ── Request models ─────────────────────────────────────────────────────────────

class CreatePresetRequest(BaseModel):
    name: str
    kind: str = "transform"
    prompt_text: str

    @field_validator("name", "prompt_text", mode="before")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("field must not be empty")
        return v

    @field_validator("kind")
    @classmethod
    def valid_kind(cls, v: str) -> str:
        if v not in ("transform",):
            raise ValueError("kind must be 'transform'")
        return v


class TransformRequest(BaseModel):
    preset_id: str

    @field_validator("preset_id")
    @classmethod
    def valid_uuid(cls, v: str) -> str:
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("preset_id must be a valid UUID")
        return v


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/api/presets")
async def list_presets(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Return all active presets. Any authenticated user can list."""
    rows = await db.execute(
        select(PromptPreset)
        .where(PromptPreset.active.is_(True))
        .order_by(PromptPreset.created_at.asc())
    )
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "kind": p.kind,
            "active": p.active,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in rows.scalars().all()
    ]


@router.post("/api/presets", status_code=201)
async def create_preset(
    req: CreatePresetRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
) -> dict:
    """Create a new transformation preset. Admin only."""
    preset = PromptPreset(
        name=req.name,
        kind=req.kind,
        prompt_text=req.prompt_text,
        active=True,
        created_by_admin=user.id,
    )
    db.add(preset)
    await db.flush()

    await write_audit(
        db,
        actor_id=user.id,
        action="preset.create",
        target_type="prompt_preset",
        target_id=preset.id,
        detail={"name": req.name, "kind": req.kind},
        tenant_id=user.tenant_id,
    )
    await db.commit()

    return {
        "id": str(preset.id),
        "name": preset.name,
        "kind": preset.kind,
        "active": preset.active,
        "created_at": preset.created_at.isoformat() if preset.created_at else None,
    }


@router.delete("/api/presets/{preset_id}", status_code=200)
async def deactivate_preset(
    preset_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN)),
) -> dict:
    """Soft-delete (deactivate) a preset. Admin only."""
    try:
        preset_uuid = uuid.UUID(preset_id)
    except ValueError:
        raise HTTPException(400, "preset_id must be a UUID")

    row = await db.execute(select(PromptPreset).where(PromptPreset.id == preset_uuid))
    preset = row.scalar_one_or_none()
    if not preset:
        raise HTTPException(404, f"Preset '{preset_id}' not found")
    if not preset.active:
        raise HTTPException(409, f"Preset '{preset_id}' is already inactive")

    preset.active = False
    await write_audit(
        db,
        actor_id=user.id,
        action="preset.deactivate",
        target_type="prompt_preset",
        target_id=preset.id,
        detail={"name": preset.name},
        tenant_id=user.tenant_id,
    )
    await db.commit()
    return {"status": "ok", "id": preset_id, "active": False}


@router.post("/api/records/{record_id}/transform")
async def apply_transform(
    record_id: str,
    req: TransformRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Apply a transformation preset to the current version of a JD.

    1. Load job + current version
    2. Load compliance findings from DB (so the prompt knows what to fix)
    3. Fill the preset's prompt_text with {raw_jd} + {findings}
    4. Call LLM with COMPLIANCE_REWRITE_SYSTEM as the system prompt
    5. Create a new jd_version (source=rewrite, parent=current_version)
    6. Return updated record with inline compliance summary
    """
    try:
        job_uuid = uuid.UUID(record_id)
    except ValueError:
        raise HTTPException(400, "record_id must be a UUID")

    preset_uuid = uuid.UUID(req.preset_id)

    # Load job
    job_r = await db.execute(
        select(Job)
        .where(Job.id == job_uuid, Job.tenant_id == user.tenant_id)
        .options(selectinload(Job.current_version))
    )
    job = job_r.scalar_one_or_none()
    if not job or not job.current_version:
        raise HTTPException(404, f"Record '{record_id}' not found")

    # Load preset
    preset_r = await db.execute(
        select(PromptPreset)
        .where(PromptPreset.id == preset_uuid, PromptPreset.active.is_(True))
    )
    preset = preset_r.scalar_one_or_none()
    if not preset:
        raise HTTPException(404, f"Preset '{req.preset_id}' not found or inactive")

    current_version = job.current_version
    raw_jd = current_version.raw_jd

    # Fetch existing compliance findings for this version to include in the prompt
    checks_r = await db.execute(
        select(ComplianceCheck)
        .where(ComplianceCheck.jd_version_id == job.current_version_id)
        .order_by(ComplianceCheck.checked_at.asc())
    )
    checks = checks_r.scalars().all()
    high_risk = [c for c in checks if get_risk_tier(c.rule_id) == "high_risk"]

    if high_risk:
        findings_str = "\n".join(
            f"- [{c.rule_id}] {c.evidence_span or '(no span)'} — {c.citation or ''}"
            for c in high_risk
        )
    else:
        # No high-risk findings — still run advisory for completeness
        advisory = [c for c in checks if c.rule_id.startswith("language.")]
        if advisory:
            findings_str = "\n".join(
                f"- [{c.rule_id}] {c.evidence_span or '(no span)'}"
                for c in advisory
            )
        else:
            findings_str = "No high-risk compliance issues detected. Apply general inclusive-language improvements if any."

    # Build prompt using the preset's prompt_text as user-side template
    try:
        user_prompt = preset.prompt_text.format(raw_jd=raw_jd, findings=findings_str)
    except KeyError:
        # Preset template doesn't use {raw_jd}/{findings} — append them
        user_prompt = f"{preset.prompt_text}\n\nJD:\n{raw_jd}\n\nIssues:\n{findings_str}"

    rewritten_text = await run_in_threadpool(generate, user_prompt, COMPLIANCE_REWRITE_SYSTEM)
    if not rewritten_text:
        raise HTTPException(
            503,
            "LLM rewrite failed — no API keys available or all quota exhausted.",
        )

    # Create new version (parent = current version, source = rewrite)
    new_version, record = await _create_version(
        db,
        job=job,
        text=rewritten_text,
        source=VersionSource.REWRITE,
        change_note=f"Applied preset: {preset.name}",
        parent_version_id=current_version.id,
        created_by=user.id,
        tenant_id=user.tenant_id,
    )

    await write_audit(
        db,
        actor_id=user.id,
        action="jd.preset_transform",
        target_type="job",
        target_id=job.id,
        detail={
            "preset_id": str(preset.id),
            "preset_name": preset.name,
            "parent_version_id": str(current_version.id),
            "new_version_id": str(new_version.id),
        },
        tenant_id=user.tenant_id,
    )

    # Inline compliance summary for the new version
    findings = run_all_compliance_checks(rewritten_text)
    counts = count_by_tier(findings)

    resp = _version_to_record(job, new_version)
    resp["compliance_summary"] = {
        "verdict": gate_verdict(findings),
        "high_risk_count": counts.get("high_risk", 0),
        "advisory_count": counts.get("advisory", 0),
    }
    resp["transform_meta"] = {
        "preset_id": str(preset.id),
        "preset_name": preset.name,
        "parent_version_id": str(current_version.id),
    }
    return resp
