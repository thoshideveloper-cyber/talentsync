# NotebookLM Prompt — Executive/Stakeholder Grade

> Upload all four MD files (01_project_overview.md, 02_technical_architecture.md,
> 03_compliance_rules.md, 04_project_context.md) to NotebookLM, then paste the
> block below exactly as written.

---

You are preparing a formal presentation for an audience of executive project 
managers, technical leads, and senior stakeholders. The tone must be precise, 
authoritative, and completely free of marketing language, superlatives, and 
hedging phrases. Every claim on every slide must be directly traceable to the 
uploaded source documents. Do not introduce any information not present in the 
sources. Do not use words like "robust", "powerful", "seamless", "cutting-edge", 
or "innovative". State what the system does and what the numbers are.

Generate slide content for exactly 7 slides in the order specified below. For 
each slide, provide:
  (A) CONTENT — the exact text to appear on the slide
  (B) LAYOUT — one line of direction for the slide designer

Do not add slides. Do not reorder slides. Do not use bullet points on slides 
1, 5, and 7.

─────────────────────────────────────────────────────────────────────────────
SLIDE 1 — TITLE
─────────────────────────────────────────────────────────────────────────────
Content:
  Primary title: TalentSync
  Secondary line: JD Intelligence Platform
  Thin horizontal separator rule
  Lower-left: Presented by: L S Thoshi Babu
  Lower-right: Guided by: Sri Jaya Vaishnavi

No body text. No bullet points. No other content.

Layout: Full-bleed dark indigo background. Wordmark centered in the upper 
third, large weight. Names in the lower third, two columns separated by a 
thin vertical rule. White text throughout.

─────────────────────────────────────────────────────────────────────────────
SLIDE 2 — PROBLEM STATEMENT AND SOLUTION
─────────────────────────────────────────────────────────────────────────────
Title: The Problem / The Solution (two clearly labeled sections)

PROBLEM SECTION — exactly three sentences, paragraph form only, no bullet 
points. Draw exclusively from the source documents.

  Sentence 1: State the regulatory context — 29 central labour laws have been 
  consolidated into India's 4 Labour Codes (Wages, Industrial Relations, Social 
  Security, Occupational Safety) with enforcement intensifying from 2025. Job 
  advertisements are the first visible point of compliance exposure.

  Sentence 2: State the operational failure — HR teams review JDs manually, a 
  process taking 30–45 minutes per document, producing routine violations including 
  age caps, gender preferences, caste-based filters, and missing pay disclosure 
  that go undetected until the advertisement is live.

  Sentence 3: State the consequence — a single high-risk clause in a published 
  job advertisement creates civil-claims exposure, reputational risk, and ESG 
  governance violations traceable directly to the text of the advertisement. 
  Note that most of these risks arise from litigation and ESG exposure, not 
  codified statutory prohibitions on private employers — which makes pre-publication 
  review the only reliable control.

SOLUTION SECTION — exactly three sentences, paragraph form only, no bullet 
points.

  Sentence 1: Describe what TalentSync does at the system level — accepts a raw 
  JD via paste, file upload (.txt/.docx/.pdf), or structured intake form; returns 
  a compliance verdict with categorized findings and risk citations; and generates 
  a corrected document — in seconds, versus the 30–45 minutes of manual review.

  Sentence 2: Describe the intelligence architecture — compliance rules run as a 
  deterministic regex engine with zero LLM calls and a ≥95% precision target on 
  the high-risk class; the LLM handles extraction, quality scoring (0–100), 
  seniority verification with a grounding quote, auto-fix rewrite, preset 
  transforms, and grounded Q&A chat.

  Sentence 3: Describe the governance output — every review, correction, override, 
  and export is recorded in an append-only audit log with UPDATE and DELETE revoked 
  at the database role level, producing a tamper-evident evidence trail for legal 
  and HR governance teams.

Layout: Two-column layout. Problem on the left with a red-amber left border 
accent. Solution on the right with a green left border accent. Paragraph text 
only — no bullets, no sub-headers within columns.

─────────────────────────────────────────────────────────────────────────────
SLIDE 3 — SYSTEM ARCHITECTURE
─────────────────────────────────────────────────────────────────────────────
Title: System Architecture

Present three clearly separated horizontal layers. Each layer: label + 
technology list as pills/tags + one-sentence role description.

LAYER 1 — PRESENTATION LAYER
Technologies (as pills):
  React 19 · TypeScript · Vite 8 · Tailwind CSS 3.4 · Radix UI · Lucide React
Role: Single-page application delivering the 4-step JD workspace, live KPI 
strip, compliance review panel with evidence spans, AI fix tools, bulk 
operations, and the org-wide Insights dashboard.

LAYER 2 — APPLICATION LAYER
Technologies (as pills):
  Python · FastAPI (async) · SQLAlchemy 2.0 · Alembic · JWT HS256 · bcrypt · 
  python-docx · LangGraph · Uvicorn ASGI
API surface: 10 routers — auth, jobs, bulk, intake, presets, chat, refine, 
  dashboard, templates, pay_hints
Role: Authentication, role-based access (recruiter / approver / admin), all 
business logic, .docx document generation, and the stateful LangGraph refine 
loop with AsyncPostgresSaver checkpointing and human-interrupt support.

LAYER 3 — DATA AND AI LAYER
Database: PostgreSQL (production) / SQLite (local dev)
Schema: 8 tables — users, jobs, jd_versions, compliance_checks, 
  prompt_presets, agent_runs, agent_steps, audit_log
  (audit_log: append-only — UPDATE + DELETE revoked at DB level)
LLM failover chain (6 model tiers, auto-rotation):
  Tier 1 → Gemini 2.5-flash (4 API keys, round-robin)
  Tier 2 → Gemini 2.0-flash (4 API keys)
  Tier 3 → Gemini 1.5-flash (4 API keys)
  Tier 4 → Groq llama-3.3-70b (5 API keys)
  Tier 5 → Groq llama-3.1-70b (5 API keys)
  Tier 6 → Groq mixtral-8x7b (5 API keys)
  Max: 27 key slots before a request is declared failed
Compliance engine: 100% deterministic regex — zero LLM calls

Below all three layers, one horizontal callout strip:
  "Deduplication: sha256 content hash per version ·
  Version lineage: parent_version_id chain ·
  Tenant isolation: tenant_id on all tables ·
  LangGraph interrupt/resume: human-in-the-loop on refine loop ·
  vLLM swap path: LLMProvider Protocol is the substitution boundary"

Layout: Three horizontal bands stacked vertically, each with a distinct left 
accent color. Technology pills inside each band. Callout strip at the bottom 
in a muted background. Dense but scannable — no prose paragraphs on this slide.

─────────────────────────────────────────────────────────────────────────────
SLIDE 4 — COMPLIANCE RULES
─────────────────────────────────────────────────────────────────────────────
Title: Compliance Engine — 11 Rules, 0 LLM Calls

Three labeled table sections. Show all 11 rules. Use exact rule IDs from 
the source documents.

Important framing note for this slide: most high-risk rules reflect 
litigation/ESG exposure, not codified statutory prohibitions on private 
employers. Use "Risk Basis" as the column header, not "Statutory Basis."

SECTION A — HIGH-RISK (7 rules)
Sub-header: "Override requires Approver/Admin + mandatory written 
justification recorded in append-only audit log."

Table columns: Rule ID | Short Name | Risk Basis

  filter.age_cap            | Age Cap             | Litigation/ESG risk · Code on Wages 2019 · no private-sector age statute (Art. 15/16 bind the State)
  filter.gender_preference  | Gender Preference   | Equal Remuneration Act 1976 / Code on Wages 2019 · direct discrimination evidence
  filter.marital_status     | Marital Status      | Indirect discrimination · ESG governance
  filter.community_caste    | Caste / Community   | Art. 14–16 Constitution · civil-claims and reputational exposure
  filter.disability_exclusion | Disability Exclusion | Rights of Persons with Disabilities Act 2016
  filter.maternity_status   | Pregnancy / Maternity | Maternity Benefit Act 1961 · direct evidence of discriminatory intent
  filter.freshers_only      | Freshers Only       | Indirect age discrimination · unjustified talent pool restriction

SECTION B — ADVISORY (2 rules)
Sub-header: "Best-practice guidance. No statutory mandate. Acknowledges 
without override justification."

  language.inclusive        | Inclusive Language  | 29-term list · TalentSync inclusive-language advisory
  pay.disclosure_absent     | No Pay Disclosure   | Code on Wages 2019 — pay transparency principles

SECTION C — QUALITY CHECKS (2 rules, LLM-based)
Sub-header: "Run in the AI extraction pipeline — not the deterministic 
compliance engine."

  quality.leveling_mismatch    | Leveling Mismatch    | LLM · fires at ≥2 ordinal tier gap (5 tiers: Internship→Executive)
  quality.unverified_seniority | Unverified Seniority | LLM · grounding quote extracted from JD text; absent = unverified

Footer (small text, bottom of slide):
"Scope: detectors flag explicit written filters only. Implicit bias is outside 
scope. Not a legal opinion. Recall target: ≥95% on high-risk class. Most 
filter.* rules reflect litigation/ESG exposure, not codified private-employer 
statutory prohibition."

Layout: Three stacked table sections. Red header row for high-risk, amber for 
advisory, indigo for quality. Footer in 8pt muted text. Dense grid — this is 
a reference slide, not a summary slide.

─────────────────────────────────────────────────────────────────────────────
SLIDE 5 — DEMO
─────────────────────────────────────────────────────────────────────────────
Content:
  Title only: Live Demo

Nothing else. No body copy. No bullets. No sub-heading. Leave the full slide 
body blank — a video recording will be inserted here during the presentation.

Layout: Title centered at vertical midpoint, large font weight. Remainder of 
slide is intentionally empty white space.

─────────────────────────────────────────────────────────────────────────────
SLIDE 6 — METRICS AND IMPACT
─────────────────────────────────────────────────────────────────────────────
Title: By the Numbers

Present as a 2-column × 5-row grid of metric cards. Each card: large numeral 
on top, short label below. No prose. No sentences. Use exactly these values — 
all directly derived from the source documents.

Left column:
  9        Compliance rule categories per scan (7 high-risk + 2 advisory)
  0        LLM calls in the compliance check path
  6        LLM model tiers in the failover chain
  29       Inclusive-language terms in the bias wordlist
  ≥95%     Precision target — high-risk rule class

Right column:
  3        User roles with distinct permission tiers
  4        Workflow steps: raw JD to audit-ready export
  2        Export formats per JD (corrected JD + audit report)
  8        Database tables in the schema
  29→4     Central labour laws consolidated into Labour Codes

Below the grid, one horizontal callout strip (three short lines maximum):
  "Manual JD legal review: 30–45 min per document."
  "TalentSync compliance scan: seconds."
  "Every finding is evidence-quoted. Every override is audit-logged 
  and tamper-evident at the database level."

Layout: 2×5 metric card grid. Large numerals in brand indigo, labels in 
muted grey. Callout strip below in a light background band. Numerals are 
the visual hero — no body text on this slide.

─────────────────────────────────────────────────────────────────────────────
SLIDE 7 — CLOSING
─────────────────────────────────────────────────────────────────────────────
Content:
  Large centered text: Thank You
  Medium line below: TalentSync · JD Intelligence Platform
  Small line below that: India's Labour Code 2025 · 
                         Compliance. Verified. Audit-ready.

No other content. No bullet points. No name credits (already on Slide 1).

Layout: Full-bleed dark indigo background matching Slide 1. All text centered 
horizontally and vertically. White text in three weight/size tiers: large / 
medium / small. No decorative elements.

─────────────────────────────────────────────────────────────────────────────
OUTPUT FORMAT

For each slide, write:

SLIDE [N] — [NAME]
(A) CONTENT:
[exact text structured as described above]

(B) LAYOUT:
[one-line design direction]

Keep every word across all slides precise and factual. No superlatives. No 
marketing adjectives. No phrases like "robust", "powerful", "seamless", or 
"innovative". State facts and numbers only.
