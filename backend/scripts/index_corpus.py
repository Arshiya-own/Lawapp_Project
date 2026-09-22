"""One-time corpus indexing (01_architecture.md § 8, 04_ai_ml_spec.md § 6).

    python -m scripts.index_corpus --corpus ../data/judgments_corpus.json

Chunks every judgment, embeds each chunk with `RETRIEVAL_DOCUMENT`, and writes
`data/corpus_index.json` in the § 3.3 shape. The output is committed, so deployment
loads precomputed vectors and a cold start costs zero embedding calls (D-005) — which
also satisfies § 6's "do not re-index on every request" more strongly than embedding
at container start would.

Vectors are L2-normalized before they are written. See `services/embeddings.py`.
"""

import argparse
import sys
from pathlib import Path

import numpy as np

from config import EMBEDDING_DIMENSIONS, REPO_ROOT
from services import embeddings
from services.chunker import chunk_corpus, load_corpus
from services.vector_store import VectorStore

BATCH_SIZE = 32  # keeps each embed_content request comfortably small


def build_index(corpus_path: Path, output_path: Path, batch_size: int = BATCH_SIZE) -> int:
    judgments = load_corpus(str(corpus_path))
    chunks = chunk_corpus(judgments)
    print(f"{len(judgments)} judgments -> {len(chunks)} chunks")

    vectors: list[np.ndarray] = []
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        vectors.append(embeddings.embed_documents([c.text for c in batch]))
        print(f"  embedded {min(start + batch_size, len(chunks))}/{len(chunks)}")

    matrix = np.vstack(vectors)

    norms = np.linalg.norm(matrix, axis=1)
    print(f"vector norms: min={norms.min():.6f} max={norms.max():.6f} "
          f"(must be 1.0 — inner product is only cosine on unit vectors)")
    if not np.allclose(norms, 1.0, atol=1e-4):
        raise SystemExit("ERROR: vectors are not unit length; refusing to write index")

    store = VectorStore(dimensions=EMBEDDING_DIMENSIONS)
    store.add([c.to_dict() for c in chunks], matrix)
    store.save(output_path)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"wrote {output_path} ({len(store)} chunks, {size_mb:.1f} MB)")
    return len(store)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Index the judgments corpus.")
    parser.add_argument("--corpus", type=Path,
                        default=REPO_ROOT / "data" / "judgments_corpus.json")
    parser.add_argument("--output", type=Path,
                        default=REPO_ROOT / "data" / "corpus_index.json")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args(argv)

    if not args.corpus.exists():
        print(f"corpus not found: {args.corpus}", file=sys.stderr)
        return 1

    build_index(args.corpus, args.output, args.batch_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
