"""
Phase 1 compliance detector golden set — 50 labeled JDs.

Structure:
  TRUE POSITIVES  — each should trigger the named rule at high_risk tier (25 JDs)
  ADVERSARIAL NEG — each should NOT trigger high_risk findings (25 JDs); may trigger advisory

Gate metric target: ≥95% precision on high_risk class.
All tests are pure-Python (no DB, no HTTP, no LLM calls).
"""
import pytest
from talentsync.compliance import (
    run_discriminatory_filter_checks,
    run_all_compliance_checks,
    gate_verdict,
    count_by_tier,
    RULE_CATALOGUE,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rule_ids(findings) -> list[str]:
    return [f.rule_id for f in findings]


def _has_high_risk(findings) -> bool:
    return any(f.risk_tier == "high_risk" for f in findings)


def _high_risk_rules(findings) -> set[str]:
    return {f.rule_id for f in findings if f.risk_tier == "high_risk"}


# ── Age cap true positives ────────────────────────────────────────────────────

AGE_TP = [
    "Software Developer. Age below 30 preferred. 3+ years Python. Salary: 15 LPA.",
    "Hiring! Age limit: 25-35 years. MBA required. Immediate joiners.",
    "Maximum age 28 years. Apply with resume. B.Tech required.",
    "Must be under 30 years of age. Strong communication skills needed.",
    "Age criteria: not more than 35 years of age as on date of application.",
    "Age group 22-30. Looking for enthusiastic professionals. AWS experience.",
    "Candidate must not be above 32 years. AWS and Python experience required.",
]


@pytest.mark.parametrize("jd", AGE_TP)
def test_age_cap_true_positive(jd):
    findings = run_discriminatory_filter_checks(jd)
    hr = _high_risk_rules(findings)
    assert "filter.age_cap" in hr, (
        f"Expected filter.age_cap in {hr!r} for JD: {jd[:80]!r}"
    )


# ── Gender preference true positives ──────────────────────────────────────────

GENDER_TP = [
    "Male candidates only. Outstation travel required. Salary: 8-12 LPA.",
    "Female candidates preferred for front-desk role. English fluency required.",
    "Gender: Male. 3+ years B2B sales experience. Delhi location.",
    "Ladies preferred for this role. Work from home option. 5+ years experience.",
    "Only male applicants will be considered. Night shift required.",
]


@pytest.mark.parametrize("jd", GENDER_TP)
def test_gender_preference_true_positive(jd):
    findings = run_discriminatory_filter_checks(jd)
    hr = _high_risk_rules(findings)
    assert "filter.gender_preference" in hr, (
        f"Expected filter.gender_preference in {hr!r} for JD: {jd[:80]!r}"
    )


# ── Marital status true positives ─────────────────────────────────────────────

MARITAL_TP = [
    "Must be single. Extensive travel required. 2+ years in FMCG sales.",
    "Unmarried candidates only. Pan-India relocation required.",
    "Preference for unmarried female candidates. Hostel accommodation provided.",
    "Marital status: Single preferred. Frequent travel to Tier-2 cities.",
]


@pytest.mark.parametrize("jd", MARITAL_TP)
def test_marital_status_true_positive(jd):
    findings = run_discriminatory_filter_checks(jd)
    hr = _high_risk_rules(findings)
    assert "filter.marital_status" in hr, (
        f"Expected filter.marital_status in {hr!r} for JD: {jd[:80]!r}"
    )


# ── Community / caste true positives ──────────────────────────────────────────

COMMUNITY_TP = [
    "Brahmin candidates preferred for temple management role. Sanskrit knowledge essential.",
    "From hindu family preferred. Temple pujari position available.",
    "OBC/SC candidates preferred. Government training scheme applicable.",
]


@pytest.mark.parametrize("jd", COMMUNITY_TP)
def test_community_caste_true_positive(jd):
    findings = run_discriminatory_filter_checks(jd)
    hr = _high_risk_rules(findings)
    assert "filter.community_caste" in hr, (
        f"Expected filter.community_caste in {hr!r} for JD: {jd[:80]!r}"
    )


# ── Freshers-only true positives ──────────────────────────────────────────────

FRESHERS_TP = [
    "Freshers only. 0-1 year experience. Python basics required. Salary: 3-4 LPA.",
    "Only freshers need apply. On-the-job training provided. 2024/2025 batch.",
    "Fresh graduates only. B.Tech CS 2024/2025 pass-outs. Day-1 joining.",
    "No experienced candidates please. We train from scratch. Stipend: ₹15,000.",
    "Experienced candidates need not apply. Looking for fresh minds.",
    "Just passed out of college? This role is for you. Freshers only.",
]


@pytest.mark.parametrize("jd", FRESHERS_TP)
def test_freshers_only_true_positive(jd):
    findings = run_discriminatory_filter_checks(jd)
    hr = _high_risk_rules(findings)
    assert "filter.freshers_only" in hr, (
        f"Expected filter.freshers_only in {hr!r} for JD: {jd[:80]!r}"
    )


# ── Adversarial negatives (must NOT trigger high_risk) ────────────────────────

ADVERSARIAL_NEG = [
    # Experienced-only (NOT freshers-only — the opposite restriction)
    "5+ years required. Strong Python. Salary: 20-30 LPA. No freshers.",
    # Explicit inclusive age statement
    "Equal opportunity employer. All genders, ages, backgrounds welcome. Salary: 12 LPA.",
    # Company name "Hero" — advisory only, not high_risk gender/age
    "Hero MotoCorp requires a Senior Software Engineer. 8+ LPA. Pune.",
    # "dynamic personality" — advisory only
    "Agile team. Dynamic personality is a plus. 3+ years Java experience.",
    # "rockstar developer" — advisory only, no high_risk
    "Fast-paced startup. Rockstar developer needed. Python. 10-15 LPA.",
    # "age no bar" — explicit inclusive guard suppresses age_cap
    "3-5 years of experience in sales. Age no bar. Open to all candidates.",
    # Clean JD — no flags
    "Salary: 15-20 LPA. Equal opportunity employer. 4+ years backend experience.",
    # Bachelor's degree — NOT marital status
    "Bachelor's degree in Computer Science required. 2+ years Python.",
    # "bachelor degree" (no apostrophe) — NOT marital status
    "Bachelor degree required. 2+ years experience in ML. Salary: 18 LPA.",
    # "single point of contact" — NOT marital status
    "Single point of contact for the project. PMP certified preferred.",
    # Open to freshers AND junior engineers (NOT freshers-only restriction)
    "Experience: 0-2 years. Entry level. Open to freshers and junior engineers. 4-6 LPA.",
    # "30 years old database" — age refers to a system, not a candidate
    "Our core banking system is 30 years old. Looking for a Senior DBA.",
    # "married life" in benefits — NOT marital status preference in hiring
    "Married life insurance benefits. Medical coverage. 8+ years experience required.",
    # "community manager" as a job title — NOT caste/community hiring criterion
    "Community manager role. Social media expertise. Salary: 6-9 LPA.",
    # "5 years of experience" — number + years, NOT an age cap
    "Senior Analyst. 5-8 years of experience in data engineering. AWS preferred.",
    # "should be above 5 years of experience" — experience, not age
    "Role requires candidates who should be above 5 years of experience in DevOps.",
    # "not more than 10 years of experience" — experience cap, not age cap
    "Not more than 10 years of experience required for this mid-level role.",
    # Explicit "no specific community preference" statement
    "Looking for IIT/IIM graduates. No specific community preference. 15 LPA.",
    # "freshers need not apply" — experienced-only, NOT freshers-only
    "Experienced candidate with 10+ years preferred. Freshers need not apply.",
    # "agile" / "tribe" / "culture fit" — advisory terms only
    "We value culture fit and work in small tribes. Agile. 5+ years React.",
    # "Digital native" — advisory only
    "Digital native with 3+ years mobile development. Flutter or React Native.",
    # "sharp candidates" — advisory only
    "Sharp candidates with killer instinct preferred. Sales role. 3-5 LPA.",
    # Gender-neutral by-design: "Candidates of any gender may apply"
    "All candidates welcome. Salary: 12-18 LPA. Python 3+ years. Hybrid.",
    # "energetic team" — advisory only, not high_risk
    "Join our energetic team. Self-starter attitude needed. 2+ years marketing.",
    # Just "MBA required" with no age/gender/marital filter
    "MBA required. 3+ years management consulting experience. Salary: 25 LPA.",
]


@pytest.mark.parametrize("jd", ADVERSARIAL_NEG)
def test_adversarial_no_high_risk(jd):
    findings = run_discriminatory_filter_checks(jd)
    hr = [f for f in findings if f.risk_tier == "high_risk"]
    assert not hr, (
        f"Unexpected high_risk finding(s) {[f.rule_id for f in hr]!r} "
        f"for adversarial JD: {jd[:80]!r}"
    )


# ── Gate verdict ──────────────────────────────────────────────────────────────

def test_gate_verdict_pass_on_clean_jd():
    clean = "Senior Python Engineer. 5+ years experience. Salary: 25-35 LPA. AWS required."
    findings = run_discriminatory_filter_checks(clean)
    assert gate_verdict(findings) == "pass"


def test_gate_verdict_warn_on_high_risk():
    jd = "Male candidates only. 3+ years experience."
    findings = run_discriminatory_filter_checks(jd)
    assert gate_verdict(findings) == "warn"


def test_count_by_tier():
    jd = "Male candidates only. Must be single. Rockstar developer needed."
    findings = run_all_compliance_checks(jd)
    counts = count_by_tier(findings)
    assert counts["high_risk"] >= 2  # gender + marital
    assert counts["advisory"] >= 1   # rockstar


# ── Evidence span is non-empty on every high_risk finding ────────────────────

def test_evidence_span_present():
    jd = "Male candidates only. Age below 30. Must be unmarried."
    findings = run_discriminatory_filter_checks(jd)
    for f in findings:
        if f.risk_tier == "high_risk":
            assert f.evidence_span, f"Missing evidence_span for rule {f.rule_id!r}"
            assert len(f.evidence_span) > 0


# ── Citation is present and non-empty for all rules ──────────────────────────

def test_rule_catalogue_has_citations():
    for rule_id, rule in RULE_CATALOGUE.items():
        assert rule.citation, f"Rule {rule_id!r} has empty citation"
        assert rule.risk_tier in ("high_risk", "advisory"), (
            f"Rule {rule_id!r} has unknown risk_tier {rule.risk_tier!r}"
        )


# ── run_all_compliance_checks covers both discriminatory + advisory ───────────

def test_all_checks_includes_pay_advisory():
    jd = "Software Engineer needed. Python 5+ years. No salary disclosed."
    findings = run_all_compliance_checks(jd)
    advisory_ids = [f.rule_id for f in findings if f.risk_tier == "advisory"]
    assert "pay.disclosure_absent" in advisory_ids


def test_all_checks_no_pay_advisory_when_pay_present():
    jd = "Software Engineer. Python 5+ years. Salary: 20-30 LPA."
    findings = run_all_compliance_checks(jd)
    ids = [f.rule_id for f in findings]
    assert "pay.disclosure_absent" not in ids


# ── Deduplication — same matched text must not produce duplicate findings ─────

def test_no_duplicate_on_identical_phrase():
    """A single occurrence of a phrase produces exactly one finding, not two."""
    jd = "Male candidates only."
    findings = run_discriminatory_filter_checks(jd)
    gender_findings = [f for f in findings if f.rule_id == "filter.gender_preference"]
    assert len(gender_findings) == 1, (
        f"Expected 1 finding for a single phrase; got {len(gender_findings)}"
    )


def test_two_distinct_phrases_produce_two_findings():
    """Two different discriminatory phrases in the same JD each produce a finding."""
    jd = "Male candidates only. Male candidates preferred."
    findings = run_discriminatory_filter_checks(jd)
    gender_findings = [f for f in findings if f.rule_id == "filter.gender_preference"]
    assert len(gender_findings) == 2, (
        f"Expected 2 findings for two distinct phrases; got {len(gender_findings)}"
    )


# ── Reservation-category / caste detection (regression: LogiTrack JD) ─────────

def test_reservation_category_preference_detected():
    """SC/ST/OBC vs 'general category' framing must flag filter.community_caste."""
    jd = (
        "Candidates from SC/ST/OBC categories may apply but preference will be "
        "given to general category candidates."
    )
    hr = _high_risk_rules(run_discriminatory_filter_checks(jd))
    assert "filter.community_caste" in hr


def test_slash_separated_categories_detected():
    jd = "Open to SC/ST/OBC candidates for this role. Salary: 8 LPA."
    hr = _high_risk_rules(run_discriminatory_filter_checks(jd))
    assert "filter.community_caste" in hr


def test_disability_exclusion_detected():
    jd = "We need able-bodied candidates only with no physical disability. 10 LPA."
    hr = _high_risk_rules(run_discriminatory_filter_checks(jd))
    assert "filter.disability_exclusion" in hr


def test_maternity_status_detected():
    jd = "Female candidates must not be pregnant and should not be planning a family."
    hr = _high_risk_rules(run_discriminatory_filter_checks(jd))
    assert "filter.maternity_status" in hr


def test_general_manager_title_not_flagged_as_category():
    """The word 'general' in a job title must NOT trigger a category finding."""
    jd = "General Manager - Operations. 10+ years experience. Salary: 30 LPA."
    hr = _high_risk_rules(run_discriminatory_filter_checks(jd))
    assert "filter.community_caste" not in hr


# ── Age no-bar guard ──────────────────────────────────────────────────────────

def test_age_no_bar_suppresses_age_cap():
    jd = "Looking for professionals. Age no bar. 3-5 years experience. Salary: 12 LPA."
    findings = run_discriminatory_filter_checks(jd)
    hr = _high_risk_rules(findings)
    assert "filter.age_cap" not in hr, (
        "age_cap should be suppressed when 'age no bar' is present"
    )
