"""Chunker tests (04_ai_ml_spec.md § 3.2, rules 1-7).

The provided corpus never exercises most of these rules: no section reaches the 400-token
target, so every section emits one chunk and the overlap, sentence-boundary and 500-cap
branches are dead on real data. Testing only against the corpus would therefore prove
almost nothing about the chunker.

So the tests come in two halves:
  - assertions against the real corpus, which pin the 72-chunk / 001-006 structure;
  - assertions against *synthetic* long sections, which are the only way to reach rules
    2, 4, 5 and 6 at all.
"""

import re

import pytest

from config import (
    CHUNK_MAX_TOKENS,
    CHUNK_MIN_TOKENS,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_TARGET_TOKENS,
    SENTENCE_BOUNDARY_WINDOW_TOKENS,
)
from services.chunker import (
    SECTION_ORDER,
    chunk_corpus,
    chunk_judgment,
    chunk_text,
    count_tokens,
    load_corpus,
    _encoding,
)

CHUNK_ID_PATTERN = re.compile(r"^j_\d{4}_chunk_\d{3}$")


# --- helpers ----------------------------------------------------------------


def synthetic_section(sentences: int, words_per_sentence: int = 12) -> str:
    """Prose long enough to force splitting, with real sentence boundaries."""
    return " ".join(
        " ".join(f"word{i}{j}" for j in range(words_per_sentence)) + "."
        for i in range(sentences)
    )


def token_ids(text: str) -> list[int]:
    return _encoding().encode(text)


def overlap_length(first: str, second: str) -> int:
    """Count trailing tokens of `first` that open `second`."""
    a, b = token_ids(first), token_ids(second)
    for size in range(min(len(a), len(b)), 0, -1):
        if a[-size:] == b[:size]:
            return size
    return 0


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


# --- real corpus: structure -------------------------------------------------


def test_corpus_yields_exactly_72_chunks(corpus):
    """12 judgments x 6 sections, one chunk each — no section reaches the target."""
    assert len(corpus) == 12
    assert len(chunk_corpus(corpus)) == 72


def test_every_section_emits_exactly_one_chunk(corpus):
    for judgment in corpus:
        chunks = chunk_judgment(judgment)
        assert len(chunks) == 6
        assert [c.section for c in chunks] == list(SECTION_ORDER)


def test_chunk_ids_are_001_to_006_per_judgment(corpus):
    """§ 3.4: zero-padded 3-digit, starting at 001, monotonic within a judgment."""
    for judgment in corpus:
        chunks = chunk_judgment(judgment)
        expected = [f"{judgment['judgment_id']}_chunk_{i:03d}" for i in range(1, 7)]
        assert [c.chunk_id for c in chunks] == expected


def test_chunk_id_format_matches_spec(corpus):
    for chunk in chunk_corpus(corpus):
        assert CHUNK_ID_PATTERN.match(chunk.chunk_id), chunk.chunk_id


def test_token_counts_are_accurate(corpus):
    for chunk in chunk_corpus(corpus):
        assert chunk.token_count == count_tokens(chunk.text)


def test_chunk_carries_section_3_3_metadata(corpus):
    chunk = chunk_judgment(corpus[0])[0]
    assert set(chunk.metadata) == {"citation", "case_name", "court", "court_tier",
                                   "date", "jurisdiction", "state"}


def test_no_corpus_section_reaches_the_target(corpus):
    """Documents why the split branches are dead on real data (finding 2)."""
    longest = max(count_tokens(j[s]) for j in corpus for s in SECTION_ORDER if j.get(s))
    assert longest < CHUNK_TARGET_TOKENS


# --- rule 3: short sections -------------------------------------------------


def test_section_below_minimum_is_emitted_whole():
    text = "A short holding. Two sentences only."
    assert count_tokens(text) < CHUNK_MIN_TOKENS
    assert chunk_text(text) == [text]


def test_empty_section_emits_nothing():
    assert chunk_text("") == []


def test_section_at_minimum_boundary_is_not_split():
    """At >= 150 but <= 500 tokens, rule 4's 'fits in one chunk' path still applies."""
    text = synthetic_section(sentences=10)
    assert CHUNK_MIN_TOKENS <= count_tokens(text) <= CHUNK_MAX_TOKENS
    assert len(chunk_text(text)) == 1


# --- rules 2, 4, 5, 6: synthetic long sections ------------------------------


def test_long_section_splits_into_multiple_chunks():
    text = synthetic_section(sentences=200)
    assert count_tokens(text) > CHUNK_MAX_TOKENS
    assert len(chunk_text(text)) > 1


def test_no_chunk_ever_exceeds_the_maximum():
    """Rule 4: 'Never emit a chunk longer than this.'"""
    for sentences in (60, 120, 200, 400):
        for chunk in chunk_text(synthetic_section(sentences)):
            assert count_tokens(chunk) <= CHUNK_MAX_TOKENS


def test_consecutive_chunks_overlap_by_exactly_80_tokens():
    """Rule 5: 80 *tokens* — not characters, not words."""
    chunks = chunk_text(synthetic_section(sentences=300))
    assert len(chunks) >= 3
    # The final chunk absorbs the remainder, so its start is not an 80-token step.
    for first, second in zip(chunks, chunks[1:-1]):
        assert overlap_length(first, second) == CHUNK_OVERLAP_TOKENS


def test_overlap_is_not_80_characters_or_words():
    """Guards the single most likely misreading of rule 5."""
    chunks = chunk_text(synthetic_section(sentences=300))
    first, second = chunks[0], chunks[1]
    overlap_tokens = _encoding().decode(token_ids(first)[-CHUNK_OVERLAP_TOKENS:])
    assert second.startswith(overlap_tokens)
    assert len(overlap_tokens) != CHUNK_OVERLAP_TOKENS  # not 80 characters
    assert len(overlap_tokens.split()) != CHUNK_OVERLAP_TOKENS  # not 80 words


def test_split_prefers_a_sentence_boundary_within_the_window():
    """Rule 6: prefer the nearest '.', '?' or ';' within ±30 tokens of the target."""
    chunks = chunk_text(synthetic_section(sentences=300))
    assert chunks[0].rstrip().endswith((".", "?", ";"))


def test_split_lands_within_the_boundary_window_of_the_target():
    chunks = chunk_text(synthetic_section(sentences=300))
    first_length = count_tokens(chunks[0])
    assert abs(first_length - CHUNK_TARGET_TOKENS) <= SENTENCE_BOUNDARY_WINDOW_TOKENS


def test_falls_back_to_target_when_no_boundary_is_available():
    """No '.', '?' or ';' anywhere, so rule 6 must degrade to splitting at target."""
    text = " ".join(f"word{i}" for i in range(2000))
    assert "." not in text
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert count_tokens(chunks[0]) == CHUNK_TARGET_TOKENS


def test_chunking_is_deterministic():
    text = synthetic_section(sentences=250)
    assert chunk_text(text) == chunk_text(text)


def test_chunks_cover_the_whole_section():
    """Nothing is dropped: concatenating chunks minus overlap rebuilds the text."""
    text = synthetic_section(sentences=200)
    chunks = chunk_text(text)
    rebuilt = chunks[0]
    for previous, current in zip(chunks, chunks[1:]):
        rebuilt += _encoding().decode(
            token_ids(current)[overlap_length(previous, current):]
        )
    assert token_ids(rebuilt) == token_ids(text)


# --- rule 7: section independence -------------------------------------------


def test_sections_are_chunked_independently():
    """A chunk never spans two sections, and ids restart per judgment, not per section."""
    judgment = {
        "judgment_id": "j_9999",
        "citation": "x", "case_name": "y", "court": "z", "court_tier": 1,
        "date": "2020-01-01", "jurisdiction": "Criminal", "state": None,
        "headnote": synthetic_section(sentences=200),
        "facts": synthetic_section(sentences=200),
        "issues": "", "held": "", "reasoning": "", "order": "",
    }
    chunks = chunk_judgment(judgment)
    headnote = [c for c in chunks if c.section == "headnote"]
    facts = [c for c in chunks if c.section == "facts"]
    assert len(headnote) > 1 and len(facts) > 1

    # No overlap bleeds across the boundary between the last headnote chunk and the
    # first facts chunk, even though both sections have identical text.
    assert overlap_length(headnote[-1].text, facts[0].text) != CHUNK_OVERLAP_TOKENS

    # Ids continue across sections rather than restarting.
    assert chunks[0].chunk_id == "j_9999_chunk_001"
    assert [c.chunk_id for c in chunks] == [
        f"j_9999_chunk_{i:03d}" for i in range(1, len(chunks) + 1)
    ]


def test_missing_sections_are_skipped_without_gaps_in_ids():
    judgment = {
        "judgment_id": "j_8888",
        "citation": "x", "case_name": "y", "court": "z", "court_tier": 2,
        "date": "2020-01-01", "jurisdiction": "Civil", "state": "Delhi",
        "headnote": "Only this section is present.",
        "facts": None, "issues": "", "held": None, "reasoning": "", "order": None,
    }
    chunks = chunk_judgment(judgment)
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "j_8888_chunk_001"
