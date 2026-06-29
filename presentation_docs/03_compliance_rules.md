# Compliance Rule Engine

## Design Principles

- **100% deterministic regex.** Zero LLM calls in the compliance check path.
- **Precision target:** ≥95% recall on the high-risk rule class.
- **Pilot gate:** WARN-ONLY mode — no hard block. The "fail" result tier is reserved for future corpus-verified, lawyer-pinned statutory rules.
- **Scope limitation (stated explicitly to users):** These detectors catch explicit written filters only. Implicit bias in neutral language is outside scope. These findings are not a legal opinion.
- **Dynamic sub-rules:** The `language.inclusive` rule generates sub-rule IDs dynamically per detected term (e.g., `language.inclusive.rockstar`). The term list contains **29 terms**.
- **Legal framing note:** Most high-risk rules do not map to a codified private-sector statutory prohibition in India — Articles 15/16 of the Constitution bind the State, not private employers. The risk is litigation exposure, civil claims, and ESG/DEI governance harm. The term "risk basis" is used below instead of "statutory basis" to reflect this accurately.

---

## Rule Catalogue

### HIGH-RISK TIER — 7 Rules

Override requires Approver or Admin role with a mandatory written business justification. The justification is written to the append-only `audit_log` table with actor ID, timestamp, job ID, version ID, and justification text. This record cannot be updated or deleted.

---

#### `filter.age_cap`
**Short name:** Age Cap

**What it detects:**
- Age limits, age caps, age ranges specified in years
- Phrases: "must be under/above N years", "maximum age", "min age", "age bracket", "age criteria", "age group"

**Exclusion guard:**
- "age no bar" is affirmatively inclusive — the engine explicitly excludes this phrase from triggering the rule

**Risk basis:**
- Litigation and ESG/DEI exposure. No codified private-sector age-discrimination statute in India — Art. 15/16 bind the State, not private employers. Civil-claims and reputational harm risk is real. Aligns with Code on Wages 2019 anti-discrimination principles. Removal also broadens the candidate pool.

---

#### `filter.gender_preference`
**Short name:** Gender Preference

**What it detects:**
- "male candidates only", "male preferred", "male required"
- "female candidates only", "female preferred"
- Gendered pronoun requirements used as mandatory candidate attributes ("he/him required", "she/her only")
- "gents only", "ladies preferred"

**Risk basis:**
- High litigation/ESG risk. The Equal Remuneration Act 1976 (now subsumed by Code on Wages 2019) prohibits sex-based discrimination in recruitment. A gender filter in the advertisement is direct evidence of such discrimination and is a common ground for civil claims and reputational harm. Legal review recommended before posting; genuine occupational qualification must be documented if the restriction is retained.

---

#### `filter.marital_status`
**Short name:** Marital Status

**What it detects:**
- "married candidates", "married persons preferred"
- "unmarried only", "single candidates preferred"
- Family-status conditions stated as hiring criteria

**Risk basis:**
- Litigation/ESG risk. Marital-status preferences in hiring advertisements are considered discriminatory practice under modern ESG and HR governance frameworks and increase indirect-discrimination legal exposure. Legal review recommended.

---

#### `filter.community_caste`
**Short name:** Caste / Community / Religion

**What it detects:**
- Caste names or caste categories stated as hiring criteria
- Community references (religion, sect, regional community) as requirements
- SC/ST/OBC category references used as screening filters
- "General category only" stated as a hiring preference

**Risk basis:**
- High litigation and reputational risk. References to caste, community, religion, or reservation categories as a hiring criterion are inconsistent with India's constitutional non-discrimination principles (Art. 14–16) and with ESG/DEI governance standards. Stating a preference for any category — including "general category" — in a private job advertisement is a serious reputational and civil-claims exposure. Legal review strongly recommended; remove all category-based preferences.

---

#### `filter.disability_exclusion`
**Short name:** Disability Exclusion

**What it detects:**
- "able-bodied only"
- "no physical disability"
- "medically fit only" when framed as a blanket exclusion rather than a documented specific occupational requirement

**Risk basis:**
- High legal risk. The Rights of Persons with Disabilities (RPwD) Act 2016 prohibits discrimination against persons with disabilities at any stage of employment and requires reasonable accommodation. Blanket "able-bodied" or "no disability" filters are inconsistent with the RPwD Act unless tied to a genuine, documented occupational requirement. Replace with the specific physical task requirement if operationally necessary.

---

#### `filter.maternity_status`
**Short name:** Pregnancy / Maternity Status

**What it detects:**
- Pregnancy conditions ("must not be pregnant")
- Family-planning questions framed as hiring criteria ("no maternity plans")
- "no children" stated as a requirement

**Risk basis:**
- High legal risk. The Maternity Benefit Act 1961 protects women from adverse treatment connected to pregnancy and maternity. Screening candidates on pregnancy or family-planning intentions is a discriminatory practice; presence in the advertisement constitutes direct evidence of discriminatory intent. Remove any pregnancy or family-planning condition unconditionally.

---

#### `filter.freshers_only`
**Short name:** Freshers Only

**What it detects:**
- "freshers only", "only fresh graduates"
- "experienced candidates need not apply"
- Blanket exclusion of candidates with prior work experience

**Risk classification:**
- Indirect age discrimination — experienced candidates are statistically older
- Shrinks the qualified talent pool without a documented occupational justification

---

### ADVISORY TIER — 2 Rules

Best-practice guidance. No current statutory mandate. A recruiter can acknowledge and proceed without an override justification.

---

#### `language.inclusive`
**Short name:** Inclusive Language

**What it detects:**
Exclusionary performance-culture buzzwords known to deter applicants from non-dominant cultural backgrounds. Current term list includes: "rockstar", "ninja", "guru", "dynamic personality", "go-getter", "hustler", and similar.

**Rule ID format:** `language.inclusive.<term>` (e.g., `language.inclusive.rockstar`, `language.inclusive.ninja`)
Sub-rules are generated dynamically per detected term.

**Basis:**
- TalentSync inclusive-language advisory
- These terms demonstrably reduce applicant pool diversity without improving role specificity

---

#### `pay.disclosure_absent`
**Short name:** No Pay Disclosure

**What it detects:**
Fires when no salary figure, salary range, CTC range, or compensation disclosure of any kind is detected in the JD text.

**Basis:**
- Code on Wages 2019 — pay transparency principles
- Not a statutory mandate for job advertisements at this time — advisory only
- Pay disclosure improves candidate conversion rates and supports equal-pay audit practices

---

### QUALITY CHECKS — 2 Rules (LLM-based)

These checks run in the AI extraction pipeline — not the deterministic compliance engine. They are executed alongside seniority classification and quality scoring.

---

#### `quality.leveling_mismatch`
**Short name:** Leveling Mismatch

**Method:** LLM-based assessment

**How it works:**
The LLM compares the seniority tier implied by the job title against the seniority tier implied by the actual requirements in the JD body (years of experience, team size, reporting lines, scope of accountability).

**Seniority tier scale (ordinal):**

| Tier | Label |
|------|-------|
| 0 | Internship |
| 1 | Entry-Level |
| 2 | Mid-Level |
| 3 | Senior |
| 4 | Executive |

**Mismatch trigger threshold:** Gap of ≥2 ordinal tiers (conservative rule to minimize false positives on legitimate title conventions).

**Example:** Title states "Junior Developer" (tier 1 = Entry-Level) but body requires 10 years of experience and people management accountability (tier 3 = Senior) — a 2-tier gap → mismatch fires.

---

#### `quality.unverified_seniority`
**Short name:** Unverified Seniority

**Method:** LLM-based extraction

**How it works:**
The LLM attempts to extract a direct verbatim quote from the JD text that grounds the classified seniority level. If no grounding sentence exists in the document, seniority is marked as unverified (`is_verified = false`).

The extracted quote is stored in the `raw_text_justification` column of `jd_versions` and displayed in the Review step UI so the recruiter can assess it.

---

## Override Mechanism — Full Detail

**Who can override:** Approver and Admin roles only

**Process:**
1. Approver/Admin clicks Override on a high-risk finding
2. Override modal requires a mandatory written business justification — the field cannot be submitted empty
3. On submission, the following is written to `audit_log`:

| Field | Value |
|-------|-------|
| actor | User ID of the Approver/Admin who submitted the override |
| action | `compliance_override` |
| target_type | `jd_version` |
| target_id | UUID of the jd_version |
| detail | `{ rule_id, justification_text, result_overridden }` |
| ts | Server timestamp |
| tenant_id | Current tenant |

4. This record cannot be updated or deleted (DB-level REVOKE)
5. All override records are visible in the Insights tab → Compliance Posture → Recent Overrides panel

---

## Evidence Span Display

For every triggered rule, the `evidence_span` column stores the exact substring from the JD text that caused the rule to fire. This is displayed in the Review step UI as a highlighted quote, giving the recruiter direct traceability from finding to source text.
