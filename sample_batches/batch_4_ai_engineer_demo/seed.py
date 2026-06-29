"""
Seed batch_4_ai_engineer_demo into the running backend.

Usage:
    python sample_batches/batch_4_ai_engineer_demo/seed.py

Requires the backend to be running on http://127.0.0.1:8000.
"""
import sys
import pathlib
import requests

BASE = "http://127.0.0.1:8000"
EMAIL = "admin@talentsync.local"
PASSWORD = "changeme123"

BATCH_DIR = pathlib.Path(__file__).parent
JD_FILES = [
    "ai_engineer_genai_platform.txt",
    "ml_engineer_llm_finetuning.txt",
    "ai_infra_engineer_model_serving.txt",
]


def login() -> str:
    r = requests.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    token = r.json()["access_token"]
    print(f"[auth] logged in as {EMAIL}")
    return token


def upload(token: str, text: str, filename: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{BASE}/api/extract", json={"text": text}, headers=headers, timeout=120)
    if r.status_code != 200:
        print(f"  [ERROR] {filename}: HTTP {r.status_code} — {r.text[:200]}")
        return {}
    return r.json()


def summarise(record: dict, filename: str) -> None:
    role = record.get("role", "?")
    status = record.get("status", "?")
    flags: list = record.get("bias_flags", [])
    score = record.get("quality_score", "?")
    pay = record.get("pay_range_present", False)
    print(f"\n  Role      : {role}")
    print(f"  File      : {filename}")
    print(f"  Status    : {status}   Quality: {score}/100   Pay disclosed: {pay}")
    if flags:
        print(f"  Flags     : {len(flags)} violation(s)")
        for f in flags:
            rule = f if isinstance(f, str) else f.get("rule_id", "?")
            print(f"    • {rule}")
    else:
        print("  Flags     : none")


def main() -> None:
    token = login()
    results = []

    for fname in JD_FILES:
        path = BATCH_DIR / fname
        text = path.read_text(encoding="utf-8")
        print(f"\n[upload] {fname} …")
        record = upload(token, text, fname)
        if record:
            summarise(record, fname)
            results.append(record)

    print(f"\n{'-' * 60}")
    print(f"Seeded {len(results)} / {len(JD_FILES)} JDs into the database.")
    if len(results) < len(JD_FILES):
        sys.exit(1)


if __name__ == "__main__":
    main()
