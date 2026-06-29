"""
LLM extraction with round-robin key/model fallback.

Priority order (best first):
  Gemini 2.5-flash  -> all 4 Google keys
  Gemini 2.0-flash  -> all 4 Google keys
  Gemini 1.5-flash  -> all 4 Google keys
  Groq llama-3.3-70b-versatile -> all 5 Groq keys
  Groq llama-3.1-70b-versatile -> all 5 Groq keys
  Groq mixtral-8x7b-32768      -> all 5 Groq keys

On rate-limit/quota, rotate to next slot immediately (2s pause).
On any other error, log and skip to next provider tier.
"""
import os
import json
import time
from typing import Protocol, runtime_checkable
from dotenv import load_dotenv
from pydantic import ValidationError

from .contracts import JobExtractionSchema
from .prompts import SYSTEM_PROMPT, FEWSHOT, USER_TEMPLATE


# ── LLMProvider interface (vLLM swaps in behind this later) ───────────────────

@runtime_checkable
class LLMProvider(Protocol):
    def extract(self, text: str) -> JobExtractionSchema | None: ...
    def generate(self, prompt: str, system: str | None = None) -> str | None: ...
    def rewrite(self, jd_text: str, instruction: str) -> str | None: ...


class GeminiGroqProvider:
    """Default provider — wraps the module-level extract() and generate() functions.

    vLLM swaps in behind the same interface when self-hosted residency is required.
    """

    def extract(self, text: str) -> JobExtractionSchema | None:
        return extract(text)

    def generate(self, prompt: str, system: str | None = None) -> str | None:
        return generate(prompt, system)

    def rewrite(self, jd_text: str, instruction: str) -> str | None:
        prompt = (
            f"Instruction: {instruction}\n\n"
            f"Job Description to rewrite:\n{jd_text}"
        )
        return generate(prompt, "You are an expert JD editor. Rewrite the job description "
                                "exactly as instructed. Return only the revised JD text.")


default_provider: LLMProvider = GeminiGroqProvider()

load_dotenv()

_STUB_MODE = os.environ.get("TALENTSYNC_STUB", "").lower() in ("1", "true", "yes")

# ── Key pools (read once at import, skip missing vars) ─────────────────────────

_GEMINI_KEYS: list[str] = [k for k in [
    os.environ.get("GOOGLE_API_KEY"),
    os.environ.get("GOOGLE_API_KEY_2"),
    os.environ.get("GOOGLE_API_KEY_3"),
    os.environ.get("GOOGLE_API_KEY_4"),
] if k]

_GROQ_KEYS: list[str] = [k for k in [
    os.environ.get("GROQ_API_KEY"),
    os.environ.get("GROQ_API_KEY_2"),
    os.environ.get("GROQ_API_KEY_3"),
    os.environ.get("GROQ_API_KEY_4"),
    os.environ.get("GROQ_API_KEY_5"),
] if k]

_GEMINI_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
_GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "mixtral-8x7b-32768"]


def _build_pool() -> list[tuple[str, str, str]]:
    """Build (provider, key, model) priority list. Best model tier first, all keys per tier."""
    pool: list[tuple[str, str, str]] = []
    for model in _GEMINI_MODELS:
        for key in _GEMINI_KEYS:
            pool.append(("gemini", key, model))
    for model in _GROQ_MODELS:
        for key in _GROQ_KEYS:
            pool.append(("groq", key, model))
    return pool


_POOL = _build_pool()


# ── Provider-specific callers ──────────────────────────────────────────────────

def _try_gemini(key: str, model: str, prompt: str) -> tuple[JobExtractionSchema | None, bool]:
    """Returns (result_or_None, rotate). rotate=True means rate-limited, try next slot."""
    from google import genai
    from google.genai import types
    try:
        client = genai.Client(api_key=key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
            ),
        )
        data = json.loads(response.text)
        return JobExtractionSchema(**data), False
    except ValidationError as e:
        print(f"    [warn] gemini/{model} validation: {e}")
        return None, False
    except Exception as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg or "UNAVAILABLE" in msg:
            print(f"    [rotate] gemini/{model} quota/unavail -> next slot")
            return None, True
        print(f"    [error] gemini/{model}: {msg[:120]}")
        return None, False


def _try_groq(key: str, model: str, description: str) -> tuple[JobExtractionSchema | None, bool]:
    """Returns (result_or_None, rotate)."""
    try:
        from groq import Groq
    except ImportError:
        return None, False  # groq package not installed; skip silently

    try:
        client = Groq(api_key=key)
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{FEWSHOT}\n\n{USER_TEMPLATE.format(description=description)}"},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = completion.choices[0].message.content
        data = json.loads(raw)
        return JobExtractionSchema(**data), False
    except ValidationError as e:
        print(f"    [warn] groq/{model} validation: {e}")
        return None, False
    except Exception as e:
        msg = str(e)
        if "429" in msg or "rate" in msg.lower() or "quota" in msg.lower():
            print(f"    [rotate] groq/{model} rate-limited -> next slot")
            return None, True
        print(f"    [error] groq/{model}: {msg[:120]}")
        return None, False


# ── Free-form generation (intake drafts, Q&A, preset rewrites) ────────────────

_STUB_GENERATE = (
    "Software Engineer — Mid-Level\n\n"
    "About the Role\nWe are seeking a Software Engineer with 3-5 years of experience "
    "to join our product team. You will own feature development end-to-end and "
    "collaborate with cross-functional teams.\n\n"
    "Requirements\n- 3-5 years of relevant experience\n"
    "- Proficiency in Python and SQL\n"
    "- Experience with REST APIs and AWS\n\n"
    "What We Offer\n- Compensation: ₹15-22 LPA\n"
    "- Hybrid work model (3 days in-office)\n"
    "- Health insurance for self and dependents\n\n"
    "We are an equal opportunity employer and welcome applications from all qualified candidates."
)


def _try_gemini_generate(
    key: str, model: str, prompt: str, system: str | None
) -> tuple[str | None, bool]:
    from google import genai
    from google.genai import types
    try:
        client = genai.Client(api_key=key)
        full = f"{system}\n\n{prompt}" if system else prompt
        response = client.models.generate_content(
            model=model,
            contents=full,
            config=types.GenerateContentConfig(temperature=0.3),
        )
        text = response.text.strip()
        return text if text else None, False
    except Exception as e:
        msg = str(e)
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg or "UNAVAILABLE" in msg:
            print(f"    [rotate] gemini/{model} quota/unavail -> next slot (generate)")
            return None, True
        print(f"    [error] gemini/{model} generate: {msg[:120]}")
        return None, False


def _try_groq_generate(
    key: str, model: str, prompt: str, system: str | None
) -> tuple[str | None, bool]:
    try:
        from groq import Groq
    except ImportError:
        return None, False

    try:
        client = Groq(api_key=key)
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
        )
        text = completion.choices[0].message.content.strip()
        return text if text else None, False
    except Exception as e:
        msg = str(e)
        if "429" in msg or "rate" in msg.lower() or "quota" in msg.lower():
            print(f"    [rotate] groq/{model} rate-limited -> next slot (generate)")
            return None, True
        print(f"    [error] groq/{model} generate: {msg[:120]}")
        return None, False


def generate(prompt: str, system: str | None = None) -> str | None:
    """
    Free-form text generation using the same round-robin pool as extract().
    Used for intake drafts, Q&A answers, and preset rewrites. Returns None on failure.
    """
    if _STUB_MODE:
        return _STUB_GENERATE

    if not _POOL:
        print("    [error] no API keys configured in .env")
        return None

    n = len(_POOL)
    for i, (provider, key, model) in enumerate(_POOL):
        result, rotate = (
            _try_gemini_generate(key, model, prompt, system)
            if provider == "gemini"
            else _try_groq_generate(key, model, prompt, system)
        )
        if result is not None:
            if i > 0:
                print(f"    [ok] slot {i+1}/{n}: {provider}/{model} (generate)")
            return result
        if rotate:
            time.sleep(2)

    print("    [warn] all pool slots exhausted (generate)")
    return None


# ── Stub ───────────────────────────────────────────────────────────────────────

def _stub_extract(description: str) -> JobExtractionSchema:
    text_lower = description.lower()
    if "6+" in text_lower or "7+" in text_lower or "10+" in text_lower:
        tier = "Senior"
    elif "fresher" in text_lower or "0-1" in text_lower or "1-2 yrs" in text_lower:
        tier = "Entry-Level"
    elif "2-4" in text_lower or "3-5" in text_lower:
        tier = "Mid-Level"
    else:
        tier = "Uncertain"

    words = description.split()
    quote = " ".join(words[:6]) if words else "stub quote"

    return JobExtractionSchema(
        one_line_summary="A stub summary for testing purposes.",
        seniority_level=tier,
        required_skills=["python", "sql"] if "python" in text_lower else ["stub_skill"],
        raw_text_justification=quote,
    )


# ── Public entry point ─────────────────────────────────────────────────────────

def extract(description: str) -> JobExtractionSchema | None:
    if _STUB_MODE:
        return _stub_extract(description)

    if not _POOL:
        print("    [error] no API keys configured in .env")
        return None

    prompt = f"{SYSTEM_PROMPT}\n\n{FEWSHOT}\n\n{USER_TEMPLATE.format(description=description)}"
    n = len(_POOL)

    for i, (provider, key, model) in enumerate(_POOL):
        result, rotate = (
            _try_gemini(key, model, prompt)
            if provider == "gemini"
            else _try_groq(key, model, description)
        )
        if result is not None:
            if i > 0:
                print(f"    [ok] slot {i+1}/{n}: {provider}/{model}")
            return result
        if rotate:
            time.sleep(2)  # brief pause before next key/model
        # on non-rotate error: continue to next slot immediately

    print("    [warn] all pool slots exhausted")
    return None
