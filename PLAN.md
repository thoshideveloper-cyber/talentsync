# TalentSync — Job Description Intelligence Platform
**"Paste any job ad — watch it normalize live."**

## Problem Statement
Recruiters and leaders drown in inconsistent, buzzword-heavy job posts. TalentSync reads
them like a skeptical senior recruiter — stripping fluff to expose real skills, true
seniority, and exactly where the official title disagrees with the actual work.

The signature insight: **audit_mismatch** — postings where the org's label says one
thing and the description text proves another.

---

## Dataset Reality (949 rows, LinkedIn_Jobs_Data_India.csv)

| Finding | Detail | Consequence |
|---|---|---|
| `experienceLevel` is dirty | `Full-time` (87), `Not Applicable` (71), `Part-time` (1) are NOT seniority | Map these to `None`; exclude from `audit_mismatch` |
| `Skill:/Exp:` prefix is rare | Only 17 / 16 rows have it | Treat as bonus hint, not ground truth |
| 135 duplicates exist | 814 unique of 949 `company+title` pairs | SHA-256 idempotency guardrail is genuinely needed |
| Descriptions are rich | Avg 2,530 chars, max 10,380, only 5 rows < 200 chars | Drop <200; no "massive dump" exclusion needed |
| Geography is demo-ready | Bengaluru 196, Mumbai 123, Gurugram 67, Pune 62… | "tech hub breakdown" chart lands well |

### Corrected Taxonomy Map
```python
NATIVE_TO_CANONICAL = {
    "Internship":       "Internship",
    "Entry level":      "Entry-Level",
    "Associate":        "Entry-Level",
    "Mid-Senior level": "Mid-Level",
    "Director":         "Senior",       # flip to "Executive" if preferred
    "Executive":        "Executive",
    # not seniority — no ground truth → exclude from audit_mismatch
    "Full-time":        None,
    "Part-time":        None,
    "Not Applicable":   None,
}
```

---

## Phased Roadmap

| Phase | Theme | What ships | Demo hook |
|---|---|---|---|
| **0** | Foundation | venv, `.env`, Pydantic contract, load + clean | *(internal)* |
| **1** | **Thin Slice (MVP)** | `extract()` on ~30 sampled rows → `results.csv` → Streamlit table + paste box | "Paste any JD — see it normalize live." |
| **2** | Scale & Resilience | Full 949 rows, async + `Semaphore(5)` + `tenacity`, SHA-256 idempotent upsert | "Whole market, safely re-runnable." |
| **3** | Trust & Audit | Verbatim-quote check, skill normalization, `audit_mismatch`, mini eval harness | "Every datapoint is verifiable — here's where titles lie." |
| **4** | Executive Dashboard | KPIs, hub breakdown, skill-frequency bars, mismatch filter, sandbox | "At-a-glance talent intelligence." |
| **5** | Differentiators | JD-vs-JD compare, skill-gap vs candidate, demand heatmap, export, deploy | "Compare roles / score a résumé / share a link." |

**Build order rule:** thin slice first (Phase 1 touches every layer), then thicken
each layer 2→5. Don't perfect any single layer before the end-to-end slice works.

---

## Phase 1 — Thin Slice Detail

### Goal
One verifiable record, end to end, with a live demo. Boring and working beats polished and broken.

### File Structure
```
d:\project\
  talentsync/
    __init__.py
    contracts.py     # SeniorityTier(Enum) + JobExtractionSchema(BaseModel)
    prompts.py       # SYSTEM_PROMPT, FEWSHOT, USER_TEMPLATE
    llm.py           # extract(description) -> JobExtractionSchema
    pipeline.py      # load -> sample 30 balanced rows -> extract -> results.csv
  app.py             # Streamlit: table + paste box
  results.csv        # output (gitignored)
  .env               # GROQ_API_KEY, GROQ_MODEL
  PLAN.md            # this file
```

### Done-When Checklist
- [ ] `contracts.py` imports and validates a hand-written dict
- [ ] One real JD through `extract()` returns a valid `JobExtractionSchema` object
- [ ] `pipeline.py` produces `results.csv` with ~30 clean rows
- [ ] Paste a JD in `app.py` → see structured output

### LLM Config
- Provider: Groq
- Model: `llama-3.3-70b-versatile`
- `temperature=0.1`
- `response_format={"type": "json_object"}`
- On `ValidationError`: retry up to 2×; mark row `failed` after that (never crash)

### Post-Processing Rules (apply after each extraction)
1. Skills: `.strip().lower()` → drop trailing punct → cap at `[:7]`
2. Summary: truncate to first sentence (split on first `.`)
3. Verification: `is_verified = extraction.raw_text_justification.lower() in description.lower()`
4. Mismatch: if `canonical_label is not None` and `canonical_label != ai_seniority` → `audit_mismatch = True`

---

## Master Prompt (see prompts.py)

Two design decisions grounded in research:
- **For Groq/Llama JSON mode**: state the keys inline + provide one worked few-shot
  example. Few-shot measurably improves schema adherence (PARSE, arXiv 2510.08623).
- **`raw_text_justification`**: the research-backed "grounding quote" technique for
  hallucination detection (Willison, ODKE+). Cheapest trust mechanism available.

> Note: If switching to Gemini native structured output later, **remove** the schema
> description from the prompt — Google explicitly states it reduces output quality.

---

## Research Sources
- Simon Willison — schema-first extraction + grounding quotes: https://simonwillison.net/2025/Feb/28/llm-schemas/
- PARSE (arXiv 2510.08623) — flat schemas beat nested for extraction reliability: https://arxiv.org/abs/2510.08623
- ODKE+ (arXiv 2509.04696) — evidence-grounded extraction verification: https://arxiv.org/pdf/2509.04696
- Maxim — clarity/structure + "never invent data": https://www.getmaxim.ai/articles/a-practitioners-guide-to-prompt-engineering-in-2025/
- Google AI Structured Outputs: https://ai.google.dev/gemini-api/docs/structured-output
