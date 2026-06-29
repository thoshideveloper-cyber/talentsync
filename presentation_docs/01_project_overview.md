# TalentSync — JD Intelligence Platform

## What It Is

TalentSync is a Job Description (JD) Intelligence Platform purpose-built for Indian organizations to achieve Labour Code 2025 compliance. It automates the compliance review, bias detection, and quality assurance of job advertisements before they are published — replacing a manual legal-review process that typically takes 30–45 minutes per JD.

---

## Problem Being Solved

Indian HR teams post job descriptions that routinely contain:

- **Illegal or high-litigation-risk filters** — age caps, gender preferences, caste/community references, disability exclusions
- **Seniority title mismatches** — a "Junior Developer" role requiring 10 years of experience and team leadership
- **Missing compensation disclosure** — contrary to Code on Wages 2019 pay transparency principles
- **Exclusionary culture language** — terms like "rockstar" or "ninja" that demonstrably deter diverse applicants

The 2019–2020 Labour Code reform consolidated 29 central labour laws into 4 Codes (Wages, Industrial Relations, Social Security, Occupational Safety). Enforcement posture has intensified since 2025. Organizations lack tooling to check JDs before posting — meaning violations are caught only after the advertisement is live.

---

## Who Uses It

Three roles with granular, non-overlapping permission tiers:

| Role | Permissions |
|------|-------------|
| **Recruiter** | Create JDs, run compliance checks, view findings, export documents |
| **Approver** | All Recruiter permissions + override compliance warnings with mandatory documented justification |
| **Admin** | All Approver permissions + create user accounts, manage prompt preset library, manage template library |

---

## Core Value Proposition

A recruiter pastes or uploads a raw JD. Within seconds, TalentSync returns:

1. A binary compliance verdict (pass / warn)
2. Categorized findings with exact quoted evidence from the JD text
3. Statutory citations for each high-risk finding
4. An AI-assisted corrected version of the JD
5. A formal export package: corrected JD (.docx) + Audit Report (.docx) — both ready for legal filing

Every action — review, correction, override, export — is recorded in a tamper-evident, append-only audit log enforced at the database privilege level (UPDATE and DELETE revoked on the talentsync_app role).

---

## The Four-Step Workspace

### Step 1 — Add JD

Three input methods:

- **Paste** — recruiter pastes raw text directly into the editor
- **Upload** — single or batch file upload (.txt, .docx, .pdf); text is extracted and normalized by the AI layer
- **Build from scratch** — a guided structured intake form collects role details and generates an initial JD draft

### Step 2 — Review

Compliance verdict shown first (pass / warn), then each finding expanded with:

- Risk tier badge (High-Risk / Advisory)
- Exact quoted evidence span from the JD text
- Statutory citation or best-practice rationale
- Seniority verification result and grounding quote (the exact sentence from the JD that justifies the classified seniority tier)
- Quality score (0–100) with per-dimension breakdown

### Step 3 — Fix

Three correction methods available in parallel:

- **Auto-fix with AI** — LLM rewrites the full JD in a single pass to resolve all compliance flags
- **Apply Preset** — admin-curated transformation prompt applied to the JD (e.g., "Make Compliance-Pass", "Neutralise Gender Language")
- **Chat about this JD** — grounded Q&A chatbot scoped strictly to the current JD text; recruiter can ask targeted questions before fixing manually

### Step 4 — Export

- Download corrected JD as `.docx`
- Download Audit Report as `.docx` — full provenance, all findings with evidence quotes, version chain, override log (if applicable), statutory citations

---

## Additional Platform Capabilities

### Roles Tab
Paginated data table of all JDs with sort, filter, and bulk-select. Each row links directly to that JD's workspace review step.

### Bulk Operations
- **Bulk Audit** — run compliance checks across a batch of JDs simultaneously
- **Bulk Auto-Fix** — AI rewrites all flagged JDs in a batch

### Insights Tab (read-only, org-wide)

**Compliance Posture panel:**
- Org-wide pass rate
- Top triggered compliance rules
- 8-week pass-rate trend chart
- Recent overrides with justifications

**Workforce Analytics panel:**
- Skill demand frequency across all roles
- Quality score distribution across all roles

**Template Library:**
- Compliance-passing JD templates created and curated by admins
- Recruiters clone a template as a starting point for a new role

### KPI Strip (always visible, live from database)
- Total roles processed
- Bias-flagged count and percentage
- Leveling mismatch count
- JDs with pay range declared
- Seniority-verified with grounding quote count

---

## Export Document Formats

### Corrected JD (.docx)
The AI-rewritten JD with all compliance flags resolved, formatted as a professional job advertisement ready for publication.

### Audit Report (.docx)
Formal compliance audit document containing:
- Original JD text
- All compliance findings with evidence quotes and statutory citations
- Seniority verification result and grounding quote
- Quality score and breakdown
- Version chain (transformation history)
- Override records (if any) with actor, timestamp, and justification text
- Unique version ID and content hash for traceability
