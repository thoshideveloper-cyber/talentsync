# TalentSync — Build Specification (v5)

> **Status:** Authoritative implementation contract. **This document wins** over
> `PLAN.md` wherever they disagree. `PLAN.md` remains valid only for the original
> dataset analysis.
>
> **What changed in v5:** (1) **UI moved from Streamlit → React (Vite + TypeScript)
> SPA + FastAPI (Python) backend.** Real REST API; the Python engine is unchanged.
> (2) All technical/product review fixes applied (unverified-summary hole, brittle
> verification, shared core, KPI honesty, paste-box-first scoping). (3) Storage is
> `results.json` (API-native) instead of CSV.
>
> **Scope honesty (read first):** the engine is a trustworthy extraction pipeline;
> the UI is now a **production-quality React app**, not a throwaway demo. This is
> **~3 days** (engine ≈1, UI ≈2), not 2. We still do NOT build auth, multi-user,
> a database cluster, or process all 949 rows. The impressive part remains **trust
> by construction** — every *judgment* output is backed by an exact quote in the
> source text.
>
> **One-line product:** Paste a messy job draft → watch it normalize live into a
> trustworthy, traceable record (skills, true seniority, biased-language flags,
> pay-range signal), with a clean **JD Intelligence dashboard** over everything
> processed — every seniority call provably tied to a quote in the source.

---

## 1. The user and where the "messy JD" comes from

**User:** HR / recruiting teams (demoed to leadership). Not job-seekers.

**Workflow finding (researched, §3):** managers rarely write a full JD. The mess
is the **published** JD, produced by HR *after* intake.

```
Stage 1  Manager sends raw input  (Slack / email / sparse form / old-JD paste)
Stage 2  HR clarifies on an intake call, takes notes
Stage 3  HR drafts the JD  (template + buzzwords + copy-paste, no technical review)
Stage 4  HR posts it  (ATS → LinkedIn / Naukri)
Stage 5  The JD sits live, messy, for 30–60 days
```

| Moment | When | What the tool does | Priority |
|---|---|---|---|
| **Quality Gate** | Stage 3, before posting | Paste a draft → "level Uncertain, 2 bias flags, no pay range, 2 real skills" → HR fixes it | **Hero (paste box)** |
| **Intelligence & Audit** | Stage 5, managing live reqs | Browse everything processed → board + skills/leveling/bias/pay views | Secondary (dashboard) |

**This build runs on the synthetic Stage-1 sample we created** (`synthetic_seeds.py`,
15 labeled seeds; §9). The LinkedIn 949 (Stage-5) is **untouched — deferred to a
later stage.** Because the seeds are Stage-1 *drafts*, the **paste box is the
product**; the dashboard is the record of what's been processed (§8 scoping).

---

## 2. Product scope — features

### Core (must ship)
1. **Extraction engine** — one LLM call per JD → `{summary, seniority, skills, grounding_quote}`.
2. **Deterministic enrichment** — biased-language flags, pay-range present, leveling mismatch. Zero API.
3. **Trust layer** — grounding-quote verification + skill traceability + small eval (§6, §10).
4. **Shared core** — `process_jd(text)` = extract → enrich → verify, called by **both** the batch script and the API (one code path; §4, §7).
5. **FastAPI backend** — typed REST endpoints over the engine; serves cached records + live `/extract` (§8.1).
6. **React SPA dashboard** — KPI strip + Board + paste box (with **before/after**) + 2 lighter views; production-quality component UI (§8.2).
7. **Corrected JD download** — `.docx` from the *already-verified* fields, per row and from the paste box. Zero new LLM call (§8.3).

### Cut from earlier drafts (deliberately, see review)
- ~~Dedicated JD-ranking view~~ — 15 rows are eyeballable; keep the quality *score* as a chip only.
- ~~Incremental-upload flow~~ — redundant with the paste box (which already live-adds).
- ~~Skills "demand map" as a headline~~ — at n=15 it's sparse; demote to a light "skills mentioned" view, reframed (not "market demand").

### Stretch (only if time)
8. **Semantic skill match** — numpy-cosine, free embeddings. No vector DB.

### Explicitly NOT built (§13)
RAG · knowledge graph · vector DB · auth / multi-user · database cluster · async at
scale · processing all 949 rows · real ATS integration · scraping · Node rewrite of
the Python engine.

---

## 3. Research foundation (primary practitioner/research sources, not SEO)

| Pain | Evidence | Source |
|---|---|---|
| Titles/JDs are chaotic; no skills inventory | BNY Mellon collapsed 3,000 positions; one firm had 65 levels | Bersin |
| Skills-based hiring is the #1 priority | 75% of recruiters say top priority; 50% search by skills | LinkedIn *Future of Recruiting 2025* |
| Inconsistent leveling → pay-equity liability | similar work paid differently; root = weak job architecture | Deel |
| Biased language skews the applicant pool | gendered phrasing statistically shifts who applies; Textio is **outcome-data-based, not a wordlist** | Textio |
| How HR fixes JDs today | augmented writing (inline, at write-time) + templates; Square + Datapeople → **25% more female applicants** | Ongig, Datapeople |
| Pay transparency is a **competitive** signal in India (not law) | Indeed: India postings with pay crossed **50%** in 2025 (26% in 2022); **senior roles least transparent (~13%)**; Code on Wages 2019 mandates equal pay, **not** range disclosure | Indeed India |
| Managers don't write JDs; HR does, after intake | "HM writes JD; signals diverge week two"; managers copy-paste old JDs | Metaview, PACE, Ongig |

> **Framing rules from the evidence:**
> - **Bias** is a wordlist here (a *naive baseline* — Textio's real value is
>   outcome-correlated). Label output **"flagged for review," never "bias detected."**
> - **Pay range** is an India **conversion/competitiveness** signal, **not legal
>   compliance.** The EU directive does NOT apply to this data — never cite it.

Full URLs in §15.

---

## 4. Architecture

```
┌─ Python engine (talentsync/) ───────────────────────────────────────┐
│ Layer 1  Extraction   one LLM call → {summary, seniority, skills, quote}   │
│ Layer 2  Enrichment   deterministic, free: bias wordlist · pay regex · skill map │
│ Layer 3  Trust        grounding-quote verify · skill traceability · audit_mismatch │
│          core.process_jd(text)  ── the SINGLE path used by batch AND API   │
└──────────────────────────────────────────────────────────────────────┘
        │ (batch, run once)                      │ (live, per request)
        ▼                                         ▼
   data/results.json  ◀────────  FastAPI (api/main.py)  ── REST ──▶  React SPA (web/)
```

**No RAG / KG / vector DB / SQL.** The whole JD fits in the prompt; an LLM + JSON
schema subsumes "NER + embeddings." Extra infra adds failure surface.

**DRY trust (review fix #5):** `core.process_jd()` is the **only** place
extract→enrich→verify runs. The batch pipeline and the API `/extract` endpoint both
call it, so the live paste-box result **cannot diverge** from the dashboard's logic.

**Run-once + cache.** The 15 seeds are processed **once, off-stage**, written to
`data/results.json`, and committed. SHA-256 dedup (hash over `raw_jd`) makes re-runs
cost 0 calls. The LinkedIn 949 run is out of scope.

**Provider:** Gemini 2.5 Flash via `google-genai`; env key **`GOOGLE_API_KEY`**.
`temperature = 0` (review fix #7 — reproducible extraction), JSON output mode.

---

## 5. The data contract

### 5.1 What the LLM returns — `JobExtractionSchema` (FLAT, MINIMAL, shape-only)

```python
class SeniorityTier(str, Enum):
    INTERNSHIP = "Internship"
    ENTRY      = "Entry-Level"
    MID        = "Mid-Level"
    SENIOR     = "Senior"
    EXECUTIVE  = "Executive"
    UNCERTAIN  = "Uncertain"      # MANDATORY when signals are absent — never guess

class JobExtractionSchema(BaseModel):
    one_line_summary:       str        # INDICATIVE, not verified — see R11
    seniority_level:        SeniorityTier
    required_skills:        list[str]  # 0–7; ONLY skills explicitly in the text. NO floor.
    raw_text_justification: str        # EXACT substring of the JD proving the seniority call
```

> **STRICT — prompt and schema MUST agree:**
> - **No minimum skill count.** 2 real skills → return 2. Never pad. (Old "5–7" was a bug.)
> - Absent years/scope/reporting signals → return `Uncertain`. Never "infer the closest tier."
> - The few-shot MUST be the **negative case** (`"rockstar mentality, python and stuff"` → `Uncertain`, 1 skill).
> - **The schema validates SHAPE ONLY (review fix #6).** All cleaning/truncation
>   happens in the pipeline (§7), not in field validators — one home for logic.

### 5.2 What gets written to `results.json` — `JobRecord`

| Field | Source | Notes |
|---|---|---|
| id, role, title, input_format | passthrough | from the seed |
| one_line_summary | **LLM** | **indicative, unverified — rendered separately (R11)** |
| ai_seniority, required_skills, raw_text_justification | **LLM** | §5.1 |
| native_label | deterministic | seniority word stated in the title/text (§9), else null |
| **is_verified** | deterministic | normalized match of quote in text, len ≥ 25 (R2) |
| **audit_mismatch** | deterministic | conservative ordinal rule (§5.5) |
| **bias_flags** | deterministic | wordlist ∩ text; surfaced as "flagged for review" |
| **pay_range_present** | deterministic | regex for ₹ / LPA / lakh / numeric range |
| **quality_score** + **score_breakdown** | deterministic | composite 0–100 **with component list** (§5.4) |
| **content_hash** | deterministic | SHA-256(`raw_jd`) — dedup (review fix #7) |
| **status** | deterministic | `ok` / `unverified` / `failed` |

### 5.3 Storage — flat JSON

`data/results.json`: a list of `JobRecord` objects. FastAPI loads it on startup and
serves it. CSV export is an endpoint (`/api/export.csv`), not the store. At 15 rows,
no database is warranted.

### 5.4 JD quality score (transparent, not a black box)

Deterministic 0–100, and the API returns the **component breakdown** so the UI shows
*why* (review/product fix), e.g. `+25 level · +20 verified · 0 pay · +10 no-bias …`.

| Signal | Points |
|---|---|
| Skills extracted ≥ 3 | +20 |
| Skills extracted ≥ 6 | +10 |
| Seniority NOT Uncertain | +25 |
| is_verified = True | +20 |
| pay_range_present = True | +15 |
| bias_flags empty | +10 |

> It is a **relative completeness** score, not an absolute grade — the UI labels it
> that way. (Most drafts lack pay, so scores cluster; that's fine for sorting.)

### 5.5 Conservative audit_mismatch rule

`experienceLevel` dropdowns are self-selected and "Mid-Senior" spans Mid+Senior, so
a naive `!=` manufactures mismatches. Use an ordinal gap:

```python
ORDINAL = {"Internship":0,"Entry-Level":1,"Mid-Level":2,"Senior":3,"Executive":4}
def audit_mismatch(native, ai):
    if native is None or ai == "Uncertain": return False
    return abs(ORDINAL[ai] - ORDINAL[native]) >= 2   # flag only a real gap
```

UI framing: "posting metadata and the text disagree — worth a look," **never** "the
title lies." Each flag MUST show the grounding quote. Built-in demos: seed_010/013/014.

---

## 6. ANTI-HALLUCINATION ENFORCEMENT (hard contract, enforced in code)

**R1 — Grounding quote mandatory** for the seniority call (exact source substring).

**R2 — Verification gate, NORMALIZED (review fix #2).** Brittle exact-substring
matching false-negatives on whitespace/newlines (the intake-form seeds contain `\n`).
Normalize both sides first:
```python
def _norm(s): return " ".join(s.split()).casefold()   # collapse all whitespace + casefold
quote = extraction.raw_text_justification.strip()
is_verified = len(quote) >= 25 and _norm(quote) in _norm(description)
if not is_verified:
    record.seniority_level = "Uncertain"; record.status = "unverified"
```

**R3 — Skills traceable, word-boundary matched.** `\bgo\b`, not bare `"go" in text`.
Post-filter drops any skill not found (via the canonical-synonym map).

**R4 — `Uncertain` is mandatory** when signals are absent. Enforced by the negative few-shot.

**R5 — Deterministic fields cannot hallucinate.** bias = wordlist ∩ text; pay = regex.

**R6 — No enrichment beyond the text.** No skills from the title, no "commonly required," no padding.

**R7 — Determinism.** `temperature = 0`, JSON/structured mode.

**R8 — Validate + bounded retry.** Pydantic (shape) → on error retry ≤2× → else `status=failed`. Never guess.

**R9 — Hallucination measured HONESTLY (not circular).** Eval (§10) reports **both**:
*pre-filter* rate (skills the model emitted that were absent from the text — the real
model-honesty number) and *post-filter* (0% by construction). A bare "0%" is disallowed.

**R10 — Provenance visible.** Every AI seniority value in the UI exposes its grounding
quote (hover/expand — trivial in React). Nothing shown as fact without the receipt.

**R11 — The summary is INDICATIVE, not verified (review fix #1).** `one_line_summary`
is free LLM prose with no grounding. It MUST be visually marked as "generated /
indicative" and **excluded from the "every output is traceable" claim**, which covers
only seniority (R1) and skills (R3). Do not present the summary as a verified fact.

---

## 7. Post-processing pipeline (`core.process_jd`, order matters — the ONE path)

For each JD, after the LLM call:
1. Validate shape against `JobExtractionSchema` (retry ≤2× per R8).
2. Skills: `.strip().lower()` → strip trailing punctuation → **R3 word-boundary filter** → cap `[:7]`. No floor.
3. Summary: first sentence — split on `". "` (period+space), not bare `.` (protects "Node.js", "3.5 years"). Tag as indicative (R11).
4. **R2 normalized verification gate** → set `is_verified`; downgrade to `Uncertain` if unverified.
5. Enrichment: bias wordlist, pay-range regex (R5).
6. `native_label` (§9) → `audit_mismatch` (conservative rule §5.5).
7. `quality_score` + `score_breakdown` (§5.4); `content_hash`; `status`.

> Both `pipeline.py` (batch) and `api/main.py` `/extract` call this exact function.

---

## 8. UI — React SPA + FastAPI backend

> Moving off Streamlit **resolves** the prior limitations: per-row download buttons,
> hover grounding-quotes, before/after contrast, and a visual verified-vs-generated
> distinction are all native in React.

### 8.1 Backend — FastAPI (`api/main.py`)

| Method · Endpoint | Returns | Notes |
|---|---|---|
| `GET /api/records` | all `JobRecord`s | from `results.json`; dashboard load = **0 LLM calls** |
| `GET /api/records/{id}` | one record + grounding | for the detail panel |
| `POST /api/extract` | `{ record }` for pasted `{ text }` | **the only live LLM call**; calls `core.process_jd` |
| `GET /api/kpis` | counts + fractions | review fix: **counts, not bare %** at n=15 |
| `GET /api/skills` | skill → frequency | the light "skills mentioned" view |
| `GET /api/records/{id}/docx` | corrected JD `.docx` | `python-docx`; per row + paste box (§8.3) |
| `GET /api/export.csv` | all records as CSV | bulk export |

CORS open to the Vite dev origin. Pydantic response models = typed contract shared
with the React client.

### 8.2 Frontend — React (Vite + TypeScript), production-quality

Component system: **Tailwind + shadcn/ui** (clean, accessible, not templated-looking).
Typed `api.ts` fetch client off the FastAPI Pydantic models.

```
PASTE BOX  (the hero — ~70% of UI effort)
  textarea → [ Process ] → POST /api/extract → result card
  ┌─ BEFORE (raw draft) ─────┐   ┌─ AFTER (normalized) ──────────────┐
  │ "senior software eng,    │   │ Software Engineer — Entry-Level   │  ← VERIFIED block
  │  java spring mysql,      │ → │ Skills: java · spring boot · mysql│     (quote on hover)
  │  1-2 yrs, gets tasks…"   │   │ Verified: "1-2 yrs exp is fine"   │
  └──────────────────────────┘   │ ─ generated ─                     │  ← INDICATIVE block,
                                  │ Summary: An entry role focused…   │     visually distinct (R11)
                                  │ ⚑ Level: title "senior" → Entry   │  ← CORRECTIONS = visual hero
                                  │ ⚑ No pay range — candidates skip  │
                                  │ Score 45/100  (+25 level …)       │
                                  │ [ ⬇ Download .docx ] [ 📋 Copy ]  │
                                  └────────────────────────────────────┘

DASHBOARD
  KPI strip   roles processed · # flagged for review · # leveling flags ·
              # with pay range · hallucinated-skill rate (model X% → 0% shipped)
              → COUNTS + fractions ("3 of 15"), not bare percentages
  Board       sortable table: role · true level · skills · ⚑flags · score;
              row-select → detail panel with grounding quote + .docx download
  Leveling    the ~3 planted mismatch cases, each as a card with its receipt
  Skills      "skills mentioned across processed drafts" (light bar list; NOT "demand")
```

**Design rules (enforced):** verified fields and the indicative summary are
visually separated (R11); corrections are the visual hero of the card; the
hallucination KPI is prominent (it's the differentiator); small-n numbers shown as
counts/fractions.

### 8.3 Corrected JD download (feature 7)

**Template reconstruction, NOT LLM rewriting** — uses only verified fields; zero new
call; cannot hallucinate. `.docx` via `python-docx`, served by `/api/records/{id}/docx`
and from the paste-box card. Plain-text/copy is the fallback if docx slips. Body:
role + level · skills (traced) · experience (from the quote) · pay-range or "add one"
· corrections (bias flags, level mismatch only if flagged).

---

## 9. Test data strategy — what we run NOW vs later

| Data | Stage | Use NOW? | Notes |
|---|---|---|---|
| `talentsync/synthetic_seeds.py` (15 hand-crafted) | Stage-1 raw input | **YES — this is the run** | already written (0 calls to create), **fully labeled**; run `core.process_jd` once (~15 calls) → `results.json` |
| `data/synthetic_jds.csv` (≈60 generated) | Stage-1 | optional | denser UI only; **excluded from accuracy** (self-consistency — review fix #3) |
| `LinkedIn_Jobs_Data_India.csv` (949) | Stage-5 | **NO — later** | do not touch; the live-req-portfolio audit, run when ready |

> **Consequence:** seeds are Stage-1 *drafts* → this build demos the **Quality Gate**
> (paste → normalize). They are labeled, so §10 gives real precision/recall. The
> Stage-5 "audit your live reqs" visual is deferred to the LinkedIn run.
>
> **Leveling on synthetic:** no `experienceLevel` dropdown — set `native_label` =
> the seniority word in the title/text (seed_013 says "senior", text reads Entry).
> Demos: seed_010, seed_013, seed_014.

---

## 10. Eval (`eval.py`) — proven honestly

Run `core.process_jd` over the **15 hand-written seeds only** and report:
- **Seniority accuracy (n=15)** — real number (seeds carry `actual_seniority`), shown
  **case-by-case** with the quote. State "labeled seed set, not a population benchmark."
  Mismatch seeds (010/013/014) MUST be caught.
- **Skill precision / recall** vs `skills_present`.
- **Hallucinated-skill rate — pre- AND post-filter** (R9).
- **Verification rate** — % of quotes (≥25, normalized) found in text.

> **Do NOT report accuracy on the generated set** — Gemini-generated then
> Gemini-extracted is self-consistency, not accuracy (review fix #3).

---

## 11. File structure

```
d:\project\
  talentsync\                 # Python engine
    __init__.py
    contracts.py              # SeniorityTier (+UNCERTAIN), JobExtractionSchema (shape only)
    prompts.py                # SYSTEM_PROMPT + negative few-shot + USER_TEMPLATE (R1,R4,R6)
    llm.py                    # extract(description) -> JobExtractionSchema (R7,R8)
    enrich.py                 # bias wordlist + pay regex + skill canonical map + quality_score (R5)
    verify.py                 # R2 normalized gate + R3 word-boundary filter
    core.py                   # process_jd(text): extract→enrich→verify  ← shared by batch + API
    pipeline.py               # batch: seeds → core.process_jd → data/results.json
    eval.py                   # §10
    synthetic_seeds.py
  api\                        # FastAPI backend
    main.py                   # endpoints (§8.1)
    docx_builder.py           # corrected-JD .docx
  web\                        # React (Vite + TS) frontend
    src\
      api.ts                  # typed fetch client
      components\             # PasteBox, BeforeAfter, ResultCard, KpiStrip, Board, LevelingView, SkillsView
      App.tsx
    index.html
    package.json
  data\
    results.json              # cached output from the 15 seeds (committed)
  LinkedIn_Jobs_Data_India.csv  # untouched (later stage)
  BUILD_SPEC.md
  PLAN.md                     # original dataset analysis only
  .env                        # GOOGLE_API_KEY + model
```

---

## 12. Build plan (~3 days)

### Day 1 — engine + API (text → trustworthy structured data, served)
| Block | Build | Checkpoint |
|---|---|---|
| Morning | `contracts.py` (+UNCERTAIN, shape-only), `prompts.py` (negative few-shot), `llm.py` | ✅ one seed → valid object + quote |
| Afternoon | `enrich.py`, `verify.py` (normalized R2, word-boundary R3), `core.py`, `pipeline.py` | ✅ `core.process_jd` green on seeds (stub the LLM first, 0 calls) |
| Evening | run the **15 seeds once** → `results.json`; `eval.py`; FastAPI endpoints serving the JSON | ✅ `GET /api/records` + accuracy/pre-post hallucination numbers |

### Day 2 — the hero (paste box) + Board
| Block | Build | Checkpoint |
|---|---|---|
| Morning | React scaffold (Vite+TS+Tailwind+shadcn), `api.ts`, KPI strip, Board + detail panel | ✅ dashboard renders from the API |
| Afternoon | Paste box → `POST /api/extract` → result card with **before/after** + verified-vs-generated split | ✅ live paste works end-to-end |
| Evening | `.docx` download (row + paste box); corrections styling | ✅ download a corrected JD |

### Day 3 — finish + polish + demo
| Block | Build | Checkpoint |
|---|---|---|
| Morning | Leveling view (3 cards) + light Skills view; CSV export | ✅ all surfaces render |
| Afternoon | visual polish, empty/error/loading states, accessibility pass | ✅ feels production-quality |
| Evening | demo script (lead with paste box), hero metric; *(stretch)* numpy-cosine | ✅ end-to-end demo runs |

---

## 13. Out of scope (do not let these eat the clock)
RAG · KG · vector DB · SQL/Mongo cluster · auth / multi-user · async at scale ·
processing all 949 rows · real ATS integration · scraping · Chrome extension ·
**rewriting the Python engine in Node** · SSR/Next.js (Vite SPA is enough) ·
ranking view · incremental-upload flow · "production-grade at scale" claims.

---

## 14. Definition of done
- `results.json` from the 15 seeds; every record validated, `status` set.
- FastAPI: `/api/records`, `/api/extract`, `/api/kpis`, `/api/skills`, `/api/records/{id}/docx`, `/api/export.csv` all work; dashboard load = **0 LLM calls**.
- React: KPI strip + Board + paste box (with before/after) + leveling + skills views render; production-quality look (Tailwind/shadcn), loading/error/empty states.
- Paste box normalizes a fresh JD live (the only runtime LLM call).
- **Verified fields and the indicative summary are visually distinct (R11).**
- Every AI seniority value exposes its grounding quote (R10).
- `eval.py` prints: seniority accuracy (n=15, case-by-case), skill P/R, **pre- AND post-filter** hallucination, verification rate.
- No overclaiming: bias = "flagged for review"; pay = "conversion signal," not compliance; summary = "indicative," not verified.
- Corrected `.docx` downloads from a row and the paste box.

---

## 15. Sources
- Bersin — Fixing Your Job Architecture: https://joshbersin.com/2021/09/fixing-your-job-architecture-now-a-business-critical-process/
- LinkedIn — Future of Recruiting 2025: https://business.linkedin.com/talent-solutions/resources/future-of-recruiting
- Textio — Language predicts the gender of your hire: https://textio.com/blog/language-in-your-job-post-predicts-the-gender-of-your-hire
- Ongig — JD writing software: https://blog.ongig.com/job-descriptions/job-description-writing-software/
- Datapeople vs Ongig (Square 25%): https://datapeople.io/comparison/datapeople-vs-ongig/
- Deel — Job Level Classification: https://www.deel.com/blog/job-level-classification/
- Indeed India — salary transparency >50% (2025): https://www.storyboard18.com/how-it-works/salary-transparency-gains-momentum-in-india-over-50-of-job-postings-now-include-pay-info-indeed-data-76695.htm
- Lightcast — Open Skills: https://lightcast.io/open-skills/faqs
- SHRM — The Real Costs of Recruitment: https://www.shrm.org/topics-tools/news/talent-acquisition/real-costs-recruitment
- Metaview — intake calls / who writes the JD: https://www.metaview.ai/resources/blog/what-is-a-hiring-manager
- PARSE (flat schemas for extraction): https://arxiv.org/abs/2510.08623
- ODKE+ (evidence-grounded extraction): https://arxiv.org/pdf/2509.04696
```
