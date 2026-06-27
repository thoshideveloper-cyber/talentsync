from enum import Enum
from typing import List
from pydantic import BaseModel


class SeniorityTier(str, Enum):
    INTERNSHIP = "Internship"
    ENTRY = "Entry-Level"
    MID = "Mid-Level"
    SENIOR = "Senior"
    EXECUTIVE = "Executive"
    UNCERTAIN = "Uncertain"


class JobExtractionSchema(BaseModel):
    """Shape-only schema. All cleaning/truncation happens in core.process_jd."""
    one_line_summary: str
    seniority_level: SeniorityTier
    required_skills: List[str]
    raw_text_justification: str


class JobRecord(BaseModel):
    id: str
    role: str
    input_format: str
    raw_jd: str
    one_line_summary: str
    ai_seniority: str
    required_skills: List[str]
    raw_text_justification: str
    native_label: str | None
    is_verified: bool
    audit_mismatch: bool
    bias_flags: List[str]
    pay_range_present: bool
    quality_score: int
    score_breakdown: List[str]
    content_hash: str
    status: str
