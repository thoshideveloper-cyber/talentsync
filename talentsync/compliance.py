"""
Deterministic compliance checks for JD text — zero LLM calls.

Risk tiers (see PLAN_NEXT_FEATURES.md §Legal Framing):
  high_risk  — litigation / ESG risk. No verified statutory prohibition exists for
               private-sector in India yet; Art. 15/16 bind the State not private
               employers. Reputational and civil-claims exposure is real. "illegal"
               tier is intentionally ABSENT until rules are lawyer-verified and pinned
               to a specific statutory provision.
  advisory   — best-practice guidance; no statutory hook.

Gate in Phase 1 pilot: WARN-ONLY (no hard block). Override-with-justification writes
to audit_log. Hard block ("fail") is reserved for future corpus-verified rules.

Recall caveat: regex detectors catch explicit written filters; implicit bias in
otherwise-neutral language is out of scope. Corpus-backed precision target: ≥95% on
the high_risk class (filter.* rules).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ComplianceRule:
    rule_id: str
    risk_tier: str      # "high_risk" | "advisory"
    check_result: str   # "warn" (always in pilot; "fail" reserved)
    description: str
    citation: str


@dataclass(frozen=True)
class ComplianceFinding:
    rule_id: str
    risk_tier: str      # "high_risk" | "advisory"
    result: str         # "warn"
    evidence_span: str
    citation: str


# ── Rule catalogue ─────────────────────────────────────────────────────────────

RULE_CATALOGUE: dict[str, ComplianceRule] = {
    "filter.age_cap": ComplianceRule(
        rule_id="filter.age_cap",
        risk_tier="high_risk",
        check_result="warn",
        description="Job description contains an age cap or age-range filter.",
        citation=(
            "Litigation/ESG risk: age-based hiring filters expose the organisation to "
            "civil-claims and reputational harm. No codified private-sector "
            "age-discrimination statute in India (Art. 15/16 bind the State, not private "
            "employers), but the risk gradient is real. Recommend removal to broaden the "
            "candidate pool and align with ESG/DEI commitments."
        ),
    ),
    "filter.gender_preference": ComplianceRule(
        rule_id="filter.gender_preference",
        risk_tier="high_risk",
        check_result="warn",
        description="Job description expresses an explicit gender preference for candidates.",
        citation=(
            "Litigation/ESG risk: the Equal Remuneration Act 1976 (now subsumed by the Code "
            "on Wages 2019) prohibits sex-based discrimination in recruitment. A gender filter "
            "in the advertisement itself is direct evidence of such discrimination and is a "
            "common ground for civil claims and reputational harm. Remove the gender "
            "requirement unless a genuine occupational qualification applies; legal review "
            "recommended before posting."
        ),
    ),
    "filter.marital_status": ComplianceRule(
        rule_id="filter.marital_status",
        risk_tier="high_risk",
        check_result="warn",
        description="Job description expresses a marital-status preference.",
        citation=(
            "Litigation/ESG risk: marital-status preferences in hiring ads are considered "
            "discriminatory practice under modern ESG and HR governance frameworks and may "
            "increase indirect-discrimination legal exposure. Legal review recommended."
        ),
    ),
    "filter.community_caste": ComplianceRule(
        rule_id="filter.community_caste",
        risk_tier="high_risk",
        check_result="warn",
        description=(
            "Job description references caste, community, or religion as a hiring criterion."
        ),
        citation=(
            "High litigation and reputational risk: references to caste, community, religion, "
            "or reservation categories (SC/ST/OBC vs 'general category') as a hiring criterion "
            "are inconsistent with India's constitutional non-discrimination principles "
            "(Art. 14–16) and with ESG/diversity governance standards. Stating a preference "
            "for any category — including 'general category' — in a private job advertisement "
            "is a serious reputational and civil-claims exposure. Remove all category-based "
            "preferences; legal review strongly recommended."
        ),
    ),
    "filter.disability_exclusion": ComplianceRule(
        rule_id="filter.disability_exclusion",
        risk_tier="high_risk",
        check_result="warn",
        description=(
            "Job description excludes candidates on the basis of disability or medical status "
            "(e.g. 'able-bodied only', 'no physical disability')."
        ),
        citation=(
            "High legal risk: the Rights of Persons with Disabilities Act 2016 prohibits "
            "discrimination against persons with disabilities at any stage of employment and "
            "requires employers to provide reasonable accommodation. Blanket 'able-bodied' or "
            "'no disability' filters in a job advertisement are inconsistent with the RPwD Act "
            "unless tied to a genuine, documented occupational requirement. Remove the "
            "exclusion or replace it with the specific physical task requirement."
        ),
    ),
    "filter.maternity_status": ComplianceRule(
        rule_id="filter.maternity_status",
        risk_tier="high_risk",
        check_result="warn",
        description=(
            "Job description references pregnancy or family-planning status as a hiring "
            "criterion (e.g. 'must not be pregnant', 'no maternity plans')."
        ),
        citation=(
            "High legal risk: the Maternity Benefit Act 1961 protects women from adverse "
            "treatment connected to pregnancy and maternity. Screening candidates on pregnancy "
            "or family-planning intentions is a discriminatory practice and direct evidence of "
            "intent. Remove any pregnancy / family-planning condition from the advertisement."
        ),
    ),
    "filter.freshers_only": ComplianceRule(
        rule_id="filter.freshers_only",
        risk_tier="high_risk",
        check_result="warn",
        description=(
            "Job description restricts applications to freshers/new graduates, explicitly "
            "excluding experienced candidates."
        ),
        citation=(
            "Litigation/ESG risk: blanket 'freshers only' or explicit exclusion of "
            "experienced candidates may carry indirect age-discrimination risk and restricts "
            "the talent pool without a stated genuine occupational justification. Review "
            "whether the restriction is operationally necessary before posting."
        ),
    ),
    "language.inclusive": ComplianceRule(
        rule_id="language.inclusive",
        risk_tier="advisory",
        check_result="warn",
        description=(
            "Job description uses potentially exclusionary performance-culture buzzwords "
            "that may discourage diverse applicants."
        ),
        citation=(
            "TalentSync inclusive-language advisory: terms like 'rockstar', 'ninja', "
            "'dynamic personality' can deter applicants from non-dominant cultural "
            "backgrounds. Advisory only — no statutory hook. Rewording broadens the "
            "applicant pool."
        ),
    ),
    "pay.disclosure_absent": ComplianceRule(
        rule_id="pay.disclosure_absent",
        risk_tier="advisory",
        check_result="warn",
        description="No salary or compensation information found in the job description.",
        citation=(
            "Best-practice pay transparency: disclosing compensation improves candidate "
            "conversion rates and supports equal-pay principles under the Code on Wages 2019. "
            "Not a statutory mandate for job advertisements — advisory signal only."
        ),
    ),
}

# Utility: derive risk tier for a rule_id, including sub-rules (language.inclusive.rockstar)
def get_risk_tier(rule_id: str) -> str:
    if rule_id in RULE_CATALOGUE:
        return RULE_CATALOGUE[rule_id].risk_tier
    for key, rule in RULE_CATALOGUE.items():
        if rule_id.startswith(key + ".") or rule_id.startswith(key + "_"):
            return rule.risk_tier
    return "advisory"


# ── Pattern groups ────────────────────────────────────────────────────────────
# Each group is a list[re.Pattern]. Word boundaries are used throughout.
# Patterns requiring "age" context to avoid collisions with experience requirements
# use explicit "age" anchors or negative lookaheads for "of experience".

_AGE_PATTERNS: list[re.Pattern] = [
    # "age: 25", "age = 30-35", "age < 35", "age ≤ 35"
    re.compile(r"\bage\s*[:=<>≤≥]\s*\d+", re.IGNORECASE),
    # "age below/above/under/over/not more than 30"
    re.compile(
        r"\bage\s+(?:below|above|under|over|not\s+(?:more|less)\s+than|between)\s+\d+",
        re.IGNORECASE,
    ),
    # "maximum age", "max age", "minimum age", "min age" (with or without number)
    re.compile(r"\b(?:maximum|max|minimum|min)\s+age\b", re.IGNORECASE),
    # "age limit", "age bar", "age cap", "age criteria", etc.
    re.compile(
        r"\bage\s+(?:limit|bar|cap|criteria|criterion|bracket|group|range|requirement)\b",
        re.IGNORECASE,
    ),
    # "must be under 30 years" — requires "years" explicitly to avoid false-positives
    # on experience requirements like "should be above 5 years of experience".
    # Negative lookahead after "years" blocks "... years of experience/work/service".
    re.compile(
        r"\b(?:must|should|shall)\s+(?:not\s+)?be\s+"
        r"(?:under|below|above|not\s+more\s+than|not\s+over)\s+\d+\s+years?(?!\s+of\s+(?:experience|work|service|exp))\b",
        re.IGNORECASE,
    ),
    # "candidate must not be above 35 years"
    re.compile(
        r"\b(?:candidate|applicant|person|he|she)\s+(?:must|should|shall)\s+(?:not\s+)?be\s+"
        r"(?:below|under|above|over)\s+\d+",
        re.IGNORECASE,
    ),
    # "25-30 years of age" (explicitly "of age", not "of experience")
    re.compile(r"\b\d+\s*[-–—]\s*\d+\s+years?\s+of\s+age\b", re.IGNORECASE),
    # "not more than / not above / not exceeding 35 years of age"
    re.compile(
        r"\bnot\s+(?:more\s+than|above|exceeding)\s+\d+\s+years?\s+of\s+age\b",
        re.IGNORECASE,
    ),
    # "age no bar" is explicitly INCLUSIVE — excluded via a separate negative guard in _scan
]

_GENDER_PATTERNS: list[re.Pattern] = [
    # "male candidates only / preferred / required"
    re.compile(
        r"\b(?:male|female|men|women|gents?|ladies|lady)\s+candidates?\s+"
        r"(?:only|preferred|required|must\s+apply)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:only|exclusively)\s+(?:male|female|men|women|gents?|ladies|lady)\s+candidates?\b",
        re.IGNORECASE,
    ),
    # "for males only", "open to females only"
    re.compile(
        r"\b(?:for|open\s+(?:to|for))\s+(?:males?|females?|men|women|gents?|ladies)\s+only\b",
        re.IGNORECASE,
    ),
    # "gender: male" / "gender = female"
    re.compile(r"\bgender\s*[:=]\s*(?:male|female|m\b|f\b)", re.IGNORECASE),
    # "males preferred", "females required"
    re.compile(
        r"\b(?:males?|females?|gents?|ladies)\s+(?:preferred|required|only|need(?:ed)?)\b",
        re.IGNORECASE,
    ),
    # "ladies only", "gents only"
    re.compile(r"\b(?:ladies|gents?)\s+only\b", re.IGNORECASE),
    # "only male / female applicants will be considered"
    re.compile(
        r"\bonly\s+(?:male|female)\s+(?:applicants?|candidates?)\s+"
        r"(?:will\s+be|are)\s+(?:considered|eligible|accepted|entertained)\b",
        re.IGNORECASE,
    ),
]

_MARITAL_PATTERNS: list[re.Pattern] = [
    # "must be single / unmarried / married"
    re.compile(
        r"\b(?:must|should|need\s+to|required\s+to)\s+be\s+(?:single|unmarried|married)\b",
        re.IGNORECASE,
    ),
    # "unmarried candidates only / preferred"
    re.compile(
        r"\b(?:single|unmarried|married)\s+(?:candidates?|applicants?|persons?)\s+"
        r"(?:only|preferred|required)\b",
        re.IGNORECASE,
    ),
    # "preference for unmarried candidates" — allow up to 2 modifier words before candidates
    # e.g. "Preference for unmarried female candidates"
    re.compile(
        r"\bprefer(?:ence\s+for|red)?\s+(?:single|unmarried|married)\s+"
        r"(?:\w+\s+){0,2}(?:candidates?|applicants?)\b",
        re.IGNORECASE,
    ),
    # "marital status: single"
    re.compile(
        r"\bmarital\s+status\s*[:=]\s*(?:single|married|unmarried)\b",
        re.IGNORECASE,
    ),
    # "unmarried only"
    re.compile(r"\b(?:unmarried|never\s+married)\s+only\b", re.IGNORECASE),
]

# Known caste / community / religion names for precise matching
_COMMUNITY_NAMES = (
    r"(?:brahmin|kshatriya|vaishya|kayastha|rajput|khatri|marwari|dalit|"
    r"obc|sc\b|st\b|ews|"
    r"hindu|muslim|christian|sikh|jain|parsi|buddhist|islamic)"
)

# Reservation-category vocabulary (used in the SC/ST/OBC vs "general category" framing
# that is extremely common in Indian JDs). Matched case-insensitively, including
# slash- and comma-separated lists like "SC/ST/OBC".
_RESERVATION_CATEGORY = (
    r"(?:sc|st|obc|ews|nt|sbc|general|reserved|unreserved|open|forward|"
    r"scheduled\s+caste|scheduled\s+tribe|backward\s+class(?:es)?)"
)

_COMMUNITY_PATTERNS: list[re.Pattern] = [
    # "brahmin candidates preferred / only"
    re.compile(
        r"\b" + _COMMUNITY_NAMES + r"\s+"
        r"(?:only|preferred|required|candidates?|applicants?|community|categor(?:y|ies))\b",
        re.IGNORECASE,
    ),
    # "only hindu / muslim candidates"
    re.compile(
        r"\b(?:only|exclusively)\s+" + _COMMUNITY_NAMES + r"\s+(?:candidates?|applicants?)\b",
        re.IGNORECASE,
    ),
    # "community: brahmin", "caste: OBC", "religion: Hindu"
    re.compile(
        r"\b(?:community|caste|religion|faith)\s*[:=]\s*" + _COMMUNITY_NAMES + r"\b",
        re.IGNORECASE,
    ),
    # "from brahmin / hindu family / community / background"
    re.compile(
        r"\bfrom\s+" + _COMMUNITY_NAMES + r"\s+(?:family|community|background)\b",
        re.IGNORECASE,
    ),
    # Slash/comma-separated reservation lists: "SC/ST/OBC", "SC, ST and OBC",
    # "general/OBC". Requires at least two category tokens so plain "general manager"
    # or a lone "open" never matches.
    re.compile(
        r"\b" + _RESERVATION_CATEGORY
        + r"(?:\s*(?:[/,]|and|or)\s*" + _RESERVATION_CATEGORY + r")+\b",
        re.IGNORECASE,
    ),
    # Reservation-category preference framing: "general category candidates",
    # "preference to general category", "reserved category", "open category only".
    re.compile(
        r"\b(?:general|reserved|unreserved|open|forward|backward)\s+"
        r"categor(?:y|ies)\b",
        re.IGNORECASE,
    ),
    # "preference (will be) given to <category>" — the LogiTrack pattern.
    re.compile(
        r"\bpreference\s+(?:will\s+be\s+)?(?:given|shown)\s+to\s+"
        r"(?:\w+\s+){0,2}(?:general|forward|reserved|" + _COMMUNITY_NAMES + r")\b",
        re.IGNORECASE,
    ),
]

# Disability / medical-status exclusion (RPwD Act 2016 — see citation below).
_DISABILITY_PATTERNS: list[re.Pattern] = [
    # "able-bodied only / candidates / applicants"
    re.compile(r"\bable[\s-]?bodied\b", re.IGNORECASE),
    # "no physical disability", "without any disability", "free from disability"
    re.compile(
        r"\b(?:no|without\s+any|free\s+from|not\s+have\s+any)\s+"
        r"(?:physical\s+)?disabilit(?:y|ies)\b",
        re.IGNORECASE,
    ),
    # "physically fit candidates only" used as an eligibility filter
    re.compile(
        r"\bphysically\s+fit\s+(?:candidates?|applicants?|persons?)\s+only\b",
        re.IGNORECASE,
    ),
    # "no medical conditions / health issues" as a filter
    re.compile(
        r"\bno\s+(?:medical\s+conditions?|health\s+(?:issues?|problems?))\b",
        re.IGNORECASE,
    ),
]

# Pregnancy / maternity-status exclusion (Maternity Benefit Act 1961).
_MATERNITY_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(?:must|should)\s+not\s+be\s+pregnant\b", re.IGNORECASE),
    re.compile(r"\bnon[\s-]?pregnant\s+(?:candidates?|women|females?)\b", re.IGNORECASE),
    re.compile(
        r"\bno\s+(?:pregnancy|maternity)\s+(?:plans?|leave)\b", re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:should|must)\s+not\s+(?:be\s+)?(?:planning|plan)\s+(?:a\s+)?"
        r"(?:family|pregnancy|children|kids)\b",
        re.IGNORECASE,
    ),
]

_FRESHERS_ONLY_PATTERNS: list[re.Pattern] = [
    # "freshers only" / "only freshers"
    re.compile(r"\b(?:only|exclusively)\s+freshers?\b", re.IGNORECASE),
    re.compile(r"\bfreshers?\s+only\b", re.IGNORECASE),
    # "freshers required" / "freshers need apply" / "freshers must apply"
    re.compile(
        r"\bfreshers?\s+(?:required|need\s+apply|must\s+apply|preferred\s+only)\b",
        re.IGNORECASE,
    ),
    # "fresh graduates only"
    re.compile(r"\bfresh\s+graduates?\s+only\b", re.IGNORECASE),
    # "experienced candidates need not / should not apply"
    re.compile(
        r"\bexperienced?\s+(?:candidates?|persons?|applicants?)\s+"
        r"(?:need\s+not|should\s+not|must\s+not|do\s+not)\s+apply\b",
        re.IGNORECASE,
    ),
    # "no experienced candidates" (freshers-only implied)
    re.compile(r"\bno\s+experienced?\s+(?:candidates?|persons?|applicants?)\b", re.IGNORECASE),
    # "just out of / just passed out of college"
    re.compile(
        r"\bjust\s+(?:out\s+of|passed\s+out\s+(?:from|of))\s+college\b",
        re.IGNORECASE,
    ),
    # "newly graduated" / "newly passed out"
    re.compile(r"\bnewly\s+(?:graduated|passed\s+out)\b", re.IGNORECASE),
]

# Inclusive-language exclusion guard: "age no bar" signals inclusive intent → suppress age alert
_AGE_INCLUSIVE_RE = re.compile(r"\bage\s+no\s+bar\b", re.IGNORECASE)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _context_span(text: str, match: re.Match, context: int = 80) -> str:
    """Return matched text with ±context characters for evidence display."""
    s = max(0, match.start() - context // 2)
    e = min(len(text), match.end() + context // 2)
    span = text[s:e].strip()
    if s > 0:
        span = "…" + span
    if e < len(text):
        span = span + "…"
    return span


def _scan(
    text: str,
    patterns: list[re.Pattern],
    rule: ComplianceRule,
    guard: re.Pattern | None = None,
) -> list[ComplianceFinding]:
    """
    Scan text against all patterns; return one finding per distinct matched token.
    guard: if this pattern matches anywhere in text, suppress all findings for this rule.
    """
    if guard is not None and guard.search(text):
        return []

    findings: list[ComplianceFinding] = []
    seen: set[str] = set()
    spans: list[tuple[int, int]] = []  # matched ranges, to drop overlapping duplicates
    for pat in patterns:
        for m in pat.finditer(text):
            key = m.group(0).lower().strip()
            if key in seen:
                continue
            # Collapse near-duplicate findings: if this match overlaps a range we
            # already reported for this rule, skip it (one problem, one finding).
            if any(m.start() < e and s < m.end() for s, e in spans):
                continue
            seen.add(key)
            spans.append((m.start(), m.end()))
            findings.append(ComplianceFinding(
                rule_id=rule.rule_id,
                risk_tier=rule.risk_tier,
                result=rule.check_result,
                evidence_span=_context_span(text, m),
                citation=rule.citation,
            ))
    return findings


# ── Public API ─────────────────────────────────────────────────────────────────

def run_discriminatory_filter_checks(text: str) -> list[ComplianceFinding]:
    """Run the five high-risk discriminatory-filter detectors."""
    findings: list[ComplianceFinding] = []
    findings += _scan(text, _AGE_PATTERNS, RULE_CATALOGUE["filter.age_cap"], guard=_AGE_INCLUSIVE_RE)
    findings += _scan(text, _GENDER_PATTERNS, RULE_CATALOGUE["filter.gender_preference"])
    findings += _scan(text, _MARITAL_PATTERNS, RULE_CATALOGUE["filter.marital_status"])
    findings += _scan(text, _COMMUNITY_PATTERNS, RULE_CATALOGUE["filter.community_caste"])
    findings += _scan(text, _DISABILITY_PATTERNS, RULE_CATALOGUE["filter.disability_exclusion"])
    findings += _scan(text, _MATERNITY_PATTERNS, RULE_CATALOGUE["filter.maternity_status"])
    findings += _scan(text, _FRESHERS_ONLY_PATTERNS, RULE_CATALOGUE["filter.freshers_only"])
    return findings


def run_inclusive_language_checks(text: str) -> list[ComplianceFinding]:
    """
    Advisory inclusive-language check.
    Delegates to enrich.BIAS_PATTERNS (word-boundary regex, 29 terms).
    """
    from .enrich import BIAS_PATTERNS  # sibling module; no circular import
    rule = RULE_CATALOGUE["language.inclusive"]
    findings: list[ComplianceFinding] = []
    seen: set[str] = set()
    for term, pat in BIAS_PATTERNS:
        m = pat.search(text)
        if m and term not in seen:
            seen.add(term)
            findings.append(ComplianceFinding(
                rule_id=f"language.inclusive.{term.replace(' ', '_')}",
                risk_tier=rule.risk_tier,
                result=rule.check_result,
                evidence_span=_context_span(text, m),
                citation=rule.citation,
            ))
    return findings


def run_pay_disclosure_check(text: str) -> list[ComplianceFinding]:
    """Advisory pay-disclosure check. Returns a finding only when pay info is absent."""
    from .enrich import detect_pay  # noqa: PLC0415
    if detect_pay(text):
        return []
    rule = RULE_CATALOGUE["pay.disclosure_absent"]
    return [ComplianceFinding(
        rule_id=rule.rule_id,
        risk_tier=rule.risk_tier,
        result=rule.check_result,
        evidence_span="(no salary / compensation information found in the text)",
        citation=rule.citation,
    )]


def run_all_compliance_checks(text: str) -> list[ComplianceFinding]:
    """Full compliance scan: discriminatory filters + inclusive language + pay disclosure."""
    return (
        run_discriminatory_filter_checks(text)
        + run_inclusive_language_checks(text)
        + run_pay_disclosure_check(text)
    )


def gate_verdict(findings: Sequence[ComplianceFinding]) -> str:
    """
    Returns "pass" (no findings) or "warn" (any finding).
    No hard "fail" gate in Phase 1 pilot — override-with-justification is used instead.
    """
    return "warn" if findings else "pass"


def count_by_tier(findings: Sequence[ComplianceFinding]) -> dict[str, int]:
    """Return {"high_risk": N, "advisory": M} counts."""
    counts: dict[str, int] = {"high_risk": 0, "advisory": 0}
    for f in findings:
        if f.risk_tier in counts:
            counts[f.risk_tier] += 1
    return counts
