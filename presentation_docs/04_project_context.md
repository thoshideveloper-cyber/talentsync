# Project Context and Metrics

## Academic Context

This is a capstone project submission demonstrating a production-grade full-stack application built around a real regulatory compliance use case.

**Presented by:** L S Thoshi Babu  
**Guided by:** Sri Jaya Vaishnavi

---

## India Labour Code Context

### The Reform

Between 2019 and 2020, the Government of India consolidated **29 central labour laws** into **4 Labour Codes**:

| Code | Year | Replaced Laws |
|------|------|---------------|
| Code on Wages | 2019 | Payment of Wages Act, Minimum Wages Act, Equal Remuneration Act, Payment of Bonus Act |
| Industrial Relations Code | 2020 | Trade Unions Act, Industrial Employment Act, Industrial Disputes Act |
| Social Security Code | 2020 | EPF Act, ESI Act, Maternity Benefit Act, and others |
| Occupational Safety, Health and Working Conditions Code | 2020 | Factories Act, Mines Act, Contract Labour Act, and others |

### Enforcement Context

Enforcement of the consolidated codes has intensified from 2025 onwards. Organizations now face a unified compliance framework in which prior siloed legal review processes — different teams managing different statutes — are insufficient. The first visible point of compliance exposure is the job advertisement itself.

### Why Job Advertisements Matter

A job description that contains an age cap, a gender preference, a caste/community reference, or a disability exclusion is not a drafting error — it is prima facie evidence of discriminatory hiring intent, discoverable at any point by a regulator, court, or activist organization. The Equal Remuneration Act (now Wages Code), the RPwD Act 2016, and Articles 14–16 of the Constitution all create direct exposure.

---

## Quantified System Metrics

All values below are directly derived from the implementation. No estimates or approximations.

| Metric | Value | Source |
|--------|-------|--------|
| Compliance rules enforced per JD scan | 9 catalogued + dynamic language sub-rules | `talentsync/compliance.py` |
| High-risk rule categories | 7 | Rule catalogue: `filter.*` |
| Advisory rule categories | 2 | Rule catalogue: `language.inclusive`, `pay.disclosure_absent` |
| Quality checks (LLM-based) | 2 | `quality.leveling_mismatch`, `quality.unverified_seniority` |
| LLM calls in the compliance check path | 0 (fully deterministic regex) | Design decision |
| User roles with distinct permission tiers | 3 | recruiter / approver / admin |
| JD input methods | 3 | paste / upload / structured intake form |
| Workflow steps from raw JD to export | 4 | Add → Review → Fix → Export |
| Export formats generated per JD | 2 | corrected JD (.docx) + Audit Report (.docx) |
| Quality scoring scale | 0–100 points | `quality_score` column |
| LLM model tiers in failover chain | 6 | Gemini 2.5-flash → 2.0-flash → 1.5-flash → Groq llama-3.3 → llama-3.1 → mixtral |
| Max LLM key slots before request fails | 27 | 3 Gemini tiers × 4 keys + 3 Groq tiers × 5 keys |
| Inclusive-language term list size | 29 | Exact count of `_BIAS_TERMS` in `talentsync/enrich.py` |
| Seniority classification tiers | 5 | Internship(0) → Entry(1) → Mid(2) → Senior(3) → Executive(4) |
| Mismatch trigger threshold | ≥2 ordinal tiers | Conservative false-positive guard |
| Audit log: DB privileges revoked | UPDATE + DELETE | `REVOKE UPDATE, DELETE FROM talentsync_app` |
| Central labour laws consolidated (India) | 29 → 4 Labour Codes | Ministry of Labour, 2019–2020 |
| Precision target (high-risk rule class) | ≥95% recall | Design specification |
| Database tables in schema | 8 | users, jobs, jd_versions, compliance_checks, prompt_presets, agent_runs, agent_steps, audit_log |
| API routers | 10 | auth, jobs, bulk, intake, presets, chat, refine, dashboard, templates, pay_hints |
| Manual JD legal review (baseline) | 30–45 minutes per document | Problem statement |
| TalentSync compliance scan | Seconds | Deterministic regex engine |

---

## Technology Stack — Complete Inventory

### Frontend
- React 19
- TypeScript (strict mode)
- Vite 8
- Tailwind CSS 3.4
- Radix UI (Dialog, Tooltip primitives)
- Lucide React

### Backend
- Python 3.11+
- FastAPI (async)
- Uvicorn (ASGI server)
- SQLAlchemy 2.0 async ORM
- asyncpg (PostgreSQL driver)
- aiosqlite (SQLite driver)
- Alembic (database migrations)
- python-docx (document generation)
- LangGraph (stateful agent loop)
- JWT HS256 (authentication)
- bcrypt (password hashing)

### AI Providers
- Google Gemini 2.5-flash (primary)
- Google Gemini 2.0-flash (fallback tier 2)
- Google Gemini 1.5-flash (fallback tier 3)
- Groq llama-3.3-70b-versatile (fallback tier 4)
- Groq llama-3.1-70b-versatile (fallback tier 5)
- Groq mixtral-8x7b-32768 (fallback tier 6)

### Database
- PostgreSQL (production: JSONB, native ENUMs, Alembic, AsyncPostgresSaver)
- SQLite (local dev: zero-config, metadata.create_all on startup)

---

## Architectural Decisions Worth Noting

### Why regex, not LLM, for compliance?

The compliance engine is entirely regex-based. This is not a cost-cutting decision — it is an auditing requirement. A rule that fires based on a regex pattern produces a verifiable, reproducible result. An LLM-based rule could produce different results on the same input on different days, making it indefensible as an audit artifact. Speed is a secondary benefit (microseconds vs. seconds).

### Why append-only audit log at DB level?

Application-level soft-delete conventions can be bypassed by any code with database credentials. Revoking UPDATE and DELETE on the `talentsync_app` database role at the infrastructure level means the audit log is immutable regardless of application bugs, insider threats, or future code changes.

### Why sha256 deduplication on JD content?

Without content hashing, a recruiter clicking "run check" twice would create two identical database versions, polluting the version chain and KPI counts. The sha256 check ensures idempotency on the upload path. Rewrites always create a new version even on duplicate content (because the transformation chain — who rewrote it, when, from which parent — is the record).

### Why LangGraph for the refine loop?

The refine workflow is a multi-turn loop: gate → human edit → rewrite → gate again. LangGraph's checkpointing (via `AsyncPostgresSaver`) allows this loop to pause for human input and resume exactly where it left off, even if the server restarts. This is not achievable with a stateless REST endpoint pattern.

---

## Deployment Architecture

### Local Development
- SQLite: zero configuration, file at `talentsync.db`
- Backend: FastAPI on `http://localhost:8000`
- Frontend: Vite dev server on `http://localhost:5173`
- LangGraph: in-memory checkpointer (no persistence)
- LLM: real API calls to Gemini/Groq (or stub mode for offline development)

### Production
- Database: PostgreSQL with Alembic migrations
- Backend: FastAPI with Uvicorn workers behind a reverse proxy
- Frontend: Vite static build served via reverse proxy or CDN
- LangGraph: `AsyncPostgresSaver` for durable checkpoint storage
- CORS: locked to explicit origin list via `CORS_ORIGINS` environment variable
- Tenant isolation: `tenant_id` column on all tables; RLS upgrade path is a backfill + PostgreSQL Row-Level Security policy (deferred to scale phase)
