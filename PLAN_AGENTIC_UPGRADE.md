# TalentSync — Agentic Upgrade Plan (Pilot / Scale split)

**Status:** Revised 2026-06-28 — split into a **Pilot tier** (build now) and a **Scale tier**
(deferred). Supersedes the flat phase list in the prior draft.
**Supersedes for new work:** extends [plan.md](plan.md) (original MVP, Phases 0–5) — that plan
stays valid; this covers the next, "Audit-Grade" cycle.

## Locked for the pilot (non-negotiable)

Confirmed by the user 2026-06-28. These three ship in the pilot; everything else bends around them.

1. **Database** — Postgres (replaces `data/results.json`).
2. **Agentic framework** — LangGraph wrapping the deterministic pipeline.
3. **Agent logs** — `agent_runs` / `agent_steps` + an append-only `audit_log` in the DB.

## Pilot bar

One organization, real recruiters, real daily use, small scale. **Single tenant.** The bar is
reliability + data safety + a believable, scoped compliance story — **not** multi-tenant SaaS.

---

## Confirmed direction (revised)

| Decision | Pilot choice (now) | Deferred to Scale |
|---|---|---|
| **Database** | Single Postgres. Real schema (jobs, versions, checks, agent logs, audit). Include a `tenant_id` column **defaulted to one value** so the later migration is cheap — but **no RLS yet**. | RLS, pooled-multi-tenant isolation. |
| **Agentic framework** | **LangGraph** — `StateGraph` over the existing pipeline, `PostgresSaver` checkpointer (same DB, own schema), `interrupt()` for the human edit loop. **No** tiered models, **no** fan-out orchestration, **no** per-tenant model routing. | Tiered small/large models, batch fan-out at scale, per-tenant model routing. |
| **Agent logs** | `agent_runs` / `agent_steps` + append-only `audit_log` in Postgres (who drafted, which prompts ran, who approved, when — with timestamps). | Hash-chained tamper-evidence; **self-hosted Langfuse** for dev tracing (optional, run locally later). |
| **LLM strategy** | Use the **existing Gemini/Groq keys from `.env`** ([llm.py](talentsync/llm.py)) behind an `LLMProvider` interface. **No data-residency / DPDP claim in the pilot** — these are US APIs; a JD is low-sensitivity (meant to be public), so hosted drafting is defensible. Residency only becomes load-bearing if/when candidate PII (resumes) is ingested. | Self-hosted in-region vLLM (open-weight) — the residency story; swaps in behind the same interface. |
| **Deterministic compliance core** | **Kept.** Scoped to **what a JD can actually prove** (see Pilot Phase 1). The wedge. | Appointment-letter / basic-pay-split checks (need offer/contract docs the tool doesn't ingest). |
| **Chat (2 channels = READ vs WRITE)** | **(A) Ad-hoc queries on the active / just-uploaded JD — READ-ONLY, never creates a version.** A1: closed intent set (4–5) → render *existing* analysis inline. A2: free-form **grounded Q&A** over the JD text (LLM, answers only from the JD, "not stated" fallback). **(B) Transformation presets — WRITE (LLM).** Fixed **admin-authored** library (start 2–3); admins author, **recruiters select-only**; LLM transform → new `jd_version` / document. Plus one-off freeform corrections (also WRITE). | More intents; versioned / tenant-scoped / typed-variable / injection-hardened preset library. |
| **Publishing** | Deterministic gate + DOCX/PDF export. | `publish()` adapter → LinkedIn / Naukri / ATS. |
| **Object store** | Local disk / single bucket for exports. | S3-compatible, in-region. |
| **Auth** | Minimal login + locked CORS (single org). | Org/role management, SSO. |

## Guiding principle (unchanged)

**The agent orchestrates and explains; the deterministic Python engine decides compliance.**
The LLM only drafts, rewrites, and narrates. Every legally-meaningful check is deterministic
Python in [enrich.py](talentsync/enrich.py) and produces cited, auditable evidence — never a
black-box "✅ compliant" badge.

---

# Pilot tier — build now

### Pilot Phase 0 — DB foundation (LOCKED #1)
**Deliverable first:** a one-page schema doc, then the migration.

- [ ] Single Postgres. Migrations tool (Alembic).
- [ ] Tables:
  - `users` (id, email, role: `recruiter` / `approver` / `admin`, created_at)
  - `jobs` (id, `tenant_id` *defaulted*, role, created_by, created_at, current_version_id, status)
  - `jd_versions` (id, job_id, **parent_version_id** lineage, raw_jd, content_hash, summary,
    seniority, skills[], source: `upload`/`draft`/`rewrite`, **change_note** ("what changed", powers
    the "transformations applied" list), created_by, created_at) — **append-only**
  - `compliance_checks` (id, jd_version_id, rule_id, result `pass`/`warn`/`fail`, evidence_span,
    citation, checked_at)
  - `prompt_presets` (id, name, kind: `transform`, prompt_text, active, created_by_admin, created_at)
    — **admin-authored, recruiter select-only** (Channel B)
  - `audit_log` (id, actor, action, target_type, target_id, ts, detail) — **append-only, no UPDATE/DELETE**
- [ ] Port [core.process_jd](talentsync/core.py) + the API off `results.json` onto Postgres.
      Kills the current full-file-rewrite race in [api/main.py](api/main.py#L96-L102).
- [ ] Every record carries `created_by` + `created_at` (the MVP `JobRecord` has **no timestamps** today).
- [ ] **Decide version identity** (schema-doc decision): is a re-uploaded identical JD a **new
      `jd_version` of the same job**, or a **dedup hit**? Today the code dedups on `content_hash`
      ([api/main.py:91-94](api/main.py#L91-L94)) — name the rule explicitly under the new versioned model.
- [ ] **Existing-data decision:** `data/results.json` holds synthetic seed records — **start fresh in
      Postgres** (recommended) or write a one-time import. State which.

**Exit:** a JD is created, versioned (with lineage), and read back; an `audit_log` row is written
for every state change.

### Pilot Phase 1 — Deterministic compliance core (the wedge)
Scope to **JD-stage** obligations only. Drop appointment-letter / basic-pay-split (a JD is not an
appointment letter and rarely states the basic/allowance split — those belong to the Scale tier).

**This is a NEW rule class, not a tune-up of the existing wordlist.** Today's ~29-term list in
[enrich.py](talentsync/enrich.py#L10-L18) is buzzword/ageism *vibes* ("rockstar", "young team") and is
self-labelled "flagged for review, not bias detected". The legal checks below are a different mechanism
(patterns/regex + structured detection), built fresh — budget the effort accordingly.

**Deliverable 1 — rule definitions + labeled corpus (the longest pole; do this FIRST).**
- [ ] Written rule definitions: per rule, the legal basis, the citation, what counts as a hit, `warn` vs `fail`.
- [ ] Labeled JD test corpus: **~150–200 real Indian JDs**, **2 labelers**, disagreements adjudicated,
      a stated **precision target**. The corpus gates any "audit-grade" claim — false-pass is the liability.

**Deliverable 2 — detectors (built against the corpus).**
- [ ] **Discriminatory-filter detector (NEW):** age caps ("max 30", "below 28 yrs"), gender / marital /
      community filters ("only male", "unmarried"), "freshers only" — pattern/regex + structured, each
      emitting a citation + evidence span.
- [ ] **Inclusive-language advisory (REUSE/extend):** evolve the existing wordlist to **word-boundary**
      matching + Indian-context terms. Stays **advisory (`warn`)**, never a legal `fail`.
- [ ] **Pay-disclosure presence (REUSE):** `detect_pay` / `_PAY_RE` already does ₹/LPA/lakh
      ([enrich.py:20-32](talentsync/enrich.py#L20-L32)) — wire it into the check set, don't rebuild.

**Deliverable 3 — gate + report.**
- [ ] **Final-check gate — `warn` / `pass` ONLY in the pilot** (no hard `block` yet). A wrong block is a
      liability the tool created and hurts adoption more than a missed flag. **Earn `block` later**, once
      the corpus proves precision. Include an **override-with-justification** path (recruiter overrides →
      reason written to `audit_log`).
- [ ] **Audit report (DOCX/PDF) — mostly NEW:** [docx_builder.py](api/docx_builder.py) today builds a
      *corrected JD* doc, **not** the **methodology disclosure + provenance (who / when / which checks)** an
      audit report needs. Extend it; budget this as new work, not "already mostly done."

**Exit:** an approver selects a final JD, sees a non-black-box `warn`/`pass` verdict with citations +
evidence spans, and downloads the audit report.

### Pilot Phase 2 — Agent shell + agent logs (LOCKED #2 + #3)
Keep LangGraph **minimal and scoped to the human-in-the-loop refine loop** — the *only* place its
durable `interrupt`/resume earns its keep. **Phases 0–1 ship on the existing pipeline; do NOT
re-plumb the linear extract path into a graph** (rework, no pilot payoff). Batch/single extraction
stays the current function call (or a single node).

- [ ] **Spike FIRST (de-risk):** async LangGraph + `PostgresSaver` + SSE streaming layered over the
      current **`sync def`** FastAPI handlers ([api/main.py](api/main.py#L83-L102)). This is where the
      time goes — prove the integration before building features on it.
- [ ] `StateGraph` for the **refine cycle only**: typed state (`jd_version`, `compliance`,
      `chat_history`, `pending_correction`); nodes `draft/rewrite (LLM) → chat loop (interrupt) →
      final gate (deterministic) → export`. The deterministic `enrich`/`score`/gate stays plain Python,
      called as tools.
- [ ] The rewrite node returns a short **`change_note`** ("what changed") stored on the new
      `jd_version` — this powers the "transformations applied" list in Channel-B documents (Phase 3).
- [ ] `PostgresSaver` checkpointer (same DB, own schema); `setup()` run as a migration, not at runtime.
- [ ] `LLMProvider` interface → **existing Gemini/Groq from `.env`** now (vLLM swaps in later, same interface).
- [ ] **Agent logs (LOCKED #3):** write `agent_runs` (per run) + `agent_steps` (per node: input/output
      refs, status, error, ts). This is the required logging — lives in the DB, no extra service.

**Exit:** a refine run can pause at `interrupt()`, persist, and resume after a server restart; every
step is in `agent_steps` and every approval/override in `audit_log`.

### Pilot Phase 3 — Chat (ad-hoc queries + transformation presets) + upload + export
The chat is the **single surface**, handling **two request types — keep them separate in code.**

**Channel A — ad-hoc queries about the JD in focus (READ-ONLY: never creates a `jd_version`).**
Always scoped to the **active JD** — by default the one the recruiter **just uploaded** this session
(or a record they select). Two modes:

- **A1 — structured intents (no LLM generation):** message → intent classifier (LLM, one *fixed* prompt,
  returns ONE value from a **CLOSED enum**) → **deterministic renderer** pulls fields already on the
  record → inline card (reuse existing components, not a new window). Cheaper fallback: keyword routing.
  Ship **4–5 intents**, each mapping to data already computed at upload:
  - `language` → bias / inclusive-language flags (`bias_flags`; later the discriminatory-filter checks)
    — reuses the "Corrections" block in [BeforeAfter.tsx](web/src/components/BeforeAfter.tsx#L98-L118)
  - `leveling` → seniority + native-vs-AI + mismatch + evidence quote
  - `skills` → extracted skills (+ frequency from `/skills`)
  - `pay` → pay-range presence + competitiveness note
  - `score` / `overview` → quality score + breakdown + summary
- **A2 — free-form grounded Q&A on the active JD (LLM call, still READ-ONLY):** for questions outside
  the intent set ("is there a relocation clause?", "notice period?"). The LLM answers **strictly from
  `raw_jd`** with a **"not stated in this JD"** fallback (same grounding discipline as the existing
  `raw_text_justification` technique) — no hallucinated analysis, **no new `jd_version`**.

- [ ] **Context binding:** the chat session/thread holds the **active `jd_version_id`** (just-uploaded
      by default). `process_jd` already computes the analysis at upload, so A1 has data immediately.
- [ ] Light enough to ship **before** LangGraph (active-JD context + a grounded-Q&A call; no graph needed).

**Channel B — transformation presets (WRITE/GENERATE; the fixed admin library).**
A **fixed set (start 2–3)** of admin-authored transformation prompts; recruiters **select-only**. Each
runs its fixed prompt over the current `jd_version` → transformed JD and/or composed document → saved as
a **new `jd_version`** (with its `change_note`) → optional DOCX.
- [ ] Starter presets:
  - **Make compliance-pass** — rewrite to remove flagged language / discriminatory filters, preserve
    meaning; show the gate result after.
  - **Tighten & summarize** — clean JD + one-line summary + key changes.
  - **Full pack document** *(user's example)* — a doc with **summary + transformations applied +
    compliance-passing JD**. Reuses the Phase-1 audit-report builder + the `change_note` lineage.
- [ ] "Transformations applied" = the `change_note`s along the `jd_versions` lineage — no new structure.
- [ ] Admin-only screen to create/edit presets; recruiters never author.

**Shared:**
- [ ] Inline upload panel: **Single** (paste) + **Batch** (multi-file), sequential for the pilot
      (today: [BatchUpload.tsx](web/src/components/BatchUpload.tsx)).
- [ ] Freeform follow-up corrections (one-off) → `interrupt` patch → rewrite node → **new `jd_version`**.
- [ ] **Finalize** → gate → store + download report.

**Exit:** a recruiter (a) asks *"show me the language issues"* and sees it inline (Channel A), and
(b) runs a preset that returns a compliance-passing JD + document (Channel B) — all versioned and attributed.

---

# Scale tier — deferred (swap in behind the pilot seams)

- [ ] **Multi-tenancy + RLS** keyed on `tenant_id` (column already present from Pilot Phase 0).
- [ ] **Self-hosted vLLM**: open-weight benchmarking on real JD tasks, GPU budget, tiered
      small/large models, prefix-cache tuning. Swaps in behind `LLMProvider`.
- [ ] **Hash-chained** tamper-evident provenance + **self-hosted Langfuse** (in-region dev tracing).
- [ ] **Prompt template library (advanced):** versioning, tenant-scoping, typed variables,
      system-role injection-hardening — on top of the pilot's admin presets.
- [ ] **S3-compatible** in-region object store.
- [ ] **`publish()` adapter**: API posting to LinkedIn / Naukri / ATS behind the same gate.
- [ ] Batch **fan-out** at scale (N runs, one `thread_id` each, parent aggregates).
- [ ] Appointment-letter / basic-pay-≥50% checks (require offer/contract ingestion).
- [ ] Cross-role consistency audit at scale.

---

## First two design docs (immediate next step)
1. **Postgres schema doc** — tables/columns/relationships above, the `tenant_id`-now-no-RLS decision,
   checkpointer schema (own schema, same DB).
2. **LangGraph design doc** — state schema, per-node input/output contracts, where `interrupt()` fires,
   tool surface (rules engine, scoring, export), the `LLMProvider` interface.

## Risks & mitigations
| Risk | Mitigation |
|---|---|
| LangGraph over-engineers a linear pipeline | Scope it to the **refine loop only**; Phases 0–1 run on plain Python. It orchestrates, never decides. |
| Async graph over `sync def` FastAPI | The riskiest integration — **spike it first** (Phase 2) before building on it. |
| "Audit-grade" claim on weak checks | Scope to JD-checkable rules; word-boundary + Indian terms; labeled corpus; cite every rule; conservative `warn` over false `pass`. |
| Wrong `block` stops a legit JD | Pilot gate is **warn-only** + override-with-justification (logged). Earn hard `block` after the corpus proves precision. |
| Corpus is the longest pole, under-resourced | Treat rule definitions + labeled corpus as its own deliverable (sized: ~150–200 JDs, 2 labelers, precision target) **before** detector code. |
| Compliance category error (JD ≠ appointment letter) | Appointment-letter / basic-pay-split checks deferred to Scale until offer-doc ingestion exists. |
| Overclaiming residency in the pilot | Pilot uses US APIs (Gemini/Groq from `.env`) → **make no DPDP/residency claim**. JD = low-sensitivity/public, so hosted drafting is fine. Residency story (vLLM) lands only when resumes/PII enter scope. |
| Single-tenant now, multi-tenant later | `tenant_id` column present from day one → Scale migration is backfill + add RLS, not a reshape. |
| `results.json` data loss under concurrency | Postgres in Pilot Phase 0 removes the full-file-rewrite race. |

## Out of scope this cycle
Self-hosted vLLM, multi-tenancy/RLS, hash-chaining, Langfuse, **versioned/typed-variable** prompt-template
library (basic admin presets ARE in the pilot), hard `block` gate, S3, API posting, cross-role audit at
scale — all Scale tier.
