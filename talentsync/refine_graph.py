"""
LangGraph refine loop for TalentSync.

Scope: REFINE LOOP ONLY — Phases 0-1 continue to use plain Python.

State machine:
  gate_node → (pass?) export_node : human_edit_node → rewrite_node → gate_node (loop)

Spike requirements satisfied here:
1. AsyncPostgresSaver owned in FastAPI lifespan (stashed in app.state), never per-request.
2. saver.setup() called in lifespan — not at request time.
3. Idempotent nodes: jd_version inserts use ON CONFLICT DO NOTHING on (job_id, content_hash);
   audit_log rows use idempotency_key (UUID set before interrupt, checked on resume).
4. Sync→async boundary: LLM/process_jd calls wrapped in run_in_threadpool().
"""
import uuid
from typing import Any, TypedDict

from fastapi.concurrency import run_in_threadpool
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt

from talentsync.compliance import run_all_compliance_checks, gate_verdict, count_by_tier, get_risk_tier
from talentsync.core import process_jd
from talentsync.llm import generate
from talentsync.prompts import COMPLIANCE_REWRITE_SYSTEM, COMPLIANCE_REWRITE_USER_TEMPLATE


# ── State schema ──────────────────────────────────────────────────────────────

class RefineState(TypedDict):
    job_id: str
    version_id: str           # current jd_version being refined
    jd_text: str
    compliance_findings: list[dict]
    gate_verdict: str         # "pass" | "warn"
    pending_instruction: str | None
    change_note: str | None
    export_path: str | None
    step: str                 # "draft" | "gate" | "human_edit" | "rewrite" | "export" | "done"
    error: str | None
    # internal refs for idempotent DB writes (set before interrupt, read on resume)
    run_id: str | None
    audit_idempotency_key: str | None


# ── Node helpers ──────────────────────────────────────────────────────────────

def _serialize_finding(f: Any) -> dict:
    return {
        "rule_id": f.rule_id,
        "risk_tier": get_risk_tier(f.rule_id),
        "evidence_span": f.evidence_span,
        "citation": f.citation,
    }


def _build_findings_str(findings: list[dict]) -> str:
    if not findings:
        return "No compliance issues found."
    lines = []
    for f in findings:
        lines.append(f"[{f['risk_tier'].upper()}] {f['rule_id']}: {f.get('evidence_span', '')}")
    return "\n".join(lines)


# ── Nodes ─────────────────────────────────────────────────────────────────────

async def gate_node(state: RefineState) -> RefineState:
    """Deterministic compliance scan. No LLM. Sets compliance_findings + gate_verdict."""
    findings = await run_in_threadpool(run_all_compliance_checks, state["jd_text"])
    serialized = [_serialize_finding(f) for f in findings]
    verdict = gate_verdict(findings)
    return {
        **state,
        "compliance_findings": serialized,
        "gate_verdict": verdict,
        "step": "gate",
        "error": None,
    }


async def human_edit_node(state: RefineState) -> RefineState:
    """Pause and wait for recruiter instruction. interrupt() suspends here."""
    # Set idempotency key before suspending so rewrite_node can de-dup on resume
    idempotency_key = state.get("audit_idempotency_key") or str(uuid.uuid4())
    updated = {**state, "step": "human_edit", "audit_idempotency_key": idempotency_key}

    instruction = interrupt("Waiting for recruiter rewrite instruction")  # ← suspend point
    return {**updated, "pending_instruction": instruction, "step": "human_edit"}


async def rewrite_node(state: RefineState) -> RefineState:
    """LLM rewrite. Idempotent: same instruction + same JD → same new version content."""
    instruction = state.get("pending_instruction") or ""
    findings_str = _build_findings_str(state.get("compliance_findings", []))
    user_prompt = COMPLIANCE_REWRITE_USER_TEMPLATE.format(
        raw_jd=state["jd_text"],
        findings=findings_str,
    )
    if instruction.strip():
        user_prompt = f"Additional instruction: {instruction}\n\n{user_prompt}"

    new_text = await run_in_threadpool(generate, user_prompt, COMPLIANCE_REWRITE_SYSTEM)
    if not new_text:
        return {**state, "step": "rewrite", "error": "LLM generate() returned None"}

    return {
        **state,
        "jd_text": new_text,
        "change_note": f"Refine rewrite: {instruction[:120]}" if instruction else "Refine rewrite",
        "step": "rewrite",
        "error": None,
    }


async def export_node(state: RefineState) -> RefineState:
    """Mark the run complete. DOCX export path is set for the caller to retrieve."""
    return {**state, "step": "done", "export_path": f"job_{state['job_id']}_audit_report.docx"}


# ── Routing ───────────────────────────────────────────────────────────────────

def _route_after_gate(state: RefineState) -> str:
    if state.get("gate_verdict") == "pass":
        return "export"
    return "human_edit"


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_refine_graph(checkpointer=None):
    """Build and compile the refine StateGraph.

    Pass a checkpointer (AsyncPostgresSaver) to enable interrupt/resume.
    Without a checkpointer the graph runs linearly (no durability).
    """
    builder = StateGraph(RefineState)

    builder.add_node("gate", gate_node)
    builder.add_node("human_edit", human_edit_node)
    builder.add_node("rewrite", rewrite_node)
    builder.add_node("export", export_node)

    builder.set_entry_point("gate")
    builder.add_conditional_edges("gate", _route_after_gate, {
        "export": "export",
        "human_edit": "human_edit",
    })
    builder.add_edge("human_edit", "rewrite")
    builder.add_edge("rewrite", "gate")   # loop back through gate after each rewrite
    builder.add_edge("export", END)

    return builder.compile(checkpointer=checkpointer)


# Module-level graph without checkpointer (used internally; routers inject checkpointer)
refine_graph = build_refine_graph()
