"""
Job / JD endpoints — ported off results.json onto Postgres.

Backward-compatible response shape: callers expecting the original JobRecord dict
(id, role, input_format, raw_jd, ...) continue to work. New fields are additive.

Dedup rule: on the fresh UPLOAD path (POST /api/extract) we always create a new job+version.
Intra-job dedup (same content_hash as current version) is enforced on the versioned-upload
route (POST /api/records/{id}/versions) to prevent accidental duplicates within one job.
"""
import csv
import hashlib
import io
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    AuditLog, ComplianceCheck, CheckResult, Job, JDVersion, JobStatus, VersionSource
)
from db.session import AsyncSessionLocal
from api.deps import get_db, get_current_user, require_role, write_audit
from api.docx_builder import build_corrected_jd, build_audit_report
from db.models import User, UserRole
from talentsync.core import process_jd, role_title_from_text
from talentsync.compliance import (
    run_all_compliance_checks,
    gate_verdict,
    count_by_tier,
    get_risk_tier,
    RULE_CATALOGUE,
)

router = APIRouter(tags=["jobs"])


# ── Serialisation helpers ─────────────────────────────────────────────────────

def _version_to_record(job: Job, version: JDVersion) -> dict[str, Any]:
    """Build the backward-compatible JobRecord dict from ORM objects."""
    return {
        "id": str(job.id),
        "role": job.role,
        "input_format": job.input_format,
        "raw_jd": version.raw_jd,
        "one_line_summary": version.summary or "",
        "ai_seniority": version.ai_seniority or "Uncertain",
        "required_skills": version.required_skills or [],
        "raw_text_justification": version.raw_text_justification or "",
        "native_label": version.native_label,
        "is_verified": version.is_verified,
        "audit_mismatch": version.audit_mismatch,
        "bias_flags": version.bias_flags or [],
        "pay_range_present": version.pay_range_present,
        "quality_score": version.quality_score,
        "score_breakdown": version.score_breakdown or [],
        "content_hash": version.content_hash,
        "status": version.status,
        # Additive new fields (frontend ignores unknown keys)
        "version_id": str(version.id),
        "created_at": version.created_at.isoformat() if version.created_at else None,
        "job_status": job.status.value,
    }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def _load_all_records(db: AsyncSession, tenant_id: str) -> list[dict]:
    """Load all jobs with their current versions for this tenant.

    Also attaches initial_version_id / initial_raw_jd when the job has been
    through an AI rewrite (i.e. current_version differs from Phase 1 upload),
    so the frontend can offer a clear Phase-1 vs AI-fixed download split.
    """
    jobs_q = await db.execute(
        select(Job)
        .where(Job.tenant_id == tenant_id, Job.current_version_id.isnot(None))
        .options(selectinload(Job.current_version))
        .order_by(Job.created_at.asc())
    )
    jobs = jobs_q.scalars().all()
    if not jobs:
        return []

    # Load every version for these jobs (one round-trip), keep the first per job.
    job_ids = [j.id for j in jobs]
    all_vers_q = await db.execute(
        select(JDVersion)
        .where(JDVersion.job_id.in_(job_ids))
        .order_by(JDVersion.created_at.asc())
    )
    first_by_job: dict[str, JDVersion] = {}
    for v in all_vers_q.scalars().all():
        key = str(v.job_id)
        if key not in first_by_job:
            first_by_job[key] = v

    result = []
    for j in jobs:
        if not j.current_version:
            continue
        rec = _version_to_record(j, j.current_version)
        initial_v = first_by_job.get(str(j.id))
        if initial_v and str(initial_v.id) != str(j.current_version_id):
            # A rewrite has happened — expose original Phase 1 text to the frontend
            rec["initial_version_id"] = str(initial_v.id)
            rec["initial_raw_jd"] = initial_v.raw_jd
        result.append(rec)
    return result


async def _write_compliance_checks(db: AsyncSession, version_id: uuid.UUID, record: dict) -> None:
    """
    Persist compliance and quality checks for a JD version.

    Compliance checks (from talentsync.compliance): discriminatory filters, inclusive
    language, and pay-disclosure — all keyed by rule_id so the API can return them
    with evidence spans and citations.

    Quality checks: seniority mismatch and unverified seniority are distinct from
    regulatory compliance; they use the quality.* namespace.
    """
    raw_jd = record.get("raw_jd", "")

    # Full compliance scan (deterministic, zero LLM)
    findings = run_all_compliance_checks(raw_jd)
    for f in findings:
        db.add(ComplianceCheck(
            jd_version_id=version_id,
            rule_id=f.rule_id,
            result=CheckResult.WARN,
            evidence_span=f.evidence_span,
            citation=f.citation,
        ))

    # Quality-gate checks (not regulatory compliance)
    if record.get("audit_mismatch", False):
        db.add(ComplianceCheck(
            jd_version_id=version_id,
            rule_id="quality.leveling_mismatch",
            result=CheckResult.WARN,
            evidence_span=(record.get("raw_text_justification") or "")[:256] or None,
            citation=(
                "Title stated level diverges ≥2 tiers from body text signals. "
                "Review before posting."
            ),
        ))

    if not record.get("is_verified", True):
        db.add(ComplianceCheck(
            jd_version_id=version_id,
            rule_id="quality.unverified_seniority",
            result=CheckResult.WARN,
            evidence_span=None,
            citation="LLM seniority call could not be grounded to a quote in the source text.",
        ))


async def _create_version(
    db: AsyncSession,
    *,
    job: Job,
    text: str,
    source: VersionSource,
    change_note: str | None,
    parent_version_id: uuid.UUID | None,
    created_by: uuid.UUID,
    tenant_id: str,
) -> tuple[JDVersion, dict]:
    """
    Create a new JDVersion for an existing Job, update current_version_id, and write
    compliance checks. Shared by the upload, intake-draft, and preset-rewrite paths.
    Returns (version, record_dict).
    """
    content_hash = _sha256(text)
    record = await run_in_threadpool(process_jd, text)

    version = JDVersion(
        job_id=job.id,
        parent_version_id=parent_version_id,
        raw_jd=text,
        content_hash=content_hash,
        summary=record.get("one_line_summary", ""),
        ai_seniority=record.get("ai_seniority", "Uncertain"),
        native_label=record.get("native_label"),
        required_skills=record.get("required_skills", []),
        bias_flags=record.get("bias_flags", []),
        pay_range_present=record.get("pay_range_present", False),
        quality_score=record.get("quality_score", 0),
        score_breakdown=record.get("score_breakdown", []),
        is_verified=record.get("is_verified", False),
        audit_mismatch=record.get("audit_mismatch", False),
        raw_text_justification=record.get("raw_text_justification", ""),
        source=source,
        change_note=change_note,
        status=record.get("status", "ok"),
        created_by=created_by,
        tenant_id=tenant_id,
    )
    db.add(version)
    await db.flush()

    job.current_version_id = version.id
    await db.flush()

    await _write_compliance_checks(db, version.id, record)
    return version, record


async def _create_job_and_version(
    db: AsyncSession,
    *,
    text: str,
    role: str,
    input_format: str,
    source: VersionSource,
    change_note: str | None,
    parent_version_id: uuid.UUID | None,
    created_by: uuid.UUID,
    tenant_id: str,
) -> tuple[Job, JDVersion, dict]:
    """
    Create a new Job + first JDVersion, resolving the circular FK.
    Returns (job, version, record_dict).
    """
    job = Job(
        role=role,
        input_format=input_format,
        created_by=created_by,
        tenant_id=tenant_id,
        current_version_id=None,
        status=JobStatus.ACTIVE,
    )
    db.add(job)
    await db.flush()

    version, record = await _create_version(
        db,
        job=job,
        text=text,
        source=source,
        change_note=change_note,
        parent_version_id=parent_version_id,
        created_by=created_by,
        tenant_id=tenant_id,
    )
    return job, version, record


# ── Request models ─────────────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    text: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/api/records")
async def get_records(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return await _load_all_records(db, user.tenant_id)


@router.get("/api/records/{record_id}")
async def get_record(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        job_uuid = uuid.UUID(record_id)
    except ValueError:
        raise HTTPException(400, "record_id must be a UUID")

    result = await db.execute(
        select(Job)
        .where(Job.id == job_uuid, Job.tenant_id == user.tenant_id)
        .options(selectinload(Job.current_version))
    )
    job = result.scalar_one_or_none()
    if not job or not job.current_version:
        raise HTTPException(404, f"Record '{record_id}' not found")
    rec = _version_to_record(job, job.current_version)

    # Attach initial (Phase 1) text when a rewrite has been applied
    init_q = await db.execute(
        select(JDVersion)
        .where(JDVersion.job_id == job_uuid)
        .order_by(JDVersion.created_at.asc())
        .limit(1)
    )
    initial_v = init_q.scalar_one_or_none()
    if initial_v and str(initial_v.id) != str(job.current_version_id):
        rec["initial_version_id"] = str(initial_v.id)
        rec["initial_raw_jd"] = initial_v.raw_jd

    return rec


@router.get("/api/records/{record_id}/versions")
async def get_versions(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Return all versions for a job, oldest first."""
    try:
        job_uuid = uuid.UUID(record_id)
    except ValueError:
        raise HTTPException(400, "record_id must be a UUID")

    job_r = await db.execute(
        select(Job).where(Job.id == job_uuid, Job.tenant_id == user.tenant_id)
    )
    job = job_r.scalar_one_or_none()
    if not job:
        raise HTTPException(404, f"Record '{record_id}' not found")

    vers_r = await db.execute(
        select(JDVersion)
        .where(JDVersion.job_id == job_uuid)
        .order_by(JDVersion.created_at.asc())
    )
    versions = vers_r.scalars().all()
    return [
        {
            "version_id": str(v.id),
            "parent_version_id": str(v.parent_version_id) if v.parent_version_id else None,
            "content_hash": v.content_hash,
            "source": v.source.value,
            "change_note": v.change_note,
            "ai_seniority": v.ai_seniority,
            "quality_score": v.quality_score,
            "status": v.status,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in versions
    ]


@router.get("/api/records/{record_id}/audit")
async def get_audit(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
) -> list[dict]:
    """Return audit_log rows targeting this job (approver/admin only)."""
    try:
        job_uuid = uuid.UUID(record_id)
    except ValueError:
        raise HTTPException(400, "record_id must be a UUID")

    rows_r = await db.execute(
        select(AuditLog)
        .where(AuditLog.target_id == job_uuid, AuditLog.tenant_id == user.tenant_id)
        .order_by(AuditLog.ts.asc())
    )
    rows = rows_r.scalars().all()
    return [
        {
            "id": str(r.id),
            "actor": str(r.actor),
            "action": r.action,
            "target_type": r.target_type,
            "target_id": str(r.target_id) if r.target_id else None,
            "ts": r.ts.isoformat() if r.ts else None,
            "detail": r.detail,
        }
        for r in rows
    ]


@router.post("/api/extract")
async def extract_jd(
    req: ExtractRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Live LLM call — the only endpoint that calls the model."""
    if not req.text.strip():
        raise HTTPException(400, "text must not be empty")

    job, version, record = await _create_job_and_version(
        db,
        text=req.text,
        role=await run_in_threadpool(role_title_from_text, req.text),
        input_format="paste",
        source=VersionSource.UPLOAD,
        change_note="Initial upload",
        parent_version_id=None,
        created_by=user.id,
        tenant_id=user.tenant_id,
    )

    await write_audit(
        db,
        actor_id=user.id,
        action="jd.upload",
        target_type="job",
        target_id=job.id,
        detail={"content_hash": version.content_hash, "source": "paste"},
        tenant_id=user.tenant_id,
    )

    return _version_to_record(job, version)


@router.post("/api/extract/file")
async def extract_from_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Parse a .txt / .docx / .pdf file and run it through the extraction pipeline."""
    filename = file.filename or "unknown"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    raw = await file.read()

    if ext in ("txt", "md"):
        text = raw.decode("utf-8", errors="replace")
    elif ext == "docx":
        try:
            from docx import Document
            doc = Document(io.BytesIO(raw))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as exc:
            raise HTTPException(400, f"Could not parse .docx: {exc}") from exc
    elif ext == "pdf":
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except ImportError as exc:
            raise HTTPException(
                400, "PDF support requires pdfplumber — run: pip install pdfplumber"
            ) from exc
        except Exception as exc:
            raise HTTPException(400, f"Could not parse .pdf: {exc}") from exc
    else:
        raise HTTPException(
            400, f"Unsupported file type '.{ext}'. Upload a .txt, .docx, or .pdf file."
        )

    text = text.strip()
    if len(text) < 50:
        raise HTTPException(
            400, f"'{filename}' is too short to be a valid JD (< 50 characters after parsing)."
        )

    job, version, record = await _create_job_and_version(
        db,
        text=text,
        role=filename.rsplit(".", 1)[0] if "." in filename else filename,
        input_format="file",
        source=VersionSource.UPLOAD,
        change_note=f"Uploaded from file: {filename}",
        parent_version_id=None,
        created_by=user.id,
        tenant_id=user.tenant_id,
    )

    await write_audit(
        db,
        actor_id=user.id,
        action="jd.upload",
        target_type="job",
        target_id=job.id,
        detail={"content_hash": version.content_hash, "source": "file", "filename": filename},
        tenant_id=user.tenant_id,
    )

    return _version_to_record(job, version)


@router.get("/api/kpis")
async def get_kpis(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Returns counts + fractions for the KPI strip."""
    records = await _load_all_records(db, user.tenant_id)
    n = len(records)

    if n == 0:
        return {
            "total": 0,
            "flagged_for_review": "0 of 0",
            "leveling_flags": "0 of 0",
            "with_pay_range": "0 of 0",
            "verified": "0 of 0",
            "hallucination_note": "pre-filter rate unavailable (post-filter: 0 of 0 skills)",
        }

    flagged = sum(1 for r in records if r.get("bias_flags"))
    level_flags = sum(1 for r in records if r.get("audit_mismatch"))
    with_pay = sum(1 for r in records if r.get("pay_range_present"))
    verified = sum(1 for r in records if r.get("is_verified"))
    total_skills = sum(len(r.get("required_skills", [])) for r in records)

    return {
        "total": n,
        "flagged_for_review": f"{flagged} of {n}",
        "leveling_flags": f"{level_flags} of {n}",
        "with_pay_range": f"{with_pay} of {n}",
        "verified": f"{verified} of {n}",
        "hallucination_note": (
            f"pre-filter rate: see eval.py output; "
            f"post-filter: 0 of {total_skills} skills (by construction)"
        ),
    }


@router.get("/api/skills")
async def get_skills(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    records = await _load_all_records(db, user.tenant_id)
    freq: dict[str, int] = {}
    for rec in records:
        for skill in rec.get("required_skills", []):
            freq[skill] = freq.get(skill, 0) + 1
    return sorted(
        [{"skill": k, "count": v} for k, v in freq.items()],
        key=lambda x: -x["count"],
    )


@router.get("/api/records/{record_id}/docx")
async def download_docx(
    record_id: str,
    version_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    try:
        job_uuid = uuid.UUID(record_id)
    except ValueError:
        raise HTTPException(400, "record_id must be a UUID")

    result = await db.execute(
        select(Job)
        .where(Job.id == job_uuid, Job.tenant_id == user.tenant_id)
        .options(selectinload(Job.current_version))
    )
    job = result.scalar_one_or_none()
    if not job or not job.current_version:
        raise HTTPException(404, f"Record '{record_id}' not found")

    if version_id:
        # Download a specific version (e.g. the Phase 1 original)
        try:
            ver_uuid = uuid.UUID(version_id)
        except ValueError:
            raise HTTPException(400, "version_id must be a UUID")
        ver_r = await db.execute(
            select(JDVersion).where(JDVersion.id == ver_uuid, JDVersion.job_id == job_uuid)
        )
        target_version = ver_r.scalar_one_or_none()
        if not target_version:
            raise HTTPException(404, "Version not found")
        rec = _version_to_record(job, target_version)
    else:
        rec = _version_to_record(job, job.current_version)

    content = build_corrected_jd(rec)

    await write_audit(
        db,
        actor_id=user.id,
        action="jd.docx_download",
        target_type="job",
        target_id=job.id,
        detail={"version_id": str(job.current_version_id)},
        tenant_id=user.tenant_id,
    )

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{record_id}_corrected.docx"'},
    )


@router.post("/api/extract/docx")
async def download_paste_docx(
    req: ExtractRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    result = await extract_jd(req, db=db, user=user)
    content = build_corrected_jd(result)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="corrected_jd.docx"'},
    )


@router.delete("/api/records/{record_id}")
async def delete_record(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Delete a job and all its versions. Admin or the creating user only."""
    try:
        job_uuid = uuid.UUID(record_id)
    except ValueError:
        raise HTTPException(400, "record_id must be a UUID")

    job_r = await db.execute(
        select(Job).where(Job.id == job_uuid, Job.tenant_id == user.tenant_id)
    )
    job = job_r.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Record not found")

    if user.role != UserRole.ADMIN and job.created_by != user.id:
        raise HTTPException(403, "Not authorised to delete this record")

    # Null the circular FK (jobs.current_version_id → jd_versions) before deleting,
    # otherwise the DB-level FK constraint blocks the cascade even with ondelete=CASCADE.
    job.current_version_id = None
    await db.flush()
    await db.delete(job)
    await db.commit()
    return {"deleted": record_id}


@router.get("/api/records/{record_id}/compliance")
async def get_compliance(
    record_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Return all compliance checks for the current version of a job, with gate verdict.
    Evidence spans and citations included so the caller never sees a black box.
    """
    try:
        job_uuid = uuid.UUID(record_id)
    except ValueError:
        raise HTTPException(400, "record_id must be a UUID")

    result = await db.execute(
        select(Job)
        .where(Job.id == job_uuid, Job.tenant_id == user.tenant_id)
        .options(selectinload(Job.current_version))
    )
    job = result.scalar_one_or_none()
    if not job or not job.current_version:
        raise HTTPException(404, f"Record '{record_id}' not found")

    checks_r = await db.execute(
        select(ComplianceCheck)
        .where(ComplianceCheck.jd_version_id == job.current_version_id)
        .order_by(ComplianceCheck.checked_at.asc())
    )
    checks = checks_r.scalars().all()

    serialized = []
    for c in checks:
        tier = get_risk_tier(c.rule_id)
        serialized.append({
            "id": str(c.id),
            "rule_id": c.rule_id,
            "risk_tier": tier,
            "result": c.result.value,
            "evidence_span": c.evidence_span,
            "citation": c.citation,
            "checked_at": c.checked_at.isoformat() if c.checked_at else None,
        })

    high_risk = [s for s in serialized if s["risk_tier"] == "high_risk"]
    verdict = "warn" if high_risk else ("warn" if serialized else "pass")

    return {
        "version_id": str(job.current_version_id),
        "verdict": verdict,
        "high_risk_count": len(high_risk),
        "advisory_count": len(serialized) - len(high_risk),
        "checks": serialized,
    }


class OverrideRequest(BaseModel):
    version_id: str
    justification: str


@router.post("/api/records/{record_id}/compliance/override")
async def compliance_override(
    record_id: str,
    req: OverrideRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.APPROVER, UserRole.ADMIN)),
) -> dict:
    """
    Approver/admin submits a documented override for a compliance warning.
    The justification is written to audit_log (append-only); no check is deleted.
    """
    try:
        job_uuid = uuid.UUID(record_id)
    except ValueError:
        raise HTTPException(400, "record_id must be a UUID")

    try:
        version_uuid = uuid.UUID(req.version_id)
    except ValueError:
        raise HTTPException(400, "version_id must be a UUID")

    justification = req.justification.strip()
    if not justification:
        raise HTTPException(400, "justification must not be empty")

    job_r = await db.execute(
        select(Job).where(Job.id == job_uuid, Job.tenant_id == user.tenant_id)
    )
    if not job_r.scalar_one_or_none():
        raise HTTPException(404, f"Record '{record_id}' not found")

    await write_audit(
        db,
        actor_id=user.id,
        action="compliance.override",
        target_type="jd_version",
        target_id=version_uuid,
        detail={
            "job_id": str(job_uuid),
            "version_id": str(version_uuid),
            "justification": justification,
        },
        tenant_id=user.tenant_id,
    )

    return {
        "status": "ok",
        "action": "compliance.override",
        "job_id": str(job_uuid),
        "version_id": str(version_uuid),
    }


@router.get("/api/records/{record_id}/audit-report")
async def download_audit_report(
    record_id: str,
    format: str = "docx",
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """
    Generate and download a compliance audit report for a job.
    ?format=docx (default) returns a DOCX. ?format=pdf is not yet supported.
    Any authenticated user may download. Findings, methodology, and audit trail included.
    """
    if format not in ("docx",):
        raise HTTPException(422, "Unsupported format. Only 'docx' is currently supported.")

    try:
        job_uuid = uuid.UUID(record_id)
    except ValueError:
        raise HTTPException(400, "record_id must be a UUID")

    result = await db.execute(
        select(Job)
        .where(Job.id == job_uuid, Job.tenant_id == user.tenant_id)
        .options(selectinload(Job.current_version))
    )
    job = result.scalar_one_or_none()
    if not job or not job.current_version:
        raise HTTPException(404, f"Record '{record_id}' not found")

    checks_r = await db.execute(
        select(ComplianceCheck)
        .where(ComplianceCheck.jd_version_id == job.current_version_id)
        .order_by(ComplianceCheck.checked_at.asc())
    )
    checks = checks_r.scalars().all()

    # Audit trail: last 20 log rows for this job, most recent first
    audit_rows_r = await db.execute(
        select(AuditLog, User)
        .join(User, AuditLog.actor == User.id)
        .where(AuditLog.target_id == job_uuid, AuditLog.tenant_id == user.tenant_id)
        .order_by(AuditLog.ts.desc())
        .limit(20)
    )
    audit_trail = [
        {
            "actor_email": u.email,
            "action": al.action,
            "ts": al.ts.isoformat() if al.ts else None,
            "detail": al.detail,
        }
        for al, u in audit_rows_r.all()
    ]

    rec = _version_to_record(job, job.current_version)
    compliance_rows = [
        {
            "rule_id": c.rule_id,
            "risk_tier": get_risk_tier(c.rule_id),
            "result": c.result.value,
            "evidence_span": c.evidence_span,
            "citation": c.citation,
            "checked_at": c.checked_at.isoformat() if c.checked_at else None,
        }
        for c in checks
    ]

    meta = {
        "actor_email": user.email,
        "actor_role": user.role.value,
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "job_id": str(job_uuid),
        "version_id": str(job.current_version_id),
    }

    content = await run_in_threadpool(
        build_audit_report, rec, compliance_rows, meta, audit_trail
    )

    await write_audit(
        db,
        actor_id=user.id,
        action="audit_report.generated",
        target_type="job",
        target_id=job.id,
        detail={"version_id": str(job.current_version_id), "format": format},
        tenant_id=user.tenant_id,
    )

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{record_id}_audit_report.docx"'
        },
    )


@router.get("/api/export.csv")
async def export_csv(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    records = await _load_all_records(db, user.tenant_id)
    if not records:
        raise HTTPException(404, "No records to export")

    output = io.StringIO()
    fieldnames = [
        "id", "role", "input_format", "ai_seniority", "native_label",
        "is_verified", "audit_mismatch", "quality_score",
        "pay_range_present", "required_skills", "bias_flags",
        "one_line_summary", "raw_text_justification", "status", "created_at",
    ]
    writer = csv.DictWriter(
        output, fieldnames=fieldnames, extrasaction="ignore",
        quoting=csv.QUOTE_ALL, lineterminator="\n",
    )
    writer.writeheader()
    for rec in records:
        row = dict(rec)
        row["required_skills"] = ", ".join(rec.get("required_skills", []))
        row["bias_flags"] = ", ".join(rec.get("bias_flags", []))
        for f in ("raw_text_justification", "one_line_summary"):
            if isinstance(row.get(f), str):
                row[f] = " ".join(row[f].split())
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=talentsync_export.csv"},
    )
