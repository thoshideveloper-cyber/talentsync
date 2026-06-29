"""
core.process_jd — the SINGLE shared path used by both the batch pipeline and the API.
Implements the §7 post-processing pipeline in order.
"""
import hashlib
import re
from typing import Any

from .contracts import SeniorityTier
from .llm import extract
from .enrich import detect_bias, detect_pay, quality_score, canonical_skill
from .verify import verify_quote, filter_skills

ORDINAL: dict[str, int] = {
    "Internship": 0,
    "Entry-Level": 1,
    "Mid-Level": 2,
    "Senior": 3,
    "Executive": 4,
}


def _audit_mismatch(native: str | None, ai: str) -> bool:
    """Conservative ordinal rule (§5.5): flag only a gap of ≥2 tiers."""
    if native is None or ai == "Uncertain":
        return False
    n = ORDINAL.get(native)
    a = ORDINAL.get(ai)
    if n is None or a is None:
        return False
    return abs(a - n) >= 2


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _native_label_from_seed(seed: dict) -> str | None:
    """
    For synthetic seeds there is no LinkedIn experienceLevel dropdown.
    We derive native_label from the title/text using the mismatch ground truth.
    Seeds with mismatch=True have a stated title level that contradicts the text.
    We store the title-level as native_label so audit_mismatch can be computed.
    """
    role = seed.get("role", "")
    raw = seed.get("raw_jd", "")
    combined = (role + " " + raw).lower()

    # Look for explicit level words in the combined text
    level_map = [
        (["executive", "vp ", "vice president", "cto", "ceo", "coo", "head of engineering",
          "head of"], "Executive"),
        (["principal ", "director"], "Senior"),
        (["senior ", "sr."], "Senior"),
        (["junior ", "jr.", "associate ", "fresher", "entry"], "Entry-Level"),
        (["intern"], "Internship"),
        (["mid ", "mid-senior", "3-5", "3 to 5"], "Mid-Level"),
    ]
    for keywords, level in level_map:
        for kw in keywords:
            if kw in combined:
                return level
    return None


# Word-boundary title-level patterns, senior-first so the highest stated level wins
# (e.g. "Associate Director" -> Executive). Used on the PASTE path, which has no seed/
# dropdown label — without this, audit_mismatch silently never fires on the main
# workflow (paste runs with seed={} -> native_label=None -> mismatch always False).
_TITLE_LEVEL_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(head\s+of|vp|vice\s+president|director|chief|c(?:to|eo|oo|fo|xo)|executive|president)\b", re.IGNORECASE), "Executive"),
    (re.compile(r"\b(senior|sr\.?|lead|principal|staff)\b", re.IGNORECASE), "Senior"),
    (re.compile(r"\b(mid[\s-]?level|mid[\s-]?senior)\b", re.IGNORECASE), "Mid-Level"),
    (re.compile(r"\b(fresher|entry[\s-]?level|graduate\s+trainee|trainee|junior|jr\.?|associate)\b", re.IGNORECASE), "Entry-Level"),
    (re.compile(r"\b(intern|internship)\b", re.IGNORECASE), "Internship"),
]


_TITLE_PREFIX_RE = re.compile(
    r"^(?:job\s+title|position|role|designation|vacancy|opening|title)\s*[:\-–]\s*",
    re.IGNORECASE,
)
_NOISE_SUFFIXES_RE = re.compile(
    r"\s*[\|·•]\s*.{0,60}$",  # strip "| Company Name" or "• Location" from title line
)

def role_title_from_text(text: str) -> str:
    """Extract a clean job title from the first meaningful line of a pasted JD.
    Falls back to 'Pasted JD' if nothing sensible is found."""
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate or len(candidate) < 3:
            continue
        # Skip lines that are obviously headers/labels, not a title
        if re.match(r"^(company|location|department|about|overview|summary|responsibilities)\s*[:\-]", candidate, re.IGNORECASE):
            continue
        # Strip "Job Title: " prefixes
        candidate = _TITLE_PREFIX_RE.sub("", candidate)
        # Strip trailing " | Company Name" or " • Location" suffixes
        candidate = _NOISE_SUFFIXES_RE.sub("", candidate).strip()
        # Accept if it looks like a title: reasonable length, not a sentence
        if 3 < len(candidate) <= 120 and candidate.count(" ") <= 10:
            return candidate[:100]
    return "Pasted JD"


def _native_label_from_title(text: str) -> str | None:
    """Derive the stated seniority from the JD title (first non-empty line).
    Pasted JDs carry no native dropdown label, so this is what lets audit_mismatch
    fire on the real user workflow. Conservative by design: the ≥2-tier gap rule in
    _audit_mismatch still guards against minor title-parsing imprecision."""
    title = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    if not title:
        return None
    for pat, level in _TITLE_LEVEL_PATTERNS:
        if pat.search(title):
            return level
    return None


def process_jd(text: str, seed: dict | None = None) -> dict[str, Any]:
    """
    Full pipeline: extract → enrich → verify → score.
    Returns a dict matching the JobRecord schema.
    """
    seed = seed or {}
    record_id = seed.get("id", "paste_" + _sha256(text)[:8])
    role = seed.get("role", "Pasted JD")
    input_format = seed.get("input_format", "paste")
    content_hash = _sha256(text)

    # Seed-derived label wins (synthetic pipeline); fall back to the JD title so the
    # paste path also gets a stated level and audit_mismatch can actually fire.
    native_label = _native_label_from_seed(seed) or _native_label_from_title(text)

    # ── Step 1: LLM extraction (with retry ≤2, per R8) ──────────────────────
    extraction = extract(text)

    if extraction is None:
        return {
            "id": record_id,
            "role": role,
            "input_format": input_format,
            "raw_jd": text,
            "one_line_summary": "",
            "ai_seniority": "Uncertain",
            "required_skills": [],
            "raw_text_justification": "",
            "native_label": native_label,
            "is_verified": False,
            "audit_mismatch": False,
            "bias_flags": detect_bias(text),
            "pay_range_present": detect_pay(text),
            "quality_score": 0,
            "score_breakdown": [],
            "content_hash": content_hash,
            "status": "failed",
        }

    # ── Step 2: Skills — clean → R3 word-boundary filter → cap 7 ────────────
    raw_skills = [s.strip().lower().rstrip(".,;:!?") for s in extraction.required_skills if s.strip()]
    skills = filter_skills(raw_skills, text)

    # ── Step 3: Summary — first sentence (split on ". " to protect "Node.js") ──
    summary_raw = extraction.one_line_summary.strip()
    parts = summary_raw.split(". ")
    summary = (parts[0].strip() + ".") if parts[0].strip() else summary_raw

    # ── Step 4: R2 normalized verification gate ──────────────────────────────
    quote = extraction.raw_text_justification.strip()
    is_verified = verify_quote(quote, text)

    ai_seniority = extraction.seniority_level.value
    status = "ok"

    if not is_verified:
        ai_seniority = "Uncertain"
        status = "unverified"

    # ── Step 5: Deterministic enrichment (R5) ────────────────────────────────
    bias_flags = detect_bias(text)
    pay_range_present = detect_pay(text)

    # ── Step 6: audit_mismatch (§5.5) — native_label computed above ──────────
    mismatch = _audit_mismatch(native_label, ai_seniority)

    # ── Step 7: quality score + content_hash ─────────────────────────────────
    q_score, q_breakdown = quality_score(
        skills, ai_seniority, is_verified, pay_range_present, bias_flags
    )

    return {
        "id": record_id,
        "role": role,
        "input_format": input_format,
        "raw_jd": text,
        "one_line_summary": summary,
        "ai_seniority": ai_seniority,
        "required_skills": skills,
        "raw_text_justification": quote,
        "native_label": native_label,
        "is_verified": is_verified,
        "audit_mismatch": mismatch,
        "bias_flags": bias_flags,
        "pay_range_present": pay_range_present,
        "quality_score": q_score,
        "score_breakdown": q_breakdown,
        "content_hash": content_hash,
        "status": status,
    }
