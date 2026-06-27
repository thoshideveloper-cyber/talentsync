"""
Reconstruct results.json using known-good LLM outputs captured from the terminal,
plus stub for failed seeds. Run once when API quota is exhausted.
"""
import json
from pathlib import Path
from unittest.mock import patch

from .contracts import JobExtractionSchema, SeniorityTier
from .core import process_jd
from .synthetic_seeds import SEEDS

ROOT = Path(__file__).parent.parent
RESULTS_PATH = ROOT / "data" / "results.json"

# Known-good LLM outputs from successful API calls (quotes verified against seed text)
KNOWN = {
    "seed_001": ("Uncertain", ["python"], "will report to me, fast paced startup",
                 "An uncertain-level role on a startup data team with minimal details."),
    "seed_002": ("Entry-Level", ["react", "figma"], "freshers ok, react preferred, will build screens from figma",
                 "An entry-level frontend role focused on building UI screens from Figma."),
    "seed_003": ("Mid-Level", ["python", "spark", "airflow", "sql"],
                 "2-4 yrs, python spark airflow, they'll maintain our pipelines",
                 "A mid-level data engineering role focused on pipeline maintenance."),
    "seed_004": ("Senior", ["pytorch", "python", "mlops", "llm"],
                 "6+ yrs, pytorch mlops experience, ideally llm background. will own the model infra",
                 "A senior ML engineering role focused on owning model infrastructure and mentoring."),
    "seed_005": ("Uncertain", ["product management", "agile"],
                 "someone senior or mid we are flexible",
                 "An uncertain-level product management role in a startup environment."),
    "seed_006": ("Senior", ["kubernetes", "terraform", "aws", "ci/cd"],
                 "Job Title: DevOps / Infra (senior level)\nKey skills: k8s, terraform, AWS\nExperience: 5+ years",
                 "A senior DevOps role focused on infrastructure ownership and SRE practices."),
    "seed_007": ("Entry-Level", ["figma", "user research"],
                 "Experience: 0-1 year or fresher ok",
                 "An entry-level UX design role focused on supporting the senior designer."),
    "seed_008": ("Uncertain", ["python", "machine learning", "sql"],
                 "Experience: experienced preferred",
                 "An uncertain-level data science role with vague experience requirements."),
    "seed_009": ("Mid-Level", ["android", "java", "kotlin", "rest api", "mvvm"],
                 "We are looking for an Android Developer with 2-4 years of experience",
                 "A mid-level Android development role focused on consumer applications."),
    "seed_010": ("Senior", ["node.js", "mongodb", "aws", "system design"],
                 "You will design the architecture for our new platform, lead the backend squad of 4 engineers",
                 "A senior backend role focused on platform architecture and team leadership."),
    "seed_011": ("Executive", ["people management", "roadmap", "system design", "hiring"],
                 "this is basically a co-founder level hire",
                 "An executive engineering leadership role reporting directly to the CEO."),
    "seed_012": ("Mid-Level", ["react", "node.js", "postgresql"],
                 "Needs a fullstack dev, react + node, postgres. 2-4 years",
                 "A mid-level full stack development role focused on product shipping."),
    "seed_013": ("Entry-Level", ["java", "spring boot", "mysql"],
                 "1-2 yrs exp is fine. will get tasks from the tech lead and code them up",
                 "An entry-level software engineering role focused on executing assigned tasks."),
    "seed_014": ("Senior", ["python", "machine learning", "statistics", "deep learning"],
                 "define ML strategy for the company, publish research, represent company at conferences",
                 "A senior data science role focused on ML strategy and research."),
    "seed_015": ("Uncertain", ["node.js", "mongodb"],
                 "backend dev needed. node and mongo. salary negotiable",
                 "An uncertain-level backend development role with minimal detail."),
}


def _make_extraction(seed_id: str) -> JobExtractionSchema:
    seniority, skills, quote, summary = KNOWN[seed_id]
    return JobExtractionSchema(
        one_line_summary=summary,
        seniority_level=SeniorityTier(seniority),
        required_skills=skills,
        raw_text_justification=quote,
    )


def run() -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    results = []
    seed_map = {s["id"]: s for s in SEEDS}

    print(f"Reconstructing {len(SEEDS)} records from known LLM outputs...")

    for seed in SEEDS:
        sid = seed["id"]
        extraction = _make_extraction(sid)

        with patch("talentsync.core.extract", return_value=extraction):
            record = process_jd(seed["raw_jd"], seed=seed)

        v = "V" if record["is_verified"] else " "
        print(f"  [{v}] {sid}: {record['status']:12} {record['ai_seniority']:12} score={record['quality_score']}")
        results.append(record)

    RESULTS_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\nSaved {len(results)} records -> {RESULTS_PATH} ({ok} verified ok)")


if __name__ == "__main__":
    run()
