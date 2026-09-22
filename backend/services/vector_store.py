"""FAISS vector store (04_ai_ml_spec.md § 5.2, § 6).

`IndexFlatIP` computes inner product, which equals cosine similarity only when both
sides are unit vectors. Every vector entering this module is normalized by
`services.embeddings` — see that module for why the 768-dimension output makes this
mandatory rather than merely tidy. `add()` re-normalizes defensively so a hand-built
index cannot quietly break the 0.65 threshold.

§ 6 requires the index to persist across requests and never to be rebuilt per request.
The committed `data/corpus_index.json` is loaded once at startup (D-005), so a cold
start costs zero embedding API calls.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import faiss
import numpy as np

from config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, get_settings
from middleware import log_event
from services.embeddings import l2_normalize


@dataclass
class SearchHit:
    chunk_id: str
    judgment_id: str
    section: str
    text: str
    similarity: float
    metadata: dict[str, Any]


class VectorStore:
    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        self.dimensions = dimensions
        self.index = faiss.IndexFlatIP(dimensions)
        self.chunks: list[dict[str, Any]] = []

    def __len__(self) -> int:
        return len(self.chunks)

    def add(self, chunks: list[dict[str, Any]], vectors: np.ndarray) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(
                f"{len(chunks)} chunks but {len(vectors)} vectors")
        self.index.add(l2_normalize(np.asarray(vectors, dtype=np.float32)))
        self.chunks.extend(chunks)

    def search(self, query_vector: np.ndarray, top_k: int) -> list[SearchHit]:
        """Top-k by cosine similarity. No threshold applied — that is § 5.2 step 3."""
        if not self.chunks:
            return []

        query = l2_normalize(np.asarray(query_vector, dtype=np.float32)).reshape(1, -1)
        scores, indices = self.index.search(query, min(top_k, len(self.chunks)))

        hits: list[SearchHit] = []
        for score, position in zip(scores[0], indices[0]):
            if position < 0:  # FAISS pads with -1 when fewer than k results exist
                continue
            chunk = self.chunks[int(position)]
            hits.append(SearchHit(
                chunk_id=chunk["chunk_id"],
                judgment_id=chunk["judgment_id"],
                section=chunk["section"],
                text=chunk["text"],
                similarity=float(score),
                metadata=chunk.get("metadata", {}),
            ))
        return hits

    # --- persistence (§ 6, D-005) -------------------------------------------

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        vectors = self.index.reconstruct_n(0, self.index.ntotal)
        payload = {
            "embedding_model": EMBEDDING_MODEL,
            "dimensions": self.dimensions,
            "normalized": True,
            "chunk_count": len(self.chunks),
            "chunks": [
                {**chunk, "embedding": [round(float(v), 7) for v in vector]}
                for chunk, vector in zip(self.chunks, vectors)
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "VectorStore":
        target = path or get_settings().index_path
        payload = json.loads(Path(target).read_text(encoding="utf-8"))

        store = cls(dimensions=payload.get("dimensions", EMBEDDING_DIMENSIONS))
        records = payload["chunks"]
        vectors = np.array([r["embedding"] for r in records], dtype=np.float32)
        chunks = [{k: v for k, v in r.items() if k != "embedding"} for r in records]
        store.add(chunks, vectors)

        log_event(event="index_loaded", path=str(target), chunks=len(store),
                  dimensions=store.dimensions)
        return store


_store: Optional[VectorStore] = None


def get_store() -> VectorStore:
    """Process-wide singleton: the index is loaded once, never per request (§ 6)."""
    global _store
    if _store is None:
        _store = VectorStore.load()
    return _store


def reset_store(store: Optional[VectorStore] = None) -> None:
    """Swap the singleton — used by tests and by admin reindex."""
    global _store
    _store = store
