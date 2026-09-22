"""Court-hierarchy ranking (04_ai_ml_spec.md § 5.2 steps 3-5, § 5.3, § 5.5).

The pipeline after vector search is:

    threshold (0.65) -> collapse chunks to judgments -> recompute tier
    -> drop tier 4 -> sort -> take 5

**Tier is recomputed, not read from the corpus.** `court_tier` in
`judgments_corpus.json` is baked for a Maharashtra-origin case: Bombay HC is stored as
tier 2 and Delhi HC as tier 3. But § 5.3 defines tier 2 as "High Court of the same state
as the uploaded case", which is a property of the *query*, not of the judgment — for a
Delhi-origin case those two tiers must swap. Trusting the stored field would silently
mis-rank every case that did not originate in Maharashtra.

Sort order is `court_tier` ascending, then `date` **descending**, then
`similarity_score` descending. The middle key is the one that is easy to get backwards.
"""

import re
from dataclasses import dataclass
from typing import Any, Optional

from config import (
    EXCLUDED_COURT_TIER,
    FINAL_TOP_K_PER_DIMENSION,
    SIMILARITY_PRECISION,
    SIMILARITY_THRESHOLD,
    SNIPPET_BOUNDARY_SEARCH_CHARS,
    SNIPPET_MAX_CHARS,
)
from services.vector_store import SearchHit

SUPREME_COURT_TIER = 1
SAME_STATE_HIGH_COURT_TIER = 2
OTHER_HIGH_COURT_TIER = 3

# High Court -> state, for resolving the uploaded case's origin from its court name.
HIGH_COURT_STATES = {
    "bombay": "Maharashtra",
    "delhi": "Delhi",
    "madras": "Tamil Nadu",
    "calcutta": "West Bengal",
    "karnataka": "Karnataka",
    "allahabad": "Uttar Pradesh",
    "gujarat": "Gujarat",
    "kerala": "Kerala",
    "rajasthan": "Rajasthan",
    "punjab and haryana": "Punjab and Haryana",
    "madhya pradesh": "Madhya Pradesh",
    "patna": "Bihar",
    "orissa": "Odisha",
    "telangana": "Telangana",
    "andhra pradesh": "Andhra Pradesh",
    "gauhati": "Assam",
    "jharkhand": "Jharkhand",
    "chhattisgarh": "Chhattisgarh",
    "uttarakhand": "Uttarakhand",
    "himachal pradesh": "Himachal Pradesh",
    "jammu and kashmir": "Jammu and Kashmir",
    "sikkim": "Sikkim",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "tripura": "Tripura",
}

STATE_NAMES = sorted(set(HIGH_COURT_STATES.values()), key=len, reverse=True)


def resolve_case_state(court: Optional[str]) -> Optional[str]:
    """Derive the uploaded case's state from its `court` metadata (§ 5.3).

    § 5.3 names `court` as the source, and its own examples cover both forms:
    "Bombay High Court" and "Supreme Court of India with Maharashtra origin".
    Returns None when the state cannot be determined, which § 5.3 says to treat as
    "all non-SC High Courts are tier 3".
    """
    if not court:
        return None
    lowered = court.lower()

    for fragment, state in HIGH_COURT_STATES.items():
        if fragment in lowered:
            return state

    # "...with Maharashtra origin" and similar.
    for state in STATE_NAMES:
        if re.search(rf"\b{re.escape(state.lower())}\b", lowered):
            return state
    return None


def is_supreme_court(court: Optional[str]) -> bool:
    return bool(court) and "supreme court" in court.lower()


def is_district_court(court: Optional[str]) -> bool:
    return bool(court) and any(token in court.lower()
                               for token in ("district court", "sessions court"))


def compute_court_tier(judgment_court: Optional[str], judgment_state: Optional[str],
                       case_state: Optional[str]) -> int:
    """§ 5.3 tier assignment, relative to the uploaded case's state."""
    if is_supreme_court(judgment_court):
        return SUPREME_COURT_TIER
    if is_district_court(judgment_court):
        return EXCLUDED_COURT_TIER
    if case_state and judgment_state and judgment_state == case_state:
        return SAME_STATE_HIGH_COURT_TIER
    return OTHER_HIGH_COURT_TIER


def build_snippet(text: str) -> str:
    """§ 5.5 snippet selection.

    Up to 400 characters. If a sentence boundary falls within the last 50 characters
    of that window, end there; otherwise hard-truncate and append an ellipsis.
    """
    if len(text) <= SNIPPET_MAX_CHARS:
        return text

    window = text[:SNIPPET_MAX_CHARS]
    search_from = SNIPPET_MAX_CHARS - SNIPPET_BOUNDARY_SEARCH_CHARS
    boundary = max(window.rfind(mark, search_from) for mark in (".", "?", "!", ";"))
    if boundary != -1:
        return window[:boundary + 1]
    return window + "…"


@dataclass
class RankedResult:
    judgment_id: str
    citation: str
    case_name: str
    court: str
    court_tier: int
    date: str
    chunk_id: str
    snippet: str
    similarity_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "judgment_id": self.judgment_id,
            "citation": self.citation,
            "case_name": self.case_name,
            "court": self.court,
            "court_tier": self.court_tier,
            "date": self.date,
            "chunk_id": self.chunk_id,
            "snippet": self.snippet,
            "similarity_score": self.similarity_score,
        }


def apply_threshold(hits: list[SearchHit],
                    threshold: float = SIMILARITY_THRESHOLD) -> list[SearchHit]:
    """§ 5.2 step 3. Zero survivors is a legitimate outcome (see QUESTIONS.md)."""
    return [hit for hit in hits if hit.similarity >= threshold]


def collapse_to_judgments(hits: list[SearchHit]) -> list[SearchHit]:
    """§ 5.2 step 4: one chunk per judgment, the highest-scoring one."""
    best: dict[str, SearchHit] = {}
    for hit in hits:
        current = best.get(hit.judgment_id)
        if current is None or hit.similarity > current.similarity:
            best[hit.judgment_id] = hit
    return list(best.values())


def rank(hits: list[SearchHit], case_state: Optional[str],
         top_k: int = FINAL_TOP_K_PER_DIMENSION) -> list[RankedResult]:
    """Full § 5.2 step 3 -> § 5.3 pipeline for one dimension."""
    surviving = collapse_to_judgments(apply_threshold(hits))

    results: list[RankedResult] = []
    for hit in surviving:
        metadata = hit.metadata
        tier = compute_court_tier(metadata.get("court"), metadata.get("state"),
                                  case_state)
        if tier == EXCLUDED_COURT_TIER:
            continue  # § 5.3: District Courts are filtered out before ranking
        results.append(RankedResult(
            judgment_id=hit.judgment_id,
            citation=metadata.get("citation", ""),
            case_name=metadata.get("case_name", ""),
            court=metadata.get("court", ""),
            court_tier=tier,
            date=metadata.get("date", ""),
            chunk_id=hit.chunk_id,
            snippet=build_snippet(hit.text),
            similarity_score=round(hit.similarity, SIMILARITY_PRECISION),
        ))

    # tier ascending, then date DESCENDING, then similarity descending.
    results.sort(key=lambda r: (r.court_tier, _date_sort_key(r.date),
                                -r.similarity_score))
    return results[:top_k]


def _date_sort_key(date: str) -> str:
    """Invert an ISO date so ascending sort yields descending chronology.

    Dates are `YYYY-MM-DD`, so complementing each digit gives a string whose
    lexicographic order is the reverse of the calendar order. This keeps the whole
    sort in a single ascending `sort()` call rather than relying on multiple passes.
    """
    return "".join(str(9 - int(ch)) if ch.isdigit() else ch for ch in date)
