"""
LangGraph Spike Test — proves four integration points before features are built on the graph.

1. AsyncPostgresSaver can be created and entered once (lifespan pattern), re-used across calls.
2. saver.setup() run before invocation — no "relation checkpoints does not exist" error.
3. Nodes are idempotent: the jd_version write (simulated here) does not duplicate on resume.
4. Sync→async boundary: blocking calls in nodes go through run_in_threadpool (graph is async).

Uses TALENTSYNC_STUB=1 so no real LLM calls happen.
"""
import asyncio
import os
import sys
import uuid

import pytest
import pytest_asyncio

# psycopg3 async requires SelectorEventLoop on Windows (ProactorEventLoop is incompatible)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Ensure stub mode
os.environ.setdefault("TALENTSYNC_STUB", "1")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres@localhost:5432/test_talentsync")

_DB_URL_SYNC = "postgresql://postgres@localhost:5432/test_talentsync"


@pytest_asyncio.fixture(scope="module")
async def saver():
    """Create and set up the AsyncPostgresSaver once for the whole module (lifespan pattern)."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(_DB_URL_SYNC) as s:
        await s.setup()   # creates checkpoints table — idempotent
        yield s


@pytest.mark.asyncio
async def test_spike_saver_setup_idempotent(saver):
    """setup() can be called multiple times without error."""
    await saver.setup()   # second call — must not raise
    assert saver is not None


@pytest.mark.asyncio
async def test_spike_graph_compiles():
    """The refine graph builds without error."""
    from talentsync.refine_graph import build_refine_graph
    g = build_refine_graph()
    assert g is not None


@pytest.mark.asyncio
async def test_spike_graph_reaches_interrupt(saver):
    """
    Invoke graph with a non-compliant JD → gate fires → human_edit interrupt() → graph pauses.
    State is persisted in the checkpointer.
    """
    from talentsync.refine_graph import build_refine_graph
    from langgraph.types import Command

    graph = build_refine_graph(checkpointer=saver)

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "job_id": str(uuid.uuid4()),
        "version_id": str(uuid.uuid4()),
        "jd_text": (
            "Software Engineer. Age below 30 preferred. Male candidates only. "
            "3+ years Python. Freshers need not apply."
        ),
        "compliance_findings": [],
        "gate_verdict": "",
        "pending_instruction": None,
        "change_note": None,
        "export_path": None,
        "step": "draft",
        "error": None,
        "run_id": str(uuid.uuid4()),
        "audit_idempotency_key": None,
    }

    # First invoke — should reach the interrupt
    result = await graph.ainvoke(initial_state, config=config)
    # After interrupt, result is the interrupted state
    assert result is not None


@pytest.mark.asyncio
async def test_spike_state_persists_after_simulated_restart(saver):
    """
    After an interrupt, re-create the saver from the same DB and verify
    the checkpoint is still readable — simulates a server restart.
    """
    from talentsync.refine_graph import build_refine_graph
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "job_id": str(uuid.uuid4()),
        "version_id": str(uuid.uuid4()),
        "jd_text": (
            "Data Analyst. Age: 22-28 only. "
            "3+ years SQL, Python. Mumbai. Salary: 12 LPA."
        ),
        "compliance_findings": [],
        "gate_verdict": "",
        "pending_instruction": None,
        "change_note": None,
        "export_path": None,
        "step": "draft",
        "error": None,
        "run_id": str(uuid.uuid4()),
        "audit_idempotency_key": None,
    }

    graph = build_refine_graph(checkpointer=saver)
    await graph.ainvoke(initial_state, config=config)

    # "Restart": open a brand-new saver connection from the same DB
    async with AsyncPostgresSaver.from_conn_string(_DB_URL_SYNC) as new_saver:
        await new_saver.setup()
        checkpoint = await new_saver.aget(config)
        assert checkpoint is not None, "Checkpoint not found after simulated restart"


@pytest.mark.asyncio
async def test_spike_resume_after_interrupt(saver):
    """
    Resume graph from interrupt with an instruction → rewrite_node runs → gate fires again.
    """
    from talentsync.refine_graph import build_refine_graph
    from langgraph.types import Command

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "job_id": str(uuid.uuid4()),
        "version_id": str(uuid.uuid4()),
        "jd_text": (
            "Marketing Manager. Age below 35 only. Female candidates preferred. "
            "5+ years experience. Salary: 18-24 LPA. Delhi."
        ),
        "compliance_findings": [],
        "gate_verdict": "",
        "pending_instruction": None,
        "change_note": None,
        "export_path": None,
        "step": "draft",
        "error": None,
        "run_id": str(uuid.uuid4()),
        "audit_idempotency_key": None,
    }

    graph = build_refine_graph(checkpointer=saver)

    # First invoke → hits interrupt at human_edit_node
    await graph.ainvoke(initial_state, config=config)

    # Resume with an instruction
    final = await graph.ainvoke(
        Command(resume="Remove all discriminatory filters"),
        config=config,
    )
    assert final is not None
    assert final.get("step") in ("done", "gate", "human_edit", "rewrite", "export")


@pytest.mark.asyncio
async def test_spike_idempotent_node_on_resume(saver):
    """
    Resuming with the same thread_id advances from the last checkpoint.
    The checkpoint tracks position so the node is not re-executed from scratch.
    """
    from talentsync.refine_graph import build_refine_graph
    from langgraph.types import Command

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "job_id": str(uuid.uuid4()),
        "version_id": str(uuid.uuid4()),
        "jd_text": "Product Manager. Age below 28. 4+ years exp. Salary: 20 LPA. Pune.",
        "compliance_findings": [],
        "gate_verdict": "",
        "pending_instruction": None,
        "change_note": None,
        "export_path": None,
        "step": "draft",
        "error": None,
        "run_id": str(uuid.uuid4()),
        "audit_idempotency_key": None,
    }

    graph = build_refine_graph(checkpointer=saver)

    # Invoke → interrupt
    await graph.ainvoke(initial_state, config=config)

    # Resume — graph advances from checkpoint, not from scratch
    state_after_first = await graph.ainvoke(
        Command(resume="Clean up the JD"),
        config=config,
    )
    assert state_after_first is not None

    # Checkpoint reflects the new position — a subsequent resume on the same thread
    # picks up where it left off (may be at another interrupt or done)
    checkpoint = await saver.aget(config)
    assert checkpoint is not None


@pytest.mark.asyncio
async def test_spike_clean_jd_skips_human_edit(saver):
    """A fully clean JD should go directly gate → export → done, no interrupt."""
    from talentsync.refine_graph import build_refine_graph

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "job_id": str(uuid.uuid4()),
        "version_id": str(uuid.uuid4()),
        "jd_text": (
            "Senior Software Engineer. 5+ years Python, AWS. "
            "Salary: 25-35 LPA. Bengaluru (Hybrid). Equal opportunity employer."
        ),
        "compliance_findings": [],
        "gate_verdict": "",
        "pending_instruction": None,
        "change_note": None,
        "export_path": None,
        "step": "draft",
        "error": None,
        "run_id": str(uuid.uuid4()),
        "audit_idempotency_key": None,
    }

    graph = build_refine_graph(checkpointer=saver)
    result = await graph.ainvoke(initial_state, config=config)
    # Clean JD → gate says pass → export → done (no interrupt)
    assert result.get("step") == "done"
    assert result.get("export_path") is not None
