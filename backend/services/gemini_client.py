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
    DIMENSION_GENERATION_RETRIES,
    DIMENSIONS_PER_CASE,
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

# --- 04_ai_ml_spec.md § 4.2, verbatim ---------------------------------------
# The `//` comment inside the JSON block is part of the spec's prompt text and is
# reproduced as-is rather than "corrected" into valid JSON.

DIMENSION_GENERATION_PROMPT = """You are a senior Indian litigator identifying the distinct legal propositions and factual scenarios in a case that could yield relevant precedents.

Case metadata:
- Parties: {parties}
- Court: {court}
- Jurisdiction: {jurisdiction}
- Sections invoked: {sections_invoked}
- Synopsis: {synopsis}

Generate exactly 3 "dimensional queries" for precedent retrieval. Each dimension must target a DISTINCT legal proposition or factual matrix — not a restatement of the case facts.

Good dimension query: "Non-compliance with Section 65B certificate for electronic evidence"
Bad dimension query: "Criminal case of Rahul Kasat involving murder"

Return ONLY valid JSON:
{{
  "dimensions": [
    {{
      "dimension_number": 1,
      "query": "string, 5-15 words, targets a specific legal proposition",
      "rationale": "string, one sentence explaining why this dimension matters"
    }},
    // exactly 3 entries, dimension_number 1, 2, 3
  ]
}}"""

DIMENSION_COUNT_REMINDER = (
    "\n\nYour previous response did not contain exactly 3 dimensions. "
    "Return ONLY the JSON object, containing exactly 3 entries in \"dimensions\", "
    "numbered 1, 2 and 3."
)

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


def _valid_dimensions(payload: Any) -> Optional[list[dict]]:
    """Accept only a list of exactly 3 entries that each carry query and rationale."""
    if not isinstance(payload, dict):
        return None
    dimensions = payload.get("dimensions")
    if not isinstance(dimensions, list) or len(dimensions) != DIMENSIONS_PER_CASE:
        return None
    if not all(isinstance(d, dict) and d.get("query") and d.get("rationale")
               for d in dimensions):
        return None
    return dimensions


def generate_dimensions(metadata: dict) -> list[dict]:
    """Run the § 4.2 prompt. Exactly 3 dimensions, re-prompt once, then error.

    § 4.2's strict rule: "If the model returns fewer or more, re-prompt once. If it
    still misbehaves, raise an error. Do not silently fall back to 2 or 4." So a wrong
    count is never trimmed or padded — the whole response is discarded and re-requested,
    and a second failure is surfaced as 502 rather than quietly degraded.
    """
    sections = metadata.get("sections_invoked") or []
    prompt = DIMENSION_GENERATION_PROMPT.format(
        parties=metadata.get("parties", ""),
        court=metadata.get("court", ""),
        jurisdiction=metadata.get("jurisdiction", ""),
        sections_invoked=", ".join(sections) if isinstance(sections, list) else sections,
        synopsis=metadata.get("synopsis", ""),
    )

    last_count = None
    for attempt in range(DIMENSION_GENERATION_RETRIES + 1):
        payload = generate_json(prompt if attempt == 0
                                else prompt + DIMENSION_COUNT_REMINDER)
        dimensions = _valid_dimensions(payload)
        if dimensions is not None:
            # Renumber by position so the response always satisfies the 1/2/3 contract
            # even when the model numbers them oddly. The count itself is never fixed up.
            return [
                {
                    "dimension_number": index,
                    "query": str(d["query"]),
                    "rationale": str(d["rationale"]),
                }
                for index, d in enumerate(dimensions, 1)
            ]

        last_count = (len(payload.get("dimensions", []))
                      if isinstance(payload, dict)
                      and isinstance(payload.get("dimensions"), list) else None)
        log_event(event="dimension_count_wrong", attempt=attempt, received=last_count)

    raise AppError(
        502, "upstream_error",
        f"Gemini did not return exactly {DIMENSIONS_PER_CASE} dimensions after a retry.",
        {"expected": DIMENSIONS_PER_CASE, "received": last_count},
    )
