"""
tests/test_demo_batch.py
────────────────────────
Compliance-detection unit tests for the three AI Engineer demo JDs
(batch_4_ai_engineer_demo).  No LLM calls, no database, no HTTP.
Tests run the deterministic compliance engine directly.

Each JD is expected to produce a specific set of rule_id violations that
make it interesting for a live product demo.
"""
import pathlib
import pytest
from talentsync.compliance import run_all_compliance_checks, gate_verdict

BATCH = pathlib.Path(__file__).parent.parent / "sample_batches" / "batch_4_ai_engineer_demo"


# ── Helpers ───────────────────────────────────────────────────────────────────

def load(filename: str) -> str:
    return (BATCH / filename).read_text(encoding="utf-8")


def rule_ids(text: str) -> set[str]:
    findings = run_all_compliance_checks(text)
    return {f.rule_id for f in findings}


# ── JD 1: GenAI Platform Engineer ────────────────────────────────────────────
# Expected violations: age cap, gender preference, inclusive-language buzzwords,
# no pay disclosure.

class TestGenAIPlatformEngineer:
    JD = load("ai_engineer_genai_platform.txt")

    def test_age_cap_flagged(self):
        assert "filter.age_cap" in rule_ids(self.JD)

    def test_gender_preference_flagged(self):
        assert "filter.gender_preference" in rule_ids(self.JD)

    def test_inclusive_language_flagged(self):
        ids = rule_ids(self.JD)
        # language.inclusive or any sub-rule (e.g. language.inclusive.rockstar)
        assert any(r.startswith("language.inclusive") for r in ids)

    def test_no_pay_disclosure(self):
        assert "pay.disclosure_absent" in rule_ids(self.JD)

    def test_verdict_is_warn_or_fail(self):
        findings = run_all_compliance_checks(self.JD)
        assert gate_verdict(findings) in ("warn", "fail")

    def test_minimum_violation_count(self):
        # Expect at least 4 distinct flags for a meaningful demo
        assert len(rule_ids(self.JD)) >= 4


# ── JD 2: ML Engineer – LLM Fine-Tuning ──────────────────────────────────────
# Expected violations: freshers-only restriction, community/caste filter,
# no pay disclosure.

class TestMLEngineerLLMFineTuning:
    JD = load("ml_engineer_llm_finetuning.txt")

    def test_freshers_only_flagged(self):
        assert "filter.freshers_only" in rule_ids(self.JD)

    def test_community_caste_flagged(self):
        assert "filter.community_caste" in rule_ids(self.JD)

    def test_no_pay_disclosure(self):
        assert "pay.disclosure_absent" in rule_ids(self.JD)

    def test_verdict_is_warn_or_fail(self):
        findings = run_all_compliance_checks(self.JD)
        assert gate_verdict(findings) in ("warn", "fail")

    def test_minimum_violation_count(self):
        assert len(rule_ids(self.JD)) >= 3


# ── JD 3: AI Infrastructure Engineer – Model Serving ─────────────────────────
# Expected violations: disability exclusion, maternity-status filter,
# no pay disclosure.

class TestAIInfraEngineerModelServing:
    JD = load("ai_infra_engineer_model_serving.txt")

    def test_disability_exclusion_flagged(self):
        assert "filter.disability_exclusion" in rule_ids(self.JD)

    def test_maternity_status_flagged(self):
        assert "filter.maternity_status" in rule_ids(self.JD)

    def test_no_pay_disclosure(self):
        assert "pay.disclosure_absent" in rule_ids(self.JD)

    def test_verdict_is_warn_or_fail(self):
        findings = run_all_compliance_checks(self.JD)
        assert gate_verdict(findings) in ("warn", "fail")

    def test_minimum_violation_count(self):
        assert len(rule_ids(self.JD)) >= 3


# ── Cross-batch sanity ────────────────────────────────────────────────────────

@pytest.mark.parametrize("filename", [
    "ai_engineer_genai_platform.txt",
    "ml_engineer_llm_finetuning.txt",
    "ai_infra_engineer_model_serving.txt",
])
def test_every_jd_has_at_least_one_high_risk_violation(filename):
    from talentsync.compliance import get_risk_tier
    text = load(filename)
    findings = run_all_compliance_checks(text)
    high_risk = [f for f in findings if get_risk_tier(f.rule_id) == "high_risk"]
    assert len(high_risk) >= 1, (
        f"{filename} produced no high_risk findings — "
        "demo will not show the critical violation flow"
    )
