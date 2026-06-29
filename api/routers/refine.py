"""
Phase 2 — LangGraph Refine Loop endpoints.

POST /api/records/{id}/refine/start        → start a refine run
GET  /api/records/{id}/refine/{run_id}/status  → poll status + latest step
POST /api/records/{id}/refine/{run_id}/resume  → provide instruction to resume
GET  /api/records/{id}/refine/{run_id}/steps   → full step timeline

AsyncPostgresSaver is owned in FastAPI lifespan (app.state.langgraph_saver).
Graph is compiled per-request with the app-level saver injected.
"""
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import AgentRun, AgentStep, AuditLog, Job, JDVersion, User, UserRole, VersionSource
from db.session import AsyncSessionLocal
from api.deps import get_db, get_current_user, write_audit
from talentsync.refine_graph import build_refine_graph, RefineState
from api.routers.jobs import _create_version

router = APIRouter(tags=["refine"])


# ── Persist refined JD as a new version ──────────────────────────────────────

async def _persist_refined_jd(
    db: AsyncSession,
    run: AgentRun,
    result: dict,
    original_jd_text: str,
) -> str | None:
    """
    After the graph completes, save the rewritten JD as a new jd_version.
    Returns the new version_id str, or None if nothing changed / error.
    """
    new_text = result.get("jd_text", "")
    if not new_text or new_text.strip() == original_jd_text.strip():
        return None  # no change — nothing to save

    try:
        job_r = await db.execute(
            select(Job)
            .where(Job.id == run.job_id)
            .options(selectinload(Job.current_version))
        )
        job = job_r.scalar_one_or_none()
        if not job:
            return None

        parent_version_id = uuid.UUID(result["version_id"]) if result.get("version_id") else None

        new_version, _ = await _create_version(
            db,
            job=job,
            text=new_text,
            source=VersionSource.REWRITE,
            change_note=result.get("change_note") or "Agentic refine rewrite",
            parent_version_id=parent_version_id,
            created_by=run.actor,
            tenant_id=run.tenant_id,
        )

        await write_audit(
            db,
            actor_id=run.actor,
            action="jd.refine_persisted",
            target_type="job",
            target_id=run.job_id,
            detail={"run_id": str(run.id), "new_version_id": str(new_version.id)},
            tenant_id=run.tenant_id,
        )

        return str(new_version.id)
    except Exception as exc:
        print(f"[refine] Warning: failed to persist refined JD: {exc}")
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_saver(request: Request):
    saver = getattr(request.app.state, "langgraph_saver", None)
    if saver is None:
        raise HTTPException(503, "Refine service not initialised — saver unavailable")
    return saver


async def _load_job_and_version(
    db: AsyncSession, job_uuid: uuid.UUID, tenant_id: str
) -> tuple[Job, JDVersion]:
    result = await db.execute(
        select(Job)
        .where(Job.id == job_uuid, Job.tenant_id == tenant_id)
        .options(selectinload(Job.current_version))
    )
    job = result.scalar_one_or_none()
    if not job or not job.current_version:
        raise HTTPException(404, f"Record '{job_uuid}' not found")
    return job, job.current_version


async def _load_run(
    db: AsyncSession, run_uuid: uuid.UUID, job_uuid: uuid.UUID
) -> AgentRun:
    run_r = await db.execute(
        select(AgentRun).where(AgentRun.id == run_uuid, AgentRun.job_id == job_uuid)
    )
    run = run_r.scalar_one_or_none()
    if not run:
        raise HTTPException(404, f"Run '{run_uuid}' not found")
    return run


# ── Background task: run the graph ───────────────────────────────────────────

async def _run_graph_bg(
    thread_id: str,
    run_id: str,
    initial_state: dict,
    saver,
):
    """Run the graph to first interrupt (or completion) and persist AgentRun/AgentStep."""
    from datetime import datetime, timezone
    import traceback

    async with AsyncSessionLocal() as db:
        run_r = await db.execute(select(AgentRun).where(AgentRun.thread_id == thread_id))
        run = run_r.scalar_one_or_none()
        if not run:
            return

        graph = build_refine_graph(checkpointer=saver)
        config = {"configurable": {"thread_id": thread_id}}

        try:
            result = await graph.ainvoke(initial_state, config=config)
            step_status = result.get("step", "done")
            run_status = "done" if step_status == "done" else "paused"
        except Exception as exc:
            step_status = "error"
            run_status = "error"
            result = {**initial_state, "error": traceback.format_exc()[:500]}

        # If the run completed, persist the refined JD as a new jd_version
        new_version_id: str | None = None
        if run_status == "done":
            new_version_id = await _persist_refined_jd(
                db, run, result, initial_state.get("jd_text", "")
            )

        # Write AgentStep for this invocation
        db.add(AgentStep(
            id=uuid.uuid4(),
            run_id=uuid.UUID(run_id),
            node_name=result.get("step", "unknown"),
            status=step_status if step_status != "error" else "error",
            output_ref={
                "gate_verdict": result.get("gate_verdict"),
                "findings_count": len(result.get("compliance_findings", [])),
                "version_id": result.get("version_id"),
                "new_version_id": new_version_id,
            },
            error=result.get("error"),
        ))

        run.status = run_status
        if run_status in ("done", "error"):
            run.ended_at = datetime.now(timezone.utc)

        await db.commit()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/api/records/{record_id}/refine/start", status_code=201)
async def start_refine(
    record_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        job_uuid = uuid.UUID(record_id)
    except ValueError:
        raise HTTPException(400, "record_id must be a UUID")

    saver = _get_saver(request)
    job, version = await _load_job_and_version(db, job_uuid, user.tenant_id)

    thread_id = str(uuid.uuid4())
    run_id = uuid.uuid4()

    try:
        run = AgentRun(
            id=run_id,
            job_id=job.id,
            thread_id=thread_id,
            status="running",
            actor=user.id,
            tenant_id=user.tenant_id,
        )
        db.add(run)

        db.add(AgentStep(
            id=uuid.uuid4(),
            run_id=run_id,
            node_name="start",
            status="ok",
            input_ref={"job_id": str(job.id), "version_id": str(version.id)},
        ))

        await write_audit(
            db,
            actor_id=user.id,
            action="refine.started",
            target_type="job",
            target_id=job.id,
            detail={"thread_id": thread_id, "run_id": str(run_id)},
            tenant_id=user.tenant_id,
        )
        await db.commit()
    except Exception as exc:
        raise HTTPException(
            503,
            f"Refine service unavailable — database schema not ready. "
            f"Run 'alembic upgrade head' then restart the server. ({type(exc).__name__})"
        ) from exc

    initial_state: RefineState = {
        "job_id": str(job.id),
        "version_id": str(version.id),
        "jd_text": version.raw_jd,
        "compliance_findings": [],
        "gate_verdict": "",
        "pending_instruction": None,
        "change_note": None,
        "export_path": None,
        "step": "draft",
        "error": None,
        "run_id": str(run_id),
        "audit_idempotency_key": None,
    }

    background_tasks.add_task(_run_graph_bg, thread_id, str(run_id), initial_state, saver)

    return {"run_id": str(run_id), "thread_id": thread_id, "status": "running"}


@router.get("/api/records/{record_id}/refine/{run_id}/status")
async def get_refine_status(
    record_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        job_uuid = uuid.UUID(record_id)
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(400, "record_id and run_id must be UUIDs")

    run = await _load_run(db, run_uuid, job_uuid)

    # All steps newest-first. The very latest step is often "start"/"resume"
    # (no gate verdict); for display we prefer the most recent step that
    # actually carries a gate verdict, and we always surface any error.
    steps_r = await db.execute(
        select(AgentStep)
        .where(AgentStep.run_id == run_uuid)
        .order_by(AgentStep.ts.desc())
    )
    steps = steps_r.scalars().all()

    latest_step = steps[0] if steps else None
    # Prefer the newest step whose output_ref has a gate verdict.
    verdict_step = next(
        (s for s in steps if (s.output_ref or {}).get("gate_verdict")),
        latest_step,
    )
    # Surface the newest error step, if any, so the UI never hangs silently.
    error_step = next((s for s in steps if s.status == "error"), None)

    def _step_dict(s):
        if not s:
            return None
        return {
            "node_name": s.node_name,
            "status": s.status,
            "output_ref": s.output_ref,
            "error": s.error,
            "ts": s.ts.isoformat() if s.ts else None,
        }

    # Surface the new_version_id from the most recent done step (if the run completed)
    done_step = next(
        (s for s in steps if (s.output_ref or {}).get("new_version_id")),
        None,
    )
    new_version_id = (done_step.output_ref or {}).get("new_version_id") if done_step else None

    return {
        "run_id": str(run.id),
        "thread_id": run.thread_id,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "latest_step": _step_dict(verdict_step),
        "error": (error_step.error if error_step else None),
        "new_version_id": new_version_id,
    }


class ResumeRequest(BaseModel):
    instruction: str

    @field_validator("instruction")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("instruction must not be empty")
        return v.strip()


@router.post("/api/records/{record_id}/refine/{run_id}/resume")
async def resume_refine(
    record_id: str,
    run_id: str,
    req: ResumeRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        job_uuid = uuid.UUID(record_id)
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(400, "record_id and run_id must be UUIDs")

    saver = _get_saver(request)
    run = await _load_run(db, run_uuid, job_uuid)

    if run.status not in ("paused", "running"):
        raise HTTPException(409, f"Run is '{run.status}' — cannot resume")

    # Capture original JD text for the closure (needed to detect if text changed)
    job_r = await db.execute(
        select(Job)
        .where(Job.id == job_uuid)
        .options(selectinload(Job.current_version))
    )
    _job = job_r.scalar_one_or_none()
    initial_state_jd_text: str = _job.current_version.raw_jd if _job and _job.current_version else ""

    run.status = "running"

    db.add(AgentStep(
        id=uuid.uuid4(),
        run_id=run_uuid,
        node_name="resume",
        status="ok",
        input_ref={"instruction": req.instruction[:200]},
    ))

    await write_audit(
        db,
        actor_id=user.id,
        action="refine.resumed",
        target_type="job",
        target_id=job_uuid,
        detail={"run_id": run_id, "instruction": req.instruction[:200]},
        tenant_id=user.tenant_id,
    )
    await db.commit()

    # Capture original JD text before the background task runs
    original_jd_text_for_resume = initial_state_jd_text

    async def _resume_bg():
        from langgraph.types import Command
        from datetime import datetime, timezone
        import traceback

        async with AsyncSessionLocal() as session:
            run_r = await session.execute(select(AgentRun).where(AgentRun.id == run_uuid))
            bg_run = run_r.scalar_one_or_none()
            if not bg_run:
                return

            graph = build_refine_graph(checkpointer=saver)
            config = {"configurable": {"thread_id": bg_run.thread_id}}

            try:
                result = await graph.ainvoke(Command(resume=req.instruction), config=config)
                step_status = result.get("step", "done")
                run_status = "done" if step_status == "done" else "paused"
            except Exception as exc:
                step_status = "error"
                run_status = "error"
                result = {"step": "error", "error": traceback.format_exc()[:500]}

            # Persist the refined JD if the run completed
            new_version_id: str | None = None
            if run_status == "done":
                new_version_id = await _persist_refined_jd(
                    session, bg_run, result, original_jd_text_for_resume
                )

            session.add(AgentStep(
                id=uuid.uuid4(),
                run_id=run_uuid,
                node_name=result.get("step", "unknown"),
                status=step_status if step_status != "error" else "error",
                output_ref={
                    "gate_verdict": result.get("gate_verdict"),
                    "findings_count": len(result.get("compliance_findings", [])),
                    "new_version_id": new_version_id,
                },
                error=result.get("error"),
            ))

            bg_run.status = run_status
            if run_status in ("done", "error"):
                bg_run.ended_at = datetime.now(timezone.utc)

            await session.commit()

    background_tasks.add_task(_resume_bg)

    return {"run_id": run_id, "status": "running"}


@router.get("/api/records/{record_id}/refine/{run_id}/steps")
async def get_refine_steps(
    record_id: str,
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    try:
        job_uuid = uuid.UUID(record_id)
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(400, "record_id and run_id must be UUIDs")

    await _load_run(db, run_uuid, job_uuid)

    steps_r = await db.execute(
        select(AgentStep)
        .where(AgentStep.run_id == run_uuid)
        .order_by(AgentStep.ts.asc())
    )
    steps = steps_r.scalars().all()
    return [
        {
            "id": str(s.id),
            "node_name": s.node_name,
            "status": s.status,
            "input_ref": s.input_ref,
            "output_ref": s.output_ref,
            "error": s.error,
            "ts": s.ts.isoformat() if s.ts else None,
        }
        for s in steps
    ]
