"""
Deterministic enrichment — zero LLM calls.
R5: bias = wordlist ∩ text; pay = regex.
"""
import re
from typing import List

# ── Bias wordlist ────────────────────────────────────────────────────────────
# Naive baseline; label as "flagged for review", not "bias detected" (spec §3).
_BIAS_TERMS = [
    "rockstar", "rock star", "ninja", "wizard", "guru", "hero",
    "young team", "young culture", "young startup", "young company",
    "culture fit", "cultural fit", "hustler", "hustle", "go-getter",
    "self-starter", "fast-paced", "fast paced", "startup culture",
    "aggressive", "sharp", "killer instinct", "tribe", "band of brothers",
    "digital native", "recent graduate", "recent grad",
    "energetic", "dynamic personality",
]

# ── Pay regex ────────────────────────────────────────────────────────────────
# Matches ₹/LPA/lakh + numeric range patterns common in India JDs.
_PAY_RE = re.compile(
    r"(?:"
    r"\d+[\s\-–—to]+\d+\s*(?:lpa|lakh|l\b|lac)"
    r"|₹\s*\d+"
    r"|\d+\s*(?:lpa|lakh|l\b|lac)"
    r"|salary\s*[:=]\s*\d+"
    r"|budget\s*[:=]?\s*(?:₹|\d)"
    r"|esop"
    r")",
    re.IGNORECASE,
)

# ── Skill canonical synonym map ──────────────────────────────────────────────
# Maps common variants to the canonical form used for word-boundary matching.
SKILL_SYNONYMS: dict[str, str] = {
    "reactjs": "react",
    "react.js": "react",
    "react js": "react",
    "node js": "node.js",
    "nodejs": "node.js",
    "vuejs": "vue",
    "vue.js": "vue",
    "angularjs": "angular",
    "python3": "python",
    "python 3": "python",
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "mongo": "mongodb",
    "k8s": "kubernetes",
    "scikit learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "tensorflow": "tensorflow",
    "tf": "tensorflow",
    "js": "javascript",
    "ts": "typescript",
    "ci/cd": "ci/cd",
    "cicd": "ci/cd",
    "rest api": "rest api",
    "rest apis": "rest api",
    "restful": "rest api",
    "aws": "aws",
    "amazon web services": "aws",
    "gcp": "gcp",
    "google cloud": "gcp",
    "azure": "azure",
    "microsoft azure": "azure",
    "ml": "machine learning",
    "ai/ml": "machine learning",
    "dl": "deep learning",
    "llm": "llm",
    "large language model": "llm",
    "mlops": "mlops",
    "spring": "spring boot",
    "springboot": "spring boot",
    "spring boot": "spring boot",
    "flutter": "flutter",
    "mvvm": "mvvm",
    "figma": "figma",
    "user research": "user research",
    "people management": "people management",
    "system design": "system design",
    "roadmap": "roadmap",
    "hiring": "hiring",
    "agile": "agile",
    "product": "product management",
    "android": "android",
    "java": "java",
    "kotlin": "kotlin",
    "mysql": "mysql",
    "sql": "sql",
    "spark": "spark",
    "airflow": "airflow",
    "terraform": "terraform",
    "docker": "docker",
    "kafka": "kafka",
    "pytorch": "pytorch",
    "statistics": "statistics",
    "deep learning": "deep learning",
    "machine learning": "machine learning",
    "html": "html",
    "css": "css",
}

# ── Quality score ─────────────────────────────────────────────────────────────

def quality_score(
    skills: List[str],
    ai_seniority: str,
    is_verified: bool,
    pay_range_present: bool,
    bias_flags: List[str],
) -> tuple[int, List[str]]:
    """Returns (score 0-100, breakdown list)."""
    score = 0
    breakdown: List[str] = []

    n_skills = len(skills)
    if n_skills >= 3:
        score += 20
        breakdown.append("+20 skills≥3")
    if n_skills >= 6:
        score += 10
        breakdown.append("+10 skills≥6")

    if ai_seniority != "Uncertain":
        score += 25
        breakdown.append("+25 level")

    if is_verified:
        score += 20
        breakdown.append("+20 verified")

    if pay_range_present:
        score += 15
        breakdown.append("+15 pay range")

    if not bias_flags:
        score += 10
        breakdown.append("+10 no-bias")

    return score, breakdown


# ── Public helpers ─────────────────────────────────────────────────────────────

def detect_bias(text: str) -> List[str]:
    text_lower = text.lower()
    return [term for term in _BIAS_TERMS if term in text_lower]


def detect_pay(text: str) -> bool:
    return bool(_PAY_RE.search(text))


def canonical_skill(raw: str) -> str:
    """Normalise a skill string to its canonical form."""
    s = raw.strip().lower().rstrip(".,;:!?")
    return SKILL_SYNONYMS.get(s, s)
