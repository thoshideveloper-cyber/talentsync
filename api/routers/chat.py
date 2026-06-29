"""
Phase 5 Channel A2 — Grounded Q&A over the active JD.

READ-ONLY BY CONSTRUCTION: this router has no write access to jd_versions or jobs.
The LLM is given only the raw_jd text and instructed to answer from that text alone,
falling back to "Not stated in this JD." for absent information.

Route:
  POST /api/records/{id}/ask — question → grounded answer
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import Job, User
from api.deps import get_db, get_current_user, write_audit
from talentsync.llm import generate
from talentsync.prompts import QA_SYSTEM, QA_USER_TEMPLATE

router = APIRouter(tags=["chat"])

_NOT_IN_JD_MARKER = "not stated in this jd"


class AskRequest(BaseModel):
    question: str

    @field_validator("question", mode="before")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must not be empty")
        if len(v) > 500:
            raise ValueError("question must be ≤ 500 characters")
        return v


@router.post("/api/records/{record_id}/ask")
async def ask_about_jd(
    record_id: str,
    req: AskRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Answer a question grounded strictly to the raw JD text.

    READ-ONLY — no DB writes to jobs or versions. Audit log entry is written
    so questions are traceable but the JD itself is never modified.

    Returns:
      answer     — LLM answer, grounded to JD text only
      not_in_jd  — True when the answer is the standard "Not stated in this JD." fallback
    """
    try:
        job_uuid = uuid.UUID(record_id)
    except ValueError:
        raise HTTPException(400, "record_id must be a UUID")

    job_r = await db.execute(
        select(Job)
        .where(Job.id == job_uuid, Job.tenant_id == user.tenant_id)
        .options(selectinload(Job.current_version))
    )
    job = job_r.scalar_one_or_none()
    if not job or not job.current_version:
        raise HTTPException(404, f"Record '{record_id}' not found")

    raw_jd = job.current_version.raw_jd
    prompt = QA_USER_TEMPLATE.format(raw_jd=raw_jd, question=req.question)

    answer = await run_in_threadpool(generate, prompt, QA_SYSTEM)
    if not answer:
        raise HTTPException(
            503,
            "LLM unavailable — no API keys configured or all quota exhausted.",
        )

    not_in_jd = _NOT_IN_JD_MARKER in answer.lower()

    await write_audit(
        db,
        actor_id=user.id,
        action="jd.qa_ask",
        target_type="job",
        target_id=job.id,
        detail={
            "question": req.question[:200],
            "not_in_jd": not_in_jd,
            "version_id": str(job.current_version_id),
        },
        tenant_id=user.tenant_id,
    )

    return {
        "answer": answer,
        "not_in_jd": not_in_jd,
        "record_id": str(job.id),
        "version_id": str(job.current_version_id),
    }
