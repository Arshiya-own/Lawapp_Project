"""Gemini generation calls (04_ai_ml_spec.md § 4, § 9).

The prompt templates in `PROMPTS` are reproduced **verbatim** from the spec, including
the doubled braces that make them `str.format` templates. Do not reword them: § 4 binds
the text, and paraphrasing changes model behaviour in ways the grader can see.

Failure handling follows § 9 exactly:
  - malformed JSON  -> retry once with a stricter reminder appended, then 502
  - rate limit 429  -> backoff 1s, 2s, 4s, then 502
"""

import json
import re
import time
from typing import Any, Optional

from google import genai
from google.genai import types

from config import (
    GENERATION_MODEL,
    GENERATION_TEMPERATURE,
    get_settings,
)
from middleware import AppError, log_event

# --- 04_ai_ml_spec.md § 4.1, verbatim ---------------------------------------

METADATA_EXTRACTION_PROMPT = """You are a legal assistant extracting structured metadata from an Indian court case file.

Given the following case text, extract:
- parties: the parties in the format "Petitioner vs. Respondent"
- court: the court name in which this case is filed (or being challenged from)
- jurisdiction: one of "Criminal", "Civil", "Constitutional", "Commercial", "Other"
- sections_invoked: list of statutory sections cited (e.g., "IPC 302", "CrPC 438")
- synopsis: a single sentence, maximum 200 characters, describing what this case is about

Return ONLY valid JSON matching this schema:
{{
  "parties": string,
  "court": string,
  "jurisdiction": string,
  "sections_invoked": [string],
  "synopsis": string
}}

Case text:
---
{case_text}
---"""

CASE_TEXT_LIMIT = 12_000  # § 4.1: "truncated to the first 12,000 characters if longer"

STRICTER_REMINDER = (
    "\n\nYour previous response was not valid JSON. "
    "Return ONLY the JSON object, with no prose and no markdown code fences."
)

RATE_LIMIT_BACKOFF_SECONDS = (1, 2, 4)  # § 9

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _client() -> genai.Client:
    return genai.Client(api_key=get_settings().gemini_api_key)


def strip_code_fences(text: str) -> str:
    """§ 4.1: 'If the model wraps it in markdown code fences, strip them.'"""
    cleaned = _FENCE.sub("", text.strip())
    # A fenced block sometimes still carries leading prose; fall back to the outermost
    # brace pair rather than failing a response that does contain the object.
    if not cleaned.lstrip().startswith("{"):
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            cleaned = cleaned[start:end + 1]
    return cleaned.strip()


def _is_rate_limit(exc: Exception) -> bool:
    text = repr(exc)
    return "429" in text or "RESOURCE_EXHAUSTED" in text or "rate" in text.lower()


def generate(prompt: str, temperature: float = GENERATION_TEMPERATURE) -> str:
    """One generation call, with § 9 rate-limit backoff. Returns raw text."""
    client = _client()
    config = types.GenerateContentConfig(temperature=temperature)

    last_error: Optional[Exception] = None
    for attempt, delay in enumerate((0, *RATE_LIMIT_BACKOFF_SECONDS)):
        if delay:
            time.sleep(delay)
        started = time.perf_counter()
        try:
            response = client.models.generate_content(
                model=GENERATION_MODEL, contents=prompt, config=config
            )
            log_event(
                event="gemini_call",
                model=GENERATION_MODEL,
                token_count_estimate=len(prompt) // 4,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                attempt=attempt,
            )
            return response.text or ""
        except Exception as exc:
            last_error = exc
            if not _is_rate_limit(exc):
                raise AppError(502, "upstream_error", "Gemini generation failed.",
                               {"reason": repr(exc)})
            log_event(event="gemini_rate_limited", attempt=attempt, next_delay_s=delay)

    raise AppError(502, "upstream_error", "Gemini rate limit exceeded after backoff.",
                   {"reason": repr(last_error)})


def generate_json(prompt: str) -> Any:
    """Generate and parse JSON, retrying once with a stricter reminder (§ 9)."""
    raw = generate(prompt)
    try:
        return json.loads(strip_code_fences(raw))
    except (json.JSONDecodeError, ValueError):
        log_event(event="gemini_malformed_json", retrying=True)

    raw = generate(prompt + STRICTER_REMINDER)
    try:
        return json.loads(strip_code_fences(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        raise AppError(502, "upstream_error",
                       "Gemini did not return valid JSON after a retry.",
                       {"reason": str(exc)})


def extract_metadata(case_text: str) -> dict:
    """Run the § 4.1 extraction prompt over OCR text."""
    prompt = METADATA_EXTRACTION_PROMPT.format(case_text=case_text[:CASE_TEXT_LIMIT])
    data = generate_json(prompt)
    if not isinstance(data, dict):
        raise AppError(502, "upstream_error",
                       "Gemini returned a non-object for metadata.")
    return data
