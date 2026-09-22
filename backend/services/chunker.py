"""Section-aware chunking (04_ai_ml_spec.md § 3).

All seven § 3.2 rules are implemented here. Note that on the *provided* corpus only
rules 1, 3 and 7 ever fire: no section exceeds 400 tokens (longest ~227), so every
section emits exactly one chunk and the overlap, sentence-boundary and 500-cap paths
are never reached by real data. They are still implemented to spec and are covered by
`tests/test_chunker.py` using synthetic long sections — otherwise they would be
untested code that happens to look right.

Token counts are `tiktoken` `cl100k_base` throughout (rule 1). Overlap is 80 *tokens*
(rule 5) — not characters, not words.
"""

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable, Optional

import tiktoken

from config import (
    CHUNK_ID_TEMPLATE,
    CHUNK_MAX_TOKENS,
    CHUNK_MIN_TOKENS,
    CHUNK_OVERLAP_TOKENS,
    CHUNK_TARGET_TOKENS,
    SENTENCE_BOUNDARY_WINDOW_TOKENS,
    TOKENIZER_ENCODING,
)

# § 3.1, in this order. Chunk ids increase monotonically per judgment across sections.
SECTION_ORDER = ("headnote", "facts", "issues", "held", "reasoning", "order")

# Rule 6: "period, question mark, semicolon".
SENTENCE_ENDINGS = (".", "?", ";")

# § 3.3 chunk metadata block.
METADATA_FIELDS = ("citation", "case_name", "court", "court_tier", "date",
                   "jurisdiction", "state")


@dataclass
class Chunk:
    chunk_id: str
    judgment_id: str
    section: str
    text: str
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "judgment_id": self.judgment_id,
            "section": self.section,
            "text": self.text,
            "token_count": self.token_count,
            "metadata": self.metadata,
        }


@lru_cache(maxsize=1)
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(TOKENIZER_ENCODING)


def count_tokens(text: str) -> int:
    return len(_encoding().encode(text))


def _ends_sentence(encoding: tiktoken.Encoding, tokens: list[int], end: int) -> bool:
    """Does the chunk ending at ``end`` (exclusive) finish on a sentence boundary?"""
    if end <= 0 or end > len(tokens):
        return False
    tail = encoding.decode(tokens[end - 1:end]).rstrip()
    return tail.endswith(SENTENCE_ENDINGS)


def _find_split(encoding: tiktoken.Encoding, tokens: list[int], start: int,
                target: int, hard_limit: int) -> int:
    """Rule 6: nearest sentence boundary within ±30 tokens of target, else target.

    Candidates are examined by increasing distance so the *nearest* boundary wins, and
    each is clamped to the rule-4 hard limit so preferring a boundary can never push a
    chunk past 500 tokens.
    """
    for distance in range(SENTENCE_BOUNDARY_WINDOW_TOKENS + 1):
        for candidate in ({target - distance, target + distance}
                          if distance else {target}):
            if candidate <= start or candidate > hard_limit:
                continue
            if _ends_sentence(encoding, tokens, candidate):
                return candidate
    return min(target, hard_limit)


def chunk_text(text: str) -> list[str]:
    """Split one section's text per rules 2–6. Returns chunk strings in order."""
    encoding = _encoding()
    tokens = encoding.encode(text)

    # Rule 3: a short section is emitted whole, regardless of the 150 minimum.
    if len(tokens) < CHUNK_MIN_TOKENS:
        return [text] if text else []

    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        remaining = len(tokens) - start

        # Rule 4: whatever is left fits in one chunk, so stop here rather than
        # emitting a split that leaves a stub below the minimum.
        if remaining <= CHUNK_MAX_TOKENS:
            chunks.append(encoding.decode(tokens[start:]))
            break

        hard_limit = min(start + CHUNK_MAX_TOKENS, len(tokens))
        end = _find_split(encoding, tokens, start, start + CHUNK_TARGET_TOKENS,
                          hard_limit)
        chunks.append(encoding.decode(tokens[start:end]))

        # Rule 5: the next chunk starts 80 tokens back inside this one.
        next_start = end - CHUNK_OVERLAP_TOKENS
        if next_start <= start:  # defensive: guarantees forward progress
            next_start = end
        start = next_start

    return chunks


def chunk_judgment(judgment: dict[str, Any]) -> list[Chunk]:
    """Chunk every present section of one judgment, in § 3.1 order.

    Rule 7: sections are chunked independently, so no chunk spans two sections and
    no overlap crosses a section boundary.
    """
    judgment_id = judgment["judgment_id"]
    metadata = {key: judgment.get(key) for key in METADATA_FIELDS}

    chunks: list[Chunk] = []
    index = 1  # § 3.4: zero-padded 3-digit, starting at 001, per judgment
    for section in SECTION_ORDER:
        text = (judgment.get(section) or "").strip()
        if not text:
            continue
        for piece in chunk_text(text):
            chunks.append(Chunk(
                chunk_id=CHUNK_ID_TEMPLATE.format(judgment_id=judgment_id,
                                                  index=index),
                judgment_id=judgment_id,
                section=section,
                text=piece,
                token_count=count_tokens(piece),
                metadata=dict(metadata),
            ))
            index += 1
    return chunks


def chunk_corpus(judgments: Iterable[dict[str, Any]]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for judgment in judgments:
        chunks.extend(chunk_judgment(judgment))
    return chunks


def load_corpus(path: Optional[str] = None) -> list[dict[str, Any]]:
    """Read `judgments_corpus.json`, tolerating either a bare list or a wrapper."""
    import json
    from pathlib import Path

    from config import REPO_ROOT

    target = Path(path) if path else REPO_ROOT / "data" / "judgments_corpus.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for key in ("judgments", "corpus", "data"):
            if key in data:
                return data[key]
        raise ValueError(f"No judgment list found in {target}")
    return data
