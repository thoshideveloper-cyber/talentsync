# Technical Architecture

## System Overview

TalentSync is a full-stack web application comprising three layers:

1. A React 19 single-page application (SPA) frontend
2. A Python FastAPI asynchronous backend with LangGraph agent support
3. A dual-mode database (SQLite for local development, PostgreSQL for production) with a multi-provider LLM chain and a deterministic regex compliance engine

The compliance engine runs zero LLM calls by design.

---

## Layer 1 — Presentation Layer (Frontend)

### Technology Stack

| Technology | Version | Role |
|------------|---------|------|
| React | 19 | UI framework (concurrent features enabled) |
| TypeScript | strict mode | Type safety across all components |
| Vite | 8 | Build tool and local dev server |
| Tailwind CSS | 3.4 | Utility-first styling with custom design tokens |
| Radix UI | — | Accessible primitive components (Dialog, Tooltip) |
| Lucide React | — | Icon library |

### Design System

Custom CSS property tokens in HSL format (`H S% L%`), wired into Tailwind via `hsl(var(--token))` wrappers.

- **Primary color:** Deep indigo (252° hue) — applied to all primary actions and branding
- **Background:** Cool-tinted off-white
- **Contrast:** WCAG AA compliant muted foreground (≥4.5:1 on white)
- **Typeface:** Inter with OpenType feature settings

### Application Shell

- **Sticky dark-indigo header** — wordmark on left, three-tab navigation (Workspace / Roles / Insights), user identity and sign-out on right
- **Auth gate** — unauthenticated users see the LoginPage (split-pane: brand identity on left, login form on right)
- **KPI Strip** — rendered below the header on every authenticated view; live counts fetched from the database
- **Auth state** — JWT stored client-side; auth state managed in memory via `authStore` singleton (not persisted to localStorage)

### Key UI Components

| Component | Purpose |
|-----------|---------|
| Workspace | 4-step JD processing flow (Add → Review → Fix → Export) |
| Board / Roles View | Paginated JD data table with bulk-select |
| Insights View | Org-wide compliance posture + workforce analytics |
| Bulk Audit View | Batch compliance check runner |
| Bulk Fix View | Batch AI auto-fix runner |
| Chat Panel | Grounded Q&A on current JD |
| Compliance Panel | Findings display with evidence spans and citations |
| Before/After View | Side-by-side diff of original vs. corrected JD |
| KPI Strip | Live metric cards (always visible) |
| Login Page | Authentication gate |

---

## Layer 2 — Application Layer (Backend)

### Technology Stack

| Technology | Role |
|------------|------|
| Python 3.11+ | Language runtime |
| FastAPI (async) | HTTP framework |
| Uvicorn | ASGI server |
| SQLAlchemy 2.0 async ORM | Database access layer |
| asyncpg | PostgreSQL async driver (production) |
| aiosqlite | SQLite async driver (local dev) |
| Alembic | Database migrations (PostgreSQL path) |
| python-docx | .docx document generation (corrected JD + audit report) |
| JWT HS256 | Authentication tokens |
| bcrypt | Password hashing |
| LangGraph | Stateful agent loop (refine workflow) |

### API Routers

| Router | Prefix | Responsibility |
|--------|--------|---------------|
| auth | `/api/auth` | Login, token validation |
| jobs | `/api/jobs` | CRUD, compliance run, KPIs, export |
| bulk | `/api/bulk` | Batch audit + batch auto-fix |
| intake | `/api/intake` | Structured intake form submission |
| presets | `/api/presets` | Admin prompt preset library CRUD |
| chat | `/api/chat` | Grounded Q&A on current JD |
| refine | `/api/refine` | LangGraph agent refine loop |
| dashboard | `/api/dashboard` | Compliance posture aggregates |
| templates | `/api/templates` | Clone-ready JD template library |
| pay_hints | `/api/pay_hints` | Salary range inference hints |

### Security Architecture

- **CORS:** No wildcard. Origins restricted to explicit list via `CORS_ORIGINS` environment variable
- **JWT:** Required on every endpoint except `/api/auth/login`
- **Role-based access:** Enforced per-endpoint (recruiter / approver / admin)
- **Passwords:** bcrypt hashed; never stored in plaintext
- **Audit log immutability:** `REVOKE UPDATE, DELETE FROM talentsync_app` enforced at the database role level — not an application convention

### LangGraph Refine Loop

A stateful agent loop for the interactive refine workflow. The loop nodes are:

```
gate_node
  ├─ [compliance PASS] → export_node (done)
  └─ [compliance WARN] → human_edit_node → rewrite_node → gate_node (loop)
```

- **Checkpointing:** `AsyncPostgresSaver` (LangGraph's PostgreSQL checkpointer) stored in FastAPI's `lifespan` context — not per-request
- **Idempotency:** DB writes use `ON CONFLICT DO NOTHING` on `(job_id, content_hash)` to prevent duplicate version creation on retry
- **Human interrupt:** Supported. The loop pauses at `human_edit_node`; the recruiter makes edits; the loop resumes from the saved checkpoint

---

## Layer 3 — Data and AI Layer

### Database Strategy

| Environment | Database | Notes |
|-------------|----------|-------|
| Production | PostgreSQL | JSONB columns, native ENUM types, Alembic migrations, AsyncPostgresSaver |
| Local dev | SQLite | JSON as TEXT, ENUM as string, `metadata.create_all` on startup (no Alembic) |

**Dialect adapter:** `db/types.py` selects UUID and JSONB implementations at import time based on the `DATABASE_URL` environment variable.

### Database Schema (8 Tables)

**`users`**
- `id` (UUID PK), `email` (unique), `hashed_password`, `role` (recruiter/approver/admin), `created_at`, `tenant_id`

**`jobs`**
- `id` (UUID PK), `tenant_id`, `role` (title string), `input_format` (paste/upload/intake), `created_by` → users, `created_at`, `current_version_id` → jd_versions (nullable; circular FK resolved via `use_alter=True`), `status` (draft/active/published/archived)

**`jd_versions`**
- `id` (UUID PK), `job_id` → jobs, `parent_version_id` (self-referential FK, nullable — preserves transformation chain), `raw_jd` (full text), `content_hash` (sha256 — deduplication key), `summary`, `ai_seniority`, `native_label`, `required_skills` (JSONB array), `bias_flags` (JSONB array), `pay_range_present` (bool), `quality_score` (0–100 int), `score_breakdown` (JSONB list), `is_verified` (bool), `audit_mismatch` (bool), `raw_text_justification` (grounding quote text), `source` (upload/draft/rewrite), `status` (string, default "ok"), `change_note`, `created_by` → users, `created_at`, `tenant_id`

**`compliance_checks`**
- `id` (UUID PK), `jd_version_id` → jd_versions, `rule_id` (string e.g. `filter.age_cap`), `result` (pass/warn/fail enum), `evidence_span` (quoted text from JD), `citation` (statutory rationale text), `checked_at`

**`prompt_presets`**
- `id` (UUID PK), `name`, `kind` (transform), `prompt_text`, `active` (bool), `created_by_admin` → users, `created_at`

**`agent_runs`** (LangGraph refine sessions)
- `id` (UUID PK), `job_id` → jobs, `thread_id` (unique LangGraph thread ID), `status` (running/paused/done/error), `started_at`, `ended_at`, `actor` → users, `tenant_id`

**`agent_steps`** (individual node executions within a run)
- `id` (UUID PK), `run_id` → agent_runs, `node_name`, `status` (ok/error/interrupted), `input_ref` (JSONB), `output_ref` (JSONB), `error`, `ts`

**`audit_log`** (append-only, tamper-evident)
- `id` (UUID PK), `actor` → users, `action` (string), `target_type`, `target_id` (UUID), `ts`, `detail` (JSONB), `tenant_id`
- **UPDATE and DELETE revoked** at DB level from `talentsync_app` role

### Key Database Design Decisions

| Decision | Implementation |
|----------|---------------|
| **Deduplication** | sha256 hash of raw text. Same hash on upload = no new version created. Rewrites always create a new version (preserves transformation chain even on revert) |
| **Circular FK** | `jobs.current_version_id` ↔ `jd_versions.job_id` resolved via `use_alter=True`. Insert order: job (null pointer) → jd_version → UPDATE job pointer |
| **Tenant isolation** | `tenant_id` column on all tables. Single-tenant pilot; RLS upgrade path = backfill + add PostgreSQL RLS policy |
| **Version lineage** | `parent_version_id` self-reference forms a linked list of the transformation chain for any JD |
| **Audit immutability** | DB-level REVOKE, not application-level soft-delete |

---

## AI Intelligence Layer

### LLM Provider Chain

Primary model: **Google Gemini 2.5-flash**

Automatic failover sequence on rate-limit or quota exhaustion:

| Model Tier | Provider / Model | Max API Keys |
|-----------|-----------------|--------------|
| 1 | Gemini 2.5-flash | 4 Google API keys (round-robin) |
| 2 | Gemini 2.0-flash | 4 Google API keys |
| 3 | Gemini 1.5-flash | 4 Google API keys |
| 4 | Groq llama-3.3-70b-versatile | 5 Groq API keys |
| 5 | Groq llama-3.1-70b-versatile | 5 Groq API keys |
| 6 | Groq mixtral-8x7b-32768 | 5 Groq API keys |

**Rotation behavior:**
- Rate-limit hit → immediate rotation to next key slot within the same tier (2-second pause)
- Any other error → skip to next model tier entirely
- 6 model tiers total; up to 27 key slots (12 Gemini + 15 Groq) before a request is declared failed

**Future swap path:** A vLLM self-hosted instance can substitute behind the same `LLMProvider` interface without changing application code. The `LLMProvider` Protocol (extract / generate / rewrite) is the swap boundary.

### Where LLM Is Used

| Task | Description |
|------|-------------|
| JD normalization | Extracts and structures raw text from any input format |
| Seniority classification | Classifies seniority tier AND extracts a grounding quote — the exact sentence from the JD that justifies the classification |
| Quality scoring | Scores the JD 0–100 with per-dimension breakdown |
| Auto-fix rewrite | Full JD rewrite resolving all compliance flags in a single pass |
| Preset transform | Applies an admin-authored instruction to the JD text |
| Grounded Q&A chat | Answers recruiter questions using only the current JD text as context |
| Pay range inference | Suggests pay range hints based on role and market data |

### Where LLM Is Explicitly NOT Used

**The compliance rule engine runs zero LLM calls.** All 9 rule categories (7 high-risk + 2 advisory) are evaluated by a deterministic regex engine.

**Reason for this design decision:**
1. **Speed** — regex runs in microseconds; LLM calls take seconds
2. **Auditability** — deterministic output eliminates hallucination risk from the compliance path
3. **Precision** — ≥95% recall target on the high-risk rule class, achievable with regex pattern sets

---

## Deployment Configuration

| Variable | Local Dev | Production |
|----------|-----------|------------|
| Database | SQLite (zero-config) | PostgreSQL (JSONB + Alembic) |
| Frontend | Vite dev server, port 5173 | Static build behind reverse proxy |
| Backend | FastAPI Uvicorn, port 8000 | Uvicorn workers behind reverse proxy |
| CORS | Dev origin | Explicit list via `CORS_ORIGINS` env var |
| LangGraph checkpointer | In-memory (no persistence) | AsyncPostgresSaver |

**Environment-configurable:** `CORS_ORIGINS`, all LLM API keys, admin credentials, stub mode for offline development.

**Development seed credentials:**
- HR Recruiter: `hr@talentsync.local` / `hr123456`
- Admin: `admin@talentsync.local` / `changeme123`
- Configurable via `HR_EMAIL`, `HR_PASSWORD`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` environment variables
