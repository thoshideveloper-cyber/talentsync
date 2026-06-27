"""
Generates synthetic "raw manager JD" style job descriptions using the LLM.

Run once to produce data/synthetic_jds.csv — use this as the eval harness.
The LLM generates both the messy JD AND the ground truth labels in one call.

Usage:
    python -m talentsync.generate_synthetic_jds

Output: data/synthetic_jds.csv with columns:
    id, role, raw_jd, actual_seniority, skills_present,
    has_bias, bias_words, salary_mentioned, notes
"""

import asyncio
import csv
import json
import os
import random
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ── config ──────────────────────────────────────────────────────────────────

MODEL = "gemini-2.5-flash-lite-preview-06-17"
OUTPUT_PATH = Path("data/synthetic_jds.csv")

ROLES = [
    "Frontend Developer",
    "Backend Developer",
    "Full Stack Developer",
    "Data Engineer",
    "Data Analyst",
    "Data Scientist",
    "ML Engineer",
    "DevOps Engineer",
    "Mobile Developer (Android)",
    "Mobile Developer (iOS)",
    "Product Manager",
    "UX Designer",
    "QA Engineer",
    "Cloud Engineer",
    "Engineering Manager",
]

SENIORITY_LEVELS = [
    "Entry-Level",
    "Entry-Level",        # duplicate weight — more freshers in real world
    "Mid-Level",
    "Mid-Level",
    "Senior",
    "Executive",
    "Uncertain",          # vague / no signals
    "Mislabeled",         # stated level contradicts text signals
]

MANAGER_ARCHETYPES = [
    "a startup founder who dashed this off in 2 minutes",
    "a busy engineering manager who wrote this between meetings",
    "a non-technical HR generalist forwarding what the manager said on a call",
    "a technical lead who only cares about skills, forgot everything else",
    "a corporate middle manager drowning in buzzwords",
]

BIAS_WORDS = [
    "rockstar", "ninja", "aggressive", "young and dynamic", "digital native",
    "hustle", "killer instinct", "dominate", "crush it", "beast mode",
]

SYSTEM_PROMPT = """You generate synthetic job description drafts that look like
what a hiring manager actually sends to HR — messy, informal, incomplete,
and inconsistent. Not polished HR language. Real manager language.

You also generate the ground truth labels so this data can be used to
evaluate a JD extraction pipeline.

Always respond with valid JSON matching the schema exactly."""

USER_TEMPLATE = """Generate a synthetic raw manager JD draft and its ground truth labels.

Parameters:
- Role: {role}
- Intended seniority: {seniority}
- Manager archetype: {archetype}
- Include bias words: {include_bias}
- Mention salary: {mention_salary}

Rules for the raw_jd:
- Sound like a quick Slack message or email to HR, not a job posting
- Under 200 words
- If seniority is "Uncertain": give NO clear signals — no years, no responsibility scope
- If seniority is "Mislabeled": put a contradictory title (e.g. say "senior" but
  describe tasks assigned by others, 0-2 yrs exp) OR say "junior" but describe
  strategy/leadership/10+ yrs
- If include_bias is true: naturally slip in 1-2 of these words: {bias_words}
- If mention_salary is false: never mention salary or compensation
- Never explicitly state the seniority tier (no "senior engineer", "junior dev")
  UNLESS it's a mislabeled case (where you intentionally put the wrong label)

Respond with this exact JSON schema:
{{
  "raw_jd": "the messy draft text",
  "actual_seniority": "Entry-Level | Mid-Level | Senior | Executive | Uncertain",
  "skills_present": ["skill1", "skill2"],
  "has_bias": true | false,
  "bias_words": ["word1"],
  "salary_mentioned": true | false,
  "notes": "one sentence explaining the key signals or gotcha in this JD"
}}"""


async def generate_one(
    client: genai.Client,
    role: str,
    seniority: str,
    idx: int,
) -> dict | None:
    archetype = random.choice(MANAGER_ARCHETYPES)
    include_bias = random.random() < 0.4
    mention_salary = random.random() < 0.25

    prompt = USER_TEMPLATE.format(
        role=role,
        seniority=seniority,
        archetype=archetype,
        include_bias=include_bias,
        mention_salary=mention_salary,
        bias_words=", ".join(random.sample(BIAS_WORDS, 3)),
    )

    try:
        response = await client.aio.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.9,        # high temp for variety
                response_mime_type="application/json",
            ),
        )
        data = json.loads(response.text)
        data["id"] = f"syn_{idx:03d}"
        data["role"] = role
        data["intended_seniority"] = seniority
        return data
    except Exception as e:
        print(f"  [skip] {role} / {seniority}: {e}")
        return None


async def generate_batch(n: int = 60) -> list[dict]:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    # Build the generation plan: cycle through roles × seniority combos
    plan = []
    for i in range(n):
        role = ROLES[i % len(ROLES)]
        seniority = SENIORITY_LEVELS[i % len(SENIORITY_LEVELS)]
        plan.append((role, seniority, i + 1))

    # Run with concurrency=5 to stay inside free-tier RPM
    semaphore = asyncio.Semaphore(5)

    async def bounded(role, seniority, idx):
        async with semaphore:
            result = await generate_one(client, role, seniority, idx)
            await asyncio.sleep(0.5)    # gentle pacing
            return result

    tasks = [bounded(role, sen, idx) for role, sen, idx in plan]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


def save_csv(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id", "role", "intended_seniority", "actual_seniority",
        "raw_jd", "skills_present", "has_bias", "bias_words",
        "salary_mentioned", "notes",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            r["skills_present"] = "|".join(r.get("skills_present", []))
            r["bias_words"] = "|".join(r.get("bias_words", []))
            writer.writerow(r)
    print(f"\nSaved {len(records)} records → {path}")


def main():
    records = asyncio.run(generate_batch(n=60))

    # Merge with hand-crafted seeds
    from talentsync.synthetic_seeds import SEEDS
    seed_records = []
    for s in SEEDS:
        seed_records.append({
            "id": s["id"],
            "role": s["role"],
            "intended_seniority": s["actual_seniority"],
            "actual_seniority": s["actual_seniority"],
            "raw_jd": s["raw_jd"],
            "skills_present": "|".join(s["skills_present"]),
            "has_bias": s["has_bias"],
            "bias_words": "",
            "salary_mentioned": s["salary_mentioned"],
            "notes": "",
        })

    all_records = seed_records + records
    save_csv(all_records, OUTPUT_PATH)
    print(f"Total: {len(all_records)} JDs ({len(SEEDS)} seeds + {len(records)} generated)")
    print("\nSample (first 3 generated):")
    for r in records[:3]:
        print(f"\n[{r['id']}] {r['role']} | actual: {r['actual_seniority']}")
        print(f"  JD: {r['raw_jd'][:120]}...")
        print(f"  Skills: {r['skills_present']}")
        print(f"  Notes: {r['notes']}")


if __name__ == "__main__":
    main()
