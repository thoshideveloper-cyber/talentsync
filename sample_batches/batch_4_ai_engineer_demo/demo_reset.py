"""
demo_reset.py — wipe the 3 AI Engineer demo JDs from the DB so they can be
uploaded fresh during a live demo. Matches by title prefix "AI" / "ML" in the
role field (all demo records use role="Pasted JD", so we match by content hash).

Usage:
    python sample_batches/batch_4_ai_engineer_demo/demo_reset.py
"""
import pathlib
import hashlib
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


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def login() -> str:
    r = requests.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    return r.json()["access_token"]


def main() -> None:
    token = login()
    headers = {"Authorization": f"Bearer {token}"}

    target_hashes = {sha256((BATCH_DIR / f).read_text(encoding="utf-8")) for f in JD_FILES}

    records = requests.get(f"{BASE}/api/records", headers=headers).json()
    to_delete = [r for r in records if r.get("content_hash") in target_hashes]

    if not to_delete:
        print("No demo records found in the database — already clean.")
        return

    deleted = 0
    for rec in to_delete:
        r = requests.delete(f"{BASE}/api/records/{rec['id']}", headers=headers)
        if r.status_code in (200, 204, 404):
            print(f"  deleted: {rec['id']} ({rec.get('one_line_summary','')[:60]})")
            deleted += 1
        else:
            print(f"  [ERROR] {rec['id']}: HTTP {r.status_code}")

    print(f"\nRemoved {deleted} / {len(to_delete)} demo records.")
    print("You can now upload the JDs fresh via the UI or re-run seed.py.")


if __name__ == "__main__":
    main()
