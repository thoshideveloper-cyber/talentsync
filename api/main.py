"""
FastAPI backend — §8.1 endpoints.
Dashboard load = 0 LLM calls (serves cached results.json).
Only POST /api/extract makes a live LLM call.
"""
import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

# Allow running from project root: python -m api.main
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from talentsync.core import process_jd
from api.docx_builder import build_corrected_jd

RESULTS_PATH = ROOT / "data" / "results.json"

app = FastAPI(title="TalentSync API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── In-memory store (loaded once at startup) ──────────────────────────────────

_records: list[dict[str, Any]] = []


def _load_results() -> list[dict[str, Any]]:
    if RESULTS_PATH.exists():
        try:
            return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_results(records: list[dict]) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


@app.on_event("startup")
async def startup():
    global _records
    _records = _load_results()


# ── Request/Response models ────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    text: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/records")
def get_records() -> list[dict]:
    return _records


@app.get("/api/records/{record_id}")
def get_record(record_id: str) -> dict:
    for rec in _records:
        if rec["id"] == record_id:
            return rec
    raise HTTPException(404, f"Record '{record_id}' not found")


@app.post("/api/extract")
def extract_jd(req: ExtractRequest) -> dict:
    """Live LLM call — the only endpoint that calls the model."""
    if not req.text.strip():
        raise HTTPException(400, "text must not be empty")

    # Dedup check
    import hashlib
    h = hashlib.sha256(req.text.encode()).hexdigest()
    for rec in _records:
        if rec.get("content_hash") == h:
            return rec

    record = process_jd(req.text)

    # Persist to results.json (append to in-memory list)
    _records.append(record)
    _save_results(_records)

    return record


@app.post("/api/extract/file")
async def extract_from_file(file: UploadFile = File(...)) -> dict:
    """Parse a .txt / .docx / .pdf file and run it through the extraction pipeline."""
    filename = file.filename or "unknown"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    raw = await file.read()

    if ext in ("txt", "md"):
        text = raw.decode("utf-8", errors="replace")
    elif ext == "docx":
        try:
            from docx import Document  # python-docx
            doc = Document(io.BytesIO(raw))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception as exc:
            raise HTTPException(400, f"Could not parse .docx: {exc}") from exc
    elif ext == "pdf":
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except ImportError as exc:
            raise HTTPException(
                400, "PDF support requires pdfplumber — run: pip install pdfplumber"
            ) from exc
        except Exception as exc:
            raise HTTPException(400, f"Could not parse .pdf: {exc}") from exc
    else:
        raise HTTPException(
            400,
            f"Unsupported file type '.{ext}'. Upload a .txt, .docx, or .pdf file.",
        )

    text = text.strip()
    if len(text) < 50:
        raise HTTPException(
            400, f"'{filename}' is too short to be a valid JD (< 50 characters after parsing)."
        )

    return extract_jd(ExtractRequest(text=text))


@app.get("/api/kpis")
def get_kpis() -> dict:
    """Returns counts + fractions (not bare %) for the KPI strip."""
    n = len(_records)
    if n == 0:
        return {
            "total": 0,
            "flagged_for_review": "0 of 0",
            "leveling_flags": "0 of 0",
            "with_pay_range": "0 of 0",
            "verified": "0 of 0",
            "hallucination_note": "pre-filter rate unavailable (post-filter: 0 of 0 skills)",
        }

    flagged = sum(1 for r in _records if r.get("bias_flags"))
    level_flags = sum(1 for r in _records if r.get("audit_mismatch"))
    with_pay = sum(1 for r in _records if r.get("pay_range_present"))
    verified = sum(1 for r in _records if r.get("is_verified"))
    total_skills = sum(len(r.get("required_skills", [])) for r in _records)

    return {
        "total": n,
        "flagged_for_review": f"{flagged} of {n}",
        "leveling_flags": f"{level_flags} of {n}",
        "with_pay_range": f"{with_pay} of {n}",
        "verified": f"{verified} of {n}",
        "hallucination_note": (
            f"pre-filter rate: see eval.py output; "
            f"post-filter: 0 of {total_skills} skills (by construction)"
        ),
    }


@app.get("/api/skills")
def get_skills() -> list[dict]:
    """Returns skill → frequency for the 'skills mentioned' view."""
    freq: dict[str, int] = {}
    for rec in _records:
        for skill in rec.get("required_skills", []):
            freq[skill] = freq.get(skill, 0) + 1
    return sorted(
        [{"skill": k, "count": v} for k, v in freq.items()],
        key=lambda x: -x["count"],
    )


@app.get("/api/records/{record_id}/docx")
def download_docx(record_id: str) -> Response:
    rec = None
    for r in _records:
        if r["id"] == record_id:
            rec = r
            break
    if rec is None:
        raise HTTPException(404, f"Record '{record_id}' not found")

    content = build_corrected_jd(rec)
    filename = f"{record_id}_corrected.docx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/extract/docx")
def download_paste_docx(req: ExtractRequest) -> Response:
    """Download .docx for a pasted JD (same as /api/extract but returns file)."""
    record = extract_jd(req)
    content = build_corrected_jd(record)
    filename = "corrected_jd.docx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/export.csv")
def export_csv() -> StreamingResponse:
    if not _records:
        raise HTTPException(404, "No records to export")

    output = io.StringIO()
    fieldnames = [
        "id", "role", "input_format", "ai_seniority", "native_label",
        "is_verified", "audit_mismatch", "quality_score",
        "pay_range_present", "required_skills", "bias_flags",
        "one_line_summary", "raw_text_justification", "status",
    ]
    writer = csv.DictWriter(
        output, fieldnames=fieldnames, extrasaction="ignore",
        quoting=csv.QUOTE_ALL, lineterminator="\n",
    )
    writer.writeheader()
    for rec in _records:
        row = dict(rec)
        row["required_skills"] = ", ".join(rec.get("required_skills", []))
        # Collapse internal newlines so each record stays on one CSV line
        if "raw_text_justification" in row and isinstance(row["raw_text_justification"], str):
            row["raw_text_justification"] = " ".join(row["raw_text_justification"].split())
        if "one_line_summary" in row and isinstance(row["one_line_summary"], str):
            row["one_line_summary"] = " ".join(row["one_line_summary"].split())
        row["bias_flags"] = ", ".join(rec.get("bias_flags", []))
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=talentsync_export.csv"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
