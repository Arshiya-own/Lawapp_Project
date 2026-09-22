"""Ranker tests (04_ai_ml_spec.md § 5.2 steps 3-5, § 5.3, § 5.5).

Two things the real corpus cannot test:

- **Tier 4.** No District Court judgment exists in the corpus, so the exclusion rule is
  unreachable with real data and needs synthetic rows.
- **Tier 2 vs 3 for a non-Maharashtra case.** The corpus stores Bombay HC as tier 2 and
  Delhi HC as tier 3, which is only correct for a Maharashtra-origin case. Proving the
  tiers actually swap requires constructing a Delhi-origin query.

The date-descending tie-breaker is tested on its own because it is the single easiest
key in the chain to get backwards.
"""

import pytest

from config import FINAL_TOP_K_PER_DIMENSION, SIMILARITY_THRESHOLD, SNIPPET_MAX_CHARS
from services.ranker import (
    apply_threshold,
    build_snippet,
    collapse_to_judgments,
    compute_court_tier,
    rank,
    resolve_case_state,
)
from services.vector_store import SearchHit


def hit(judgment_id: str, similarity: float, court: str = "Supreme Court of India",
        state=None, date: str = "2020-01-01", chunk: str = "001",
        text: str = "snippet text") -> SearchHit:
    return SearchHit(
        chunk_id=f"{judgment_id}_chunk_{chunk}",
        judgment_id=judgment_id,
        section="held",
        text=text,
        similarity=similarity,
        metadata={
            "citation": f"({date[:4]}) 1 SCC 1",
            "case_name": f"Case {judgment_id}",
            "court": court,
            "court_tier": 1,          # deliberately wrong; the ranker must not use it
            "date": date,
            "jurisdiction": "Criminal",
            "state": state,
        },
    )


BOMBAY = ("Bombay High Court", "Maharashtra")
DELHI = ("Delhi High Court", "Delhi")
SUPREME = ("Supreme Court of India", None)


# --- resolving the uploaded case's state ------------------------------------


@pytest.mark.parametrize("court,expected", [
    ("Bombay High Court", "Maharashtra"),
    ("Delhi High Court", "Delhi"),
    ("Karnataka High Court", "Karnataka"),
    ("Supreme Court of India with Maharashtra origin", "Maharashtra"),
    ("Supreme Court of India", None),
    ("", None),
    (None, None),
])
def test_resolve_case_state(court, expected):
    assert resolve_case_state(court) == expected


# --- tier assignment (§ 5.3) ------------------------------------------------


def test_supreme_court_is_always_tier_1():
    for case_state in ("Maharashtra", "Delhi", None):
        assert compute_court_tier("Supreme Court of India", None, case_state) == 1


def test_same_state_high_court_is_tier_2():
    assert compute_court_tier(*BOMBAY, "Maharashtra") == 2


def test_other_state_high_court_is_tier_3():
    assert compute_court_tier(*BOMBAY, "Delhi") == 3


def test_tiers_swap_with_the_uploaded_case_state():
    """The corpus bakes Bombay=2 / Delhi=3; for a Delhi case they must invert."""
    assert compute_court_tier(*BOMBAY, "Maharashtra") == 2
    assert compute_court_tier(*DELHI, "Maharashtra") == 3

    assert compute_court_tier(*BOMBAY, "Delhi") == 3
    assert compute_court_tier(*DELHI, "Delhi") == 2


def test_undetermined_case_state_makes_every_high_court_tier_3():
    """§ 5.3: 'If the case's state cannot be determined, treat all non-SC HCs as 3.'"""
    assert compute_court_tier(*BOMBAY, None) == 3
    assert compute_court_tier(*DELHI, None) == 3


def test_stored_court_tier_is_ignored():
    """Every fixture carries court_tier=1; a Delhi HC judgment must still not be 1."""
    results = rank([hit("j_0008", 0.9, *DELHI)], case_state="Maharashtra")
    assert results[0].court_tier == 3


# --- tier 4 exclusion (synthetic: absent from the corpus) -------------------


@pytest.mark.parametrize("court", ["District Court, Pune", "Sessions Court, Mumbai"])
def test_district_courts_are_excluded_entirely(court):
    results = rank([hit("j_9001", 0.99, court, "Maharashtra")],
                   case_state="Maharashtra")
    assert results == []


def test_district_court_excluded_even_when_it_scores_highest():
    hits = [
        hit("j_9001", 0.99, "District Court, Pune", "Maharashtra"),
        hit("j_0001", 0.70, *SUPREME),
    ]
    results = rank(hits, case_state="Maharashtra")
    assert [r.judgment_id for r in results] == ["j_0001"]


# --- threshold and collapse (§ 5.2 steps 3-4) -------------------------------


def test_threshold_discards_below_0_65():
    hits = [hit("j_0001", 0.66), hit("j_0002", 0.65), hit("j_0003", 0.649)]
    assert [h.judgment_id for h in apply_threshold(hits)] == ["j_0001", "j_0002"]
    assert SIMILARITY_THRESHOLD == 0.65


def test_threshold_boundary_is_inclusive():
    assert len(apply_threshold([hit("j_0001", SIMILARITY_THRESHOLD)])) == 1


def test_collapse_keeps_the_highest_scoring_chunk_per_judgment():
    hits = [
        hit("j_0007", 0.71, chunk="001"),
        hit("j_0007", 0.88, chunk="004"),
        hit("j_0007", 0.80, chunk="005"),
        hit("j_0011", 0.75, chunk="002"),
    ]
    collapsed = {h.judgment_id: h for h in collapse_to_judgments(hits)}
    assert len(collapsed) == 2
    assert collapsed["j_0007"].chunk_id == "j_0007_chunk_004"
    assert collapsed["j_0007"].similarity == 0.88


def test_empty_input_produces_empty_output():
    assert rank([], case_state="Maharashtra") == []


def test_everything_below_threshold_produces_empty_output():
    """Backs the verbatim empty state in the frontend."""
    assert rank([hit("j_0001", 0.4), hit("j_0002", 0.5)], "Maharashtra") == []


# --- sort order (§ 5.3) -----------------------------------------------------


def test_tier_is_the_primary_key():
    hits = [
        hit("j_0008", 0.99, *DELHI, date="2022-01-01"),      # tier 3, best score
        hit("j_0001", 0.70, *SUPREME, date="2010-01-01"),    # tier 1, worst score
    ]
    assert [r.judgment_id for r in rank(hits, "Maharashtra")] == ["j_0001", "j_0008"]


def test_date_descending_breaks_tier_ties():
    """Gate 7: more recent first, within the same tier."""
    hits = [
        hit("j_0001", 0.80, *SUPREME, date="2014-09-18"),
        hit("j_0003", 0.80, *SUPREME, date="2020-06-22"),
        hit("j_0005", 0.80, *SUPREME, date="2017-11-08"),
    ]
    assert [r.date for r in rank(hits, "Maharashtra")] == [
        "2020-06-22", "2017-11-08", "2014-09-18"]


def test_date_ordering_is_not_ascending():
    """Explicit guard against the tie-breaker being inverted."""
    hits = [hit("j_0001", 0.8, *SUPREME, date="2011-01-01"),
            hit("j_0002", 0.8, *SUPREME, date="2021-01-01")]
    assert rank(hits, "Maharashtra")[0].date == "2021-01-01"


def test_similarity_descending_breaks_date_ties():
    hits = [
        hit("j_0001", 0.71, *SUPREME, date="2020-01-01"),
        hit("j_0003", 0.93, *SUPREME, date="2020-01-01"),
        hit("j_0005", 0.82, *SUPREME, date="2020-01-01"),
    ]
    assert [r.similarity_score for r in rank(hits, "Maharashtra")] == [0.93, 0.82, 0.71]


def test_full_tie_breaker_chain():
    """Tier beats date, date beats similarity — checked in one ordering."""
    hits = [
        hit("j_0002", 0.99, *BOMBAY, date="2022-03-22"),   # tier 2
        hit("j_0001", 0.66, *SUPREME, date="2014-09-18"),  # tier 1, older, low score
        hit("j_0003", 0.67, *SUPREME, date="2020-06-22"),  # tier 1, newer
        hit("j_0008", 0.98, *DELHI, date="2023-01-01"),    # tier 3
    ]
    assert [r.judgment_id for r in rank(hits, "Maharashtra")] == [
        "j_0003", "j_0001", "j_0002", "j_0008"]


def test_top_k_caps_at_five():
    hits = [hit(f"j_{i:04d}", 0.9 - i / 100, *SUPREME, date=f"20{10 + i}-01-01")
            for i in range(9)]
    results = rank(hits, "Maharashtra")
    assert len(results) == FINAL_TOP_K_PER_DIMENSION == 5


def test_similarity_is_rounded_to_three_decimals():
    assert rank([hit("j_0001", 0.8423719)], "Maharashtra")[0].similarity_score == 0.842


# --- snippets (§ 5.5) -------------------------------------------------------


def test_short_text_is_returned_unchanged():
    text = "A short holding."
    assert build_snippet(text) == text


def test_text_at_the_limit_is_unchanged():
    text = "x" * SNIPPET_MAX_CHARS
    assert build_snippet(text) == text


def test_long_text_prefers_a_sentence_boundary_in_the_last_50_chars():
    text = "a" * 360 + ". " + "b" * 200
    snippet = build_snippet(text)
    assert snippet.endswith(".")
    assert len(snippet) == 361
    assert "…" not in snippet


def test_long_text_without_a_nearby_boundary_is_hard_truncated():
    text = "word " * 400  # no sentence punctuation at all
    snippet = build_snippet(text)
    assert snippet.endswith("…")
    assert len(snippet) == SNIPPET_MAX_CHARS + 1


def test_boundary_outside_the_window_is_ignored():
    """A period at char 100 is too early; the rule only looks at the last 50."""
    text = "a" * 100 + ". " + "b" * 400
    snippet = build_snippet(text)
    assert snippet.endswith("…")


def test_snippet_never_exceeds_the_limit_plus_ellipsis():
    for length in (401, 500, 1200):
        assert len(build_snippet("z" * length)) <= SNIPPET_MAX_CHARS + 1
