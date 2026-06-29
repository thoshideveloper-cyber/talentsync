"""
Feature I — Pay-Range Helper from Org History.

GET /api/pay-hints?role={role}&seniority={level}

Queries jd_versions WHERE pay_range_present=True AND tenant_id=user.tenant_id,
ILIKE-matches on role text + optional seniority filter.
Returns: matched_count, sample_roles, hint string.
No external benchmark data — org history only.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import JDVersion, Job, User
from api.deps import get_db, get_current_user

router = APIRouter(tags=["pay-hints"])


@router.get("/api/pay-hints")
async def get_pay_hints(
    role: str,
    seniority: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Returns a pay-range hint derived from the organisation's own past JDs.
    """
    role_stripped = role.strip()
    if not role_stripped:
        raise HTTPException(422, "role must not be empty")

    query = (
        select(JDVersion)
        .join(Job, JDVersion.job_id == Job.id)
        .where(
            JDVersion.pay_range_present.is_(True),
            Job.tenant_id == user.tenant_id,
            Job.role.ilike(f"%{role_stripped}%"),
        )
        .options(selectinload(JDVersion.job))
        .limit(20)
    )
    if seniority and seniority.strip():
        query = query.where(JDVersion.ai_seniority == seniority.strip())

    versions_r = await db.execute(query)
    versions = versions_r.scalars().all()

    matched_count = len(versions)
    sample_roles = list({v.job.role for v in versions if v.job})[:5]

    if matched_count == 0:
        hint = (
            "No pay-range data in your JD history for this role yet. "
            "Adding a compensation band improves candidate response rates."
        )
    else:
        hint = (
            f"Based on {matched_count} of your past JDs for similar roles, "
            f"{matched_count} included a pay range. "
            "Consider adding a compensation band to improve candidate response rates."
        )

    return {
        "matched_count": matched_count,
        "sample_roles": sample_roles,
        "hint": hint,
    }
