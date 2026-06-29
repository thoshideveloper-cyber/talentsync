"""
Batch auto-fix: apply the compliance-pass preset to many JDs in one click.

POST /api/bulk-autofix              — start a batch, returns batch_id immediately
GET  /api/bulk-autofix/{batch_id}   — poll progress + per-record results

Architecture:
- Batch state is stored in an in-memory dict (single-process dev server).
- Each record is processed sequentially in a FastAPI BackgroundTask.
- The same LLM + _create_version logic as the single-record /transform endpoint
  is reused — no duplication of the rewrite pipeline.
- The "Make Compliance-Pass" preset is auto-selected if no preset_id is provided.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import ComplianceCheck, Job, PromptPreset, User, VersionSource
from db.session import AsyncSessionLocal
from api.deps import get_db, get_current_user, write_audit
from talentsync.llm import generate
from talentsync.compliance import (
    run_all_compliance_checks, gate_verdict, count_by_tier, get_risk_tier,
)
from talentsync.prompts import COMPLIANCE_REWRITE_SYSTEM
from api.routers.jobs import _create_version, _version_to_record

router = APIRouter(tags=["bulk-autofix"])

# ── In-memory batch state (keyed by batch_id str) ────────────────────────────

_batches: dict[str, dict[str, Any]] = {}


class BulkAutofixRequest(BaseModel):
    record_ids: list[str]
    preset_id: str | None = None


# ── Core single-record transform (shared logic) ───────────────────────────────

async def _transform_one(
    *,
    record_id: str,
    preset: PromptPreset,
    user_id: uuid.UUID,
    tenant_id: str,
) -> dict[str, Any]:
    """Apply preset to one record. Returns result dict or raises on failure."""
    async with AsyncSessionLocal() as db:
        job_r = await db.execute(
            select(Job)
            .where(Job.id == uuid.UUID(record_id), Job.tenant_id == tenant_id)
            .options(selectinload(Job.current_version))
        )
        job = job_r.scalar_one_or_none()
        if not job or not job.current_version:
            raise ValueError(f"Record '{record_id}' not found")

        current_version = job.current_version
        raw_jd = current_version.raw_jd

        checks_r = await db.execute(
            select(ComplianceCheck)
            .where(ComplianceCheck.jd_version_id == job.current_version_id)
        )
        checks = checks_r.scalars().all()
        high_risk = [c for c in checks if get_risk_tier(c.rule_id) == "high_risk"]

        if high_risk:
            findings_str = "\n".join(
                f"- [{c.rule_id}] {c.evidence_span or '(no span)'}"
                for c in high_risk
            )
        else:
            findings_str = "No high-risk compliance issues detected. Apply general inclusive-language improvements."

        try:
            user_prompt = preset.prompt_text.format(raw_jd=raw_jd, findings=findings_str)
        except KeyError:
            user_prompt = f"{preset.prompt_text}\n\nJD:\n{raw_jd}\n\nIssues:\n{findings_str}"

        rewritten_text = await run_in_threadpool(generate, user_prompt, COMPLIANCE_REWRITE_SYSTEM)
        if not rewritten_text:
            raise ValueError("LLM returned no output")

        new_version, record = await _create_version(
            db,
            job=job,
            text=rewritten_text,
            source=VersionSource.REWRITE,
            change_note=f"Batch auto-fix: {preset.name}",
            parent_version_id=current_version.id,
            created_by=user_id,
            tenant_id=tenant_id,
        )

        await write_audit(
            db,
            actor_id=user_id,
            action="jd.bulk_autofix",
            target_type="job",
            target_id=job.id,
            detail={"preset_name": preset.name, "new_version_id": str(new_version.id)},
            tenant_id=tenant_id,
        )

        findings = run_all_compliance_checks(rewritten_text)
        counts = count_by_tier(findings)
        return {
            "record_id": record_id,
            "role": job.role,
            "new_verdict": gate_verdict(findings),
            "high_risk_count": counts.get("high_risk", 0),
            "advisory_count": counts.get("advisory", 0),
            "new_version_id": str(new_version.id),
        }


# ── Background batch task ─────────────────────────────────────────────────────

async def _run_batch(
    batch_id: str,
    record_ids: list[str],
    preset: PromptPreset,
    user_id: uuid.UUID,
    tenant_id: str,
) -> None:
    state = _batches[batch_id]

    for record_id in record_ids:
        # Find and update item state
        item = next((i for i in state["items"] if i["record_id"] == record_id), None)
        if item:
            item["status"] = "processing"

        try:
            result = await _transform_one(
                record_id=record_id,
                preset=preset,
                user_id=user_id,
                tenant_id=tenant_id,
            )
            if item:
                item["status"] = "done"
                item["new_verdict"] = result["new_verdict"]
                item["high_risk_count"] = result["high_risk_count"]
                item["advisory_count"] = result["advisory_count"]
                item["new_version_id"] = result.get("new_version_id")
            state["completed"] += 1
        except Exception as exc:
            if item:
                item["status"] = "error"
                item["error"] = str(exc)[:200]
            state["failed"] += 1

    state["status"] = "done"
    state["ended_at"] = datetime.now(timezone.utc).isoformat()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/api/bulk-autofix", status_code=202)
async def start_bulk_autofix(
    req: BulkAutofixRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    if not req.record_ids:
        raise HTTPException(400, "record_ids must not be empty")
    if len(req.record_ids) > 50:
        raise HTTPException(400, "Maximum 50 records per batch")

    # Resolve preset: explicit ID or first active preset
    if req.preset_id:
        try:
            preset_uuid = uuid.UUID(req.preset_id)
        except ValueError:
            raise HTTPException(400, "preset_id must be a UUID")
        preset_r = await db.execute(
            select(PromptPreset).where(
                PromptPreset.id == preset_uuid,
                PromptPreset.active.is_(True),
            )
        )
    else:
        preset_r = await db.execute(
            select(PromptPreset).where(PromptPreset.active.is_(True)).limit(1)
        )

    preset = preset_r.scalar_one_or_none()
    if not preset:
        raise HTTPException(
            404,
            "No active preset found. An admin must create a 'Make Compliance-Pass' preset first.",
        )

    batch_id = str(uuid.uuid4())
    _batches[batch_id] = {
        "id": batch_id,
        "status": "running",
        "total": len(req.record_ids),
        "completed": 0,
        "failed": 0,
        "preset_name": preset.name,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
        "items": [
            {"record_id": rid, "status": "pending", "new_verdict": None,
             "high_risk_count": None, "advisory_count": None, "error": None}
            for rid in req.record_ids
        ],
    }

    background_tasks.add_task(
        _run_batch, batch_id, req.record_ids, preset, user.id, user.tenant_id
    )

    return {"batch_id": batch_id, "status": "running", "total": len(req.record_ids)}


@router.get("/api/bulk-autofix/{batch_id}")
async def get_bulk_autofix_status(
    batch_id: str,
    user: User = Depends(get_current_user),
) -> dict:
    state = _batches.get(batch_id)
    if not state:
        raise HTTPException(404, f"Batch '{batch_id}' not found")
    return state
