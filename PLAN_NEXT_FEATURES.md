# TalentSync — Next-Feature Direction & Review

**Status:** Drafted 2026-06-28, revised after CEO + Senior-Engineer critic reviews. Extends
[plan.md](plan.md) (MVP) and [PLAN_AGENTIC_UPGRADE.md](PLAN_AGENTIC_UPGRADE.md) (Pilot/Scale cycle).
This is the **product/PM layer**: what to build next for real users, and why. It does not change the
locked pilot decisions; it prioritizes around them.

> **⚠️ LEGAL FRAMING — CRITICAL CORRECTION (supersedes earlier "now-illegal" language).**
> Earlier drafts called age caps "now-illegal / legally radioactive." **That is wrong for
> private-sector India.** There is no codified private-sector age-discrimination statute; constitutional
> protections (Art. 14/15/16) bind the *State*, not private employers; the Code on Wages 2025 governs
> **gender wage parity**, not age caps or filters in advertisements. Age caps are **litigation / ESG /
> reputational risk — not illegal.** Every detector must be labeled on a **risk gradient, not a
> legality binary**:
> - **"Illegal"** — narrow, *only* rules pinned to a verified statutory hook (legal-review task; until
>   pinned, do NOT use this label).
> - **"Litigation / ESG risk"** — e.g. age caps, "freshers only".
> - **"Advisory / pool-expansion"** — inclusive language.
>
> This is a **rule-definitions-doc + legal-review fix, costing ~no code**, and it protects the entire
> value proposition. If the audit report or a deck asserts illegality and a customer's lawyer disagrees,
> we destroy the one thing the product sells: credibility.

> **Citation caveat (read before any leadership deck):** the research figures below (7.7%, ~24.2%,
> ~85%, r=0.52, +44%, "PNAS 2025" / "HBR 2026") are from credible studies but were **not independently
> re-verified**. The *direction* is safe; *exact numbers/dates are not deck-ready until checked*.

---

## Direction decisions (confirmed this session, 2026-06-28)

| # | Decision | Note |
|---|---|---|
| 1 | **Primary user = recruiter / TA specialist** (daily driver, India high-volume) | Other roles benefit; this one drives ranking. |
| 2 | **Scope = JD lifecycle + (later) one step into screening** | **Screening DEFERRED for the pilot** (review §C/D). On the roadmap, not next cycle. |
| 3 | **Success = all four**: daily stickiness · compliance-risk reduction · time saved · **leadership credibility** | Favor features hitting several at once. #3 is why LangGraph stays (see below). |
| 4 | **Data ceiling = JD text + org history + ATS/job-board sync** | *Not* external pay/market data or sourcing DBs. ATS-sync in-scope **promotes `publish()`** to near-term. |

---

## LangGraph decision (founder override — accepted)

LangGraph adds ~zero *user* value in a single-org pilot — but it has **narrative value**, and
"leadership credibility" is success-metric #3. **Decision: LangGraph is IN**, with three guardrails so
the credibility asset doesn't become the thing that sinks the timeline:

1. **Scoped to the refine loop ONLY.** Do NOT re-plumb the linear extract/batch path into a graph
   (pure rework, zero narrative). Phases 0–1 stay plain Python.
2. **Durability must be *demonstrated*, or we paid for nothing.** The credible moment is **pause at a
   human edit → restart the server → resume exactly where it was.** `interrupt()` + visible
   resume-after-restart is the *deliverable*, not an internal detail. An invisible checkpointer = all
   cost, no credibility.
3. **Gated behind a timeboxed (1-week) spike with a written go/no-go**, sequenced *before* any feature
   is built on it. The spike must prove the four things that bite everyone:
   - `AsyncPostgresSaver` owned in FastAPI **lifespan** (entered once, stashed in `app.state`) — *not*
     an `async with` inside a request handler;
   - `setup()` run **as a migration**, not at runtime (cold DB → `relation "checkpoints" does not exist`);
   - **idempotent nodes** — resume re-runs the whole node, so the `jd_version` / `audit_log` write must
     not duplicate on resume (collides directly with our append-only writes);
   - the **sync-handler → async-graph boundary** (current handlers are `def`; blocking Gemini/Groq/
     pdfplumber calls must go through `run_in_threadpool` or they serialize all requests).

   If the spike passes, build on it. If it stalls, fall back to a `refine_sessions` state row + SSE with
   the **same visible behavior** — and the deck still honestly says "human-in-the-loop agentic refine."

---

## Part 1 — Review of the proposed (PLAN_AGENTIC_UPGRADE.md) features

Verdict legend: **Keep** · **Reshape** · **Defer** · **Cut**. Priorities: must-have / high / nice-to-have.

| Proposed feature | Verdict | Priority | Reasoning |
|---|---|---|---|
| Postgres + versioned schema (lineage, change_note) | Keep | Must | `results.json` full-file-rewrite race ([api/main.py:99-100](api/main.py#L99-L100)) loses work. Versioning *is* the workflow. See engineering guardrails. |
| LangGraph (refine loop) | **Keep (scoped + gated)** | High (narrative) | IN for leadership credibility, scoped to the refine loop, durability demonstrated, gated behind the 1-week spike above. Not on the critical path until the spike passes. |
| `audit_log` (actor/action/timestamps) | Keep | Must | Compliance backbone. `JobRecord` has no timestamps/actor today ([contracts.py:23-40](talentsync/contracts.py#L23-L40)). Enforce append-only via **DB grants**, not convention. |
| `agent_runs` / `agent_steps` | Reshape | Nice-to-have | Logging, not observability/user value. Lightweight only. |
| Discriminatory-filter detector | Keep | Must | The crown jewel — but **risk-gradient labeled, not "illegal"** (see top callout). Narrow illegal class = only rules with a verified statutory hook; age caps/"freshers only" = litigation/ESG risk. |
| Inclusive-language advisory | Reshape | High | Reframe as **applicant-pool expansion**. **Word-boundary fix shipped** (was substring: "Gurugram"→guru; "Hero MotoCorp" still flags as a true word match — needs context-aware detection). Advisory `warn` only. |
| Pay-disclosure presence | Reshape | High | **Competitiveness + equal-pay risk, not a posting mandate** (no India law mandates posting salary). Nudge to add a range; warn if too wide. |
| Labeled corpus before detectors | Keep — stage it | Must | Ship a **50-JD golden set first** (prove precision on the narrow rules), grow to 150–200 later. Include **adversarial negatives** (JDs at "Hero"/"Sharp"/"Dynamic") or inclusive-language precision craters. |
| Final-check gate (warn/pass, override+justification) | Keep | Must | Protects against a wrong *block*. Does **not** protect against a wrong *legal claim* — that's the top callout. |
| Audit report (DOCX/PDF, methodology+provenance) | Keep — first-class budget | High | The differentiated artifact (proof-of-diligence the TA lead forwards to legal). New work; `docx_builder` only builds a corrected JD today. Must state recall caveats (age-cap surface forms are a long tail) or it overclaims. |
| Chat A1 (intent classifier → existing data) | **Cut/demote** | Nice-to-have | LLM classifier to fetch data you already have = theater. **Static visible panel** instead. Don't spend the demo on it. |
| Chat A2 (grounded Q&A over raw JD) | Keep | High | Real chat value. **Read-only by construction** — no tool/write access in that path (JD text is untrusted input; injection-to-write is a real vector). |
| Chat B (admin presets, recruiter select-only) | Keep | High | Daily time-saver. **"Make compliance-pass" = the killer preset.** Must be its **own route**, executing only a fixed `prompt_presets.id` — never a model-chosen action. |
| Inline upload (single + batch) | Keep | Must / High | Batch = India-volume time-saving + powers Feature F. |
| Minimal auth + locked CORS | Keep — **land in Phase 0** | Must | Audit trail needs a real actor; without auth every audit row is anonymous. CORS today is wide-open `"*"` ([api/main.py:31](api/main.py#L31)). |
| Publishing: gate + DOCX/PDF export | Keep / promote | High | `publish()`/ATS posting **moves up** given decision #4. |
| LLMProvider interface (hosted now) | Keep | Must | Residency story becomes load-bearing only when resumes enter (screening — deferred). |

**Scale-tier deferrals affirmed** (multi-tenancy/RLS, vLLM, hash-chaining, Langfuse, advanced template
library, S3, fan-out, cross-role audit). **Appointment-letter / basic-pay-split checks stay off the JD
tool** (category error — a JD is not an offer letter). *Legal note:* the "basic+DA ≥50%" rule is commonly
read that way, but the Code on Wages frames it as **wages ≥50% of total remuneration** — lawyer-verify.

---

## Engineering guardrails (from the senior-engineer review — fold into PLAN_AGENTIC_UPGRADE.md)

- **Version identity must be resolved in the schema doc before any migration:** dedup keyed on
  **`(job_id, content_hash)`**, applied on the **upload path only, never on rewrite** (an LLM rewrite that
  reverts to an ancestor's text must still create a version, or the "transformations applied" chain breaks).
- **Hash raw vs normalized text — decide consciously.** `_sha256(text)` hashes raw text today
  ([core.py](talentsync/core.py)), so a trailing-space edit = a new version. Defensible for an audit trail,
  but make it a decision, not an accident.
- **Circular FK** (`jobs.current_version_id` ↔ `jd_versions.job_id`) needs Alembic `use_alter` / deferred
  constraint, or insert-job → insert-v1 → update-pointer.
- **`audit_log` append-only enforced at the DB** (revoke UPDATE/DELETE from the app role), not by comment.
- **`compliance_checks` keyed to `jd_version_id`** (version-specific) — correct as planned.
- **Missing from the plan, add them:** results.json→Postgres data decision (start fresh, stated);
  Alembic down-migrations/rollback; a test plan wiring the corpus to CI as the detector test suite;
  surfacing LLM-failure (`status:"unverified"`) to the user in the refine loop instead of silent downgrade;
  auth mechanism specifics (session/JWT, where roles live) — landing in Phase 0.

---

## Part 2 — New features (prioritized)

### Must-have / High — next
- **A. JD intake → compliant-by-construction first draft.** *(Stickiness · Time-saved · Wow)* Guided
  intake → LLM draft → through the compliance engine. Makes TalentSync a **daily-open** tool. The
  daily-habit product.
- **B. Requirement-realism / "funnel-shrink" advisor.** *(Time-saved · Compliance · Wow)* Flag degree
  inflation, inflated years, too many must-haves. **Advisory (`warn`), sequenced behind the crisp wedge**
  — "over-specified" is subjective (lower precision than the filter rules).
- **E. Reusable, compliant JD template library (own history).** *(Stickiness · Time-saved)* Clone
  approved, compliance-passed JDs. Uses `jd_versions` lineage.
- **F. Bulk audit of existing / live JDs (upload batch + ATS/Naukri import).** *(Compliance · Time-saved ·
  Wow)* — **THE sales/demo moment.** Scan dozens-hundreds of postings → executive summary: *"X of your Y
  live postings carry illegal-or-high-risk filters"* (risk-gradient wording, **not** "now-illegal"). The
  land-and-expand gut-punch that closes the room. The single-JD refine loop is the daily-habit product;
  **F is the sales product** — give it real demo budget.

### Medium-high
- **G. Compliance-posture dashboard (team/portfolio).** *(Compliance · Leadership)* Pass-rate, top
  recurring risks, trend, override log. Secondary persona → high, not must.
- **H. Illegal/high-risk-filter guardrail extended into screening criteria.** *(Compliance)* Lands with screening.
- **I. Pay-range helper from own history.** *(Time-saved · Stickiness)* Nudge to add a range; warn on too-wide;
  suggest a band from the org's *own* past JDs (no external benchmark data).

### Deferred (roadmap, not next cycle)
- **C/D. JD → screening scorecard + glass-box résumé-fit explainer.** **DEFERRED — hold this line hard.**
  Introduces candidate PII (DPDP + residency become load-bearing), it's the most-litigated AI surface, and
  it's a different product. The single most important strategic discipline: **do not let screening into the
  pilot** — it's where the US-API shortcut turns from "fine" into "negligent."
- **J. ATS/Naukri export & push-back** (write half of F). **K. Candidate-view JD preview.**

---

## The smallest fast version that wows + funds (CEO review)
Ship **Postgres + audit_log + the narrow illegal/high-risk filter detector + the audit-report artifact +
Feature F bulk-scan**, refine loop on the LangGraph graph (scoped + gated per above). Two wow moments:
(1) recruiter closes flagged→fixed→provable-report in one click; (2) TA lead sees *"X of your live
postings carry illegal/high-risk filters"* across the portfolio.

**Cut from this cycle:** the A1 intent classifier, multi-tenancy, and the full 150–200 corpus (start at 50).
**Reframe every "illegal" claim as a risk gradient before any deck or report ships.**

### The one metric that gates the value proposition
**Detector precision on the labeled corpus — specifically near-zero false-pass on the illegal/high-risk
filter class (stated target, e.g. ≥95% precision)** — held before any "audit-grade" or risk-claim language
ships externally. Everything else (LangGraph, chat polish, multi-tenancy) is replaceable; this isn't.

---

## The next three (no rework — all ride the jd_versions + compliance-engine + audit_log spine)
1. **Postgres + audit_log + the risk-gradient filter detector** (word-boundary fix shipped).
2. **Feature A** — compliant-by-construction first draft (daily-habit lever).
3. **Feature F** — bulk audit of existing JDs (the leadership "we're exposed" moment).

---

## Shipped this session (verified)
- Word-boundary `detect_bias` ([enrich.py](talentsync/enrich.py)) — kills substring false-positives like
  "Gurugram"→guru. *Caveat:* "Hero" (Hero MotoCorp) still flags (true word match → needs context-aware detection).
- `audit_mismatch` now fires on pasted JDs — stated level derived from the JD title ([core.py](talentsync/core.py)).
