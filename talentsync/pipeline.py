"""
Batch pipeline: run core.process_jd over all 15 synthetic seeds → data/results.json.
SHA-256 dedup: re-running costs 0 calls for already-processed seeds.
"""
import json
import time
import os
from pathlib import Path

from .core import process_jd
from .synthetic_seeds import SEEDS

ROOT = Path(__file__).parent.parent
RESULTS_PATH = ROOT / "data" / "results.json"
DELAY_SECS = int(os.environ.get("PIPELINE_DELAY", "8"))


def load_existing() -> dict[str, dict]:
    """Load already-processed records keyed by content_hash for dedup."""
    if RESULTS_PATH.exists():
        try:
            records = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
            return {r["content_hash"]: r for r in records}
        except Exception:
            pass
    return {}


def run(force: bool = False) -> list[dict]:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing = {} if force else load_existing()
    results: list[dict] = []

    print(f"Processing {len(SEEDS)} synthetic seeds -> {RESULTS_PATH}")
    print(f"Stub mode: {os.environ.get('TALENTSYNC_STUB', 'off')}\n")

    for seed in SEEDS:
        text = seed["raw_jd"]

        import hashlib
        h = hashlib.sha256(text.encode()).hexdigest()

        if h in existing:
            print(f"  {seed['id']} CACHED (skip LLM)")
            results.append(existing[h])
            continue

        print(f"  {seed['id']} processing...", end=" ", flush=True)
        record = process_jd(text, seed=seed)
        print(f"-> {record['ai_seniority']}  verified={record['is_verified']}  score={record['quality_score']}")
        results.append(record)

        if os.environ.get("TALENTSYNC_STUB", "").lower() not in ("1", "true", "yes"):
            time.sleep(DELAY_SECS)

    RESULTS_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(results)} records -> {RESULTS_PATH}")
    return results


if __name__ == "__main__":
    import sys
    run(force="--force" in sys.argv)
