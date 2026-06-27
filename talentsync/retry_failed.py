"""
Targeted re-run: retry seeds with status != 'ok' using the second API key.
Uses longer delays to avoid rate limits.
"""
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
RESULTS_PATH = ROOT / "data" / "results.json"

# Override with second key (set GOOGLE_API_KEY_2 in your .env)
SECOND_KEY = os.environ.get("GOOGLE_API_KEY_2", "")
if SECOND_KEY:
    os.environ["GOOGLE_API_KEY"] = SECOND_KEY

from .core import process_jd
from .synthetic_seeds import SEEDS


def retry_failed(delay: int = 15) -> None:
    if not RESULTS_PATH.exists():
        print("No results.json found. Run pipeline.py first.")
        return

    current = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    current_map = {r["id"]: r for r in current}
    seed_map = {s["id"]: s for s in SEEDS}

    failed = [r for r in current if r.get("status") != "ok"]
    print(f"Retrying {len(failed)} of {len(current)} seeds with second API key...\n")

    for rec in failed:
        sid = rec["id"]
        seed = seed_map.get(sid)
        if seed is None:
            continue

        print(f"  {sid} retrying...", end=" ", flush=True)
        new_rec = process_jd(seed["raw_jd"], seed=seed)
        print(f"-> {new_rec['ai_seniority']}  verified={new_rec['is_verified']}  score={new_rec['quality_score']}")
        current_map[sid] = new_rec

        time.sleep(delay)

    # Preserve original order
    results = [current_map.get(s["id"], current_map[s["id"]]) for s in SEEDS if s["id"] in current_map]
    RESULTS_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(results)} records -> {RESULTS_PATH}")


if __name__ == "__main__":
    retry_failed()
