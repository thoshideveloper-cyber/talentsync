"""
Feature G — Compliance Posture Dashboard.

GET /api/dashboard/posture  — pass rate, top rules, 8-week trend, recent overrides.
All computed from compliance_checks + audit_log; no new tables.
"""
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func as sqlfunc, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AuditLog, ComplianceCheck, JDVersion, Job, User
from api.deps import get_db, get_current_user
from talentsync.compliance import get_risk_tier

router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard/posture")
async def get_posture(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Compliance posture for the calling user's tenant.
    Returns overall pass rate, top 5 triggered rules, 8-week trend, recent overrides.
    """
    tenant_id = user.tenant_id

    # ── All jd_version IDs for this tenant ────────────────────────────────────
    versions_r = await db.execute(
        select(JDVersion.id, JDVersion.created_at)
        .join(Job, JDVersion.job_id == Job.id)
        .where(Job.tenant_id == tenant_id)
    )
    version_rows = versions_r.all()

    if not version_rows:
        return {
            "overall_pass_rate": 1.0,
            "total_versions_checked": 0,
            "top_rules": [],
            "trend": [],
            "recent_overrides": [],
        }

    version_ids = [row[0] for row in version_rows]
    total = len(version_ids)

    # ── High-risk findings per version ────────────────────────────────────────
    checks_r = await db.execute(
        select(ComplianceCheck.jd_version_id, ComplianceCheck.rule_id)
        .where(ComplianceCheck.jd_version_id.in_(version_ids))
    )
    checks = checks_r.all()

    # Pass = version with zero high_risk findings
    high_risk_per_version: dict[uuid.UUID, bool] = {vid: False for vid in version_ids}
    rule_counts: dict[str, int] = {}
    for vid, rule_id in checks:
        tier = get_risk_tier(rule_id)
        if tier == "high_risk":
            high_risk_per_version[vid] = True
        rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1

    passing = sum(1 for has_hr in high_risk_per_version.values() if not has_hr)
    pass_rate = round(passing / total, 4) if total else 1.0

    top_rules = sorted(
        [{"rule_id": k, "count": v} for k, v in rule_counts.items()],
        key=lambda x: -x["count"],
    )[:5]

    # ── 8-week trend ──────────────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    trend = []
    for w in range(7, -1, -1):
        week_start = now - timedelta(weeks=w + 1)
        week_end = now - timedelta(weeks=w)
        week_label = week_start.strftime("%G-W%V")

        week_vids = [
            row[0] for row in version_rows
            if row[1] and week_start <= row[1].replace(tzinfo=timezone.utc) < week_end
        ]
        if not week_vids:
            trend.append({"week": week_label, "pass_rate": None})
            continue

        wk_passing = sum(1 for vid in week_vids if not high_risk_per_version.get(vid, False))
        trend.append({"week": week_label, "pass_rate": round(wk_passing / len(week_vids), 4)})

    # ── Recent overrides ──────────────────────────────────────────────────────
    overrides_r = await db.execute(
        select(AuditLog, User)
        .join(User, AuditLog.actor == User.id)
        .where(
            AuditLog.action == "compliance.override",
            AuditLog.tenant_id == tenant_id,
        )
        .order_by(AuditLog.ts.desc())
        .limit(10)
    )
    recent_overrides = [
        {
            "actor_email": u.email,
            "action": al.action,
            "ts": al.ts.isoformat() if al.ts else None,
            "detail": al.detail,
        }
        for al, u in overrides_r.all()
    ]

    return {
        "overall_pass_rate": pass_rate,
        "total_versions_checked": total,
        "top_rules": top_rules,
        "trend": trend,
        "recent_overrides": recent_overrides,
    }
