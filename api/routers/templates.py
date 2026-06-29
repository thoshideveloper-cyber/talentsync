"""
Feature E — Reusable Compliant Template Library.

GET  /api/templates                     — list compliance-passing jd_versions
POST /api/templates/{version_id}/clone  — clone as a new job+version
"""
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    AuditLog, ComplianceCheck, Job, JDVersion, VersionSource, JobStatus, User
)
from api.deps import get_db, get_current_user, write_audit
from api.routers.jobs import _create_version, _version_to_record
from talentsync.compliance import get_risk_tier

router = APIRouter(tags=["templates"])


async def _is_passing(db: AsyncSession, version_id: uuid.UUID) -> bool:
    """True if the version has zero high_risk compliance findings."""
    checks_r = await db.execute(
        select(ComplianceCheck.rule_id)
        .where(ComplianceCheck.jd_version_id == version_id)
    )
    for (rule_id,) in checks_r.all():
        if get_risk_tier(rule_id) == "high_risk":
            return False
    return True


@router.get("/api/templates")
async def list_templates(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """
    Return compliance-passing jd_versions from UPLOAD, DRAFT, or REWRITE sources.
    Ordered by created_at desc. Paginated via limit/offset.
    """
    versions_r = await db.execute(
        select(JDVersion)
        .join(Job, JDVersion.job_id == Job.id)
        .where(
            Job.tenant_id == user.tenant_id,
            JDVersion.source.in_([
                VersionSource.UPLOAD, VersionSource.DRAFT, VersionSource.REWRITE
            ]),
        )
        .order_by(JDVersion.created_at.desc())
        .offset(offset)
        .limit(limit * 3)  # over-fetch then filter by compliance
        .options(selectinload(JDVersion.job))
        .options(selectinload(JDVersion.creator))
    )
    versions = versions_r.scalars().all()

    results: list[dict] = []
    for v in versions:
        if len(results) >= limit:
            break
        if not await _is_passing(db, v.id):
            continue
        results.append({
            "version_id": str(v.id),
            "job_id": str(v.job_id),
            "role": v.job.role if v.job else "Unknown",
            "ai_seniority": v.ai_seniority or "Uncertain",
            "required_skills": v.required_skills or [],
            "source": v.source.value,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "created_by_email": v.creator.email if v.creator else None,
        })
    return results


@router.post("/api/templates/{version_id}/clone", status_code=201)
async def clone_template(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Clone a compliance-passing version into a new Job+JDVersion.
    Source is set to 'upload' with parent_version_id pointing at the original.
    """
    try:
        version_uuid = uuid.UUID(version_id)
    except ValueError:
        raise HTTPException(400, "version_id must be a UUID")

    # Load the source version + its job (to verify tenant)
    ver_r = await db.execute(
        select(JDVersion)
        .where(JDVersion.id == version_uuid)
        .options(selectinload(JDVersion.job))
    )
    source_version = ver_r.scalar_one_or_none()
    if not source_version or not source_version.job:
        raise HTTPException(404, f"Version '{version_id}' not found")

    if source_version.job.tenant_id != user.tenant_id:
        raise HTTPException(403, "Forbidden")

    if not await _is_passing(db, version_uuid):
        raise HTTPException(422, "Only compliance-passing versions can be cloned as templates")

    # Create new Job
    from db.models import JobStatus
    new_job = Job(
        role=source_version.job.role,
        input_format="template",
        created_by=user.id,
        tenant_id=user.tenant_id,
        current_version_id=None,
        status=JobStatus.ACTIVE,
    )
    db.add(new_job)
    await db.flush()

    # Create new version as a clone
    change_note = (
        f"Cloned from template: {source_version.job.role} "
        f"v{str(version_uuid)[:8]}"
    )
    new_version, record = await _create_version(
        db,
        job=new_job,
        text=source_version.raw_jd,
        source=VersionSource.UPLOAD,
        change_note=change_note,
        parent_version_id=version_uuid,
        created_by=user.id,
        tenant_id=user.tenant_id,
    )

    await write_audit(
        db,
        actor_id=user.id,
        action="template.cloned",
        target_type="job",
        target_id=new_job.id,
        detail={"source_version_id": version_id, "new_job_id": str(new_job.id)},
        tenant_id=user.tenant_id,
    )

    result = _version_to_record(new_job, new_version)
    result["cloned_from_version_id"] = version_id
    return result
