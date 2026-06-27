"""
Trust layer — R2 + R3.
"""
import re
from typing import List

from .enrich import canonical_skill


def _norm(s: str) -> str:
    """R2: collapse all whitespace, casefold."""
    return " ".join(s.split()).casefold()


def verify_quote(quote: str, description: str) -> bool:
    """R2 normalized verification gate."""
    q = quote.strip()
    if len(q) < 25:
        return False
    return _norm(q) in _norm(description)


def filter_skills(skills: List[str], description: str) -> List[str]:
    """R3: word-boundary filter + canonical map + cap at 7."""
    desc_lower = description.lower()
    result: List[str] = []
    seen: set[str] = set()

    for raw in skills:
        canon = canonical_skill(raw)
        if canon in seen:
            continue

        # Build search terms: try both the raw (normalised) and the canonical
        candidates = {canon, raw.strip().lower().rstrip(".,;:!?")}
        found = False
        for term in candidates:
            if not term:
                continue
            # Escape regex special chars
            escaped = re.escape(term)
            # Word-boundary match (\b works for alphanumeric; for "/" we use lookaround)
            pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
            if re.search(pattern, desc_lower, re.IGNORECASE):
                found = True
                break

        if found:
            seen.add(canon)
            result.append(canon)

    return result[:7]
