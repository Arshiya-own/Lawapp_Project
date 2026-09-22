"""Vector store and normalization tests (04_ai_ml_spec.md § 5.2, § 6).

These exist mainly to pin one property: **inner product equals cosine similarity only
on unit vectors**. `gemini-embedding-001` does not normalize its 768-dimension output
(measured norm ≈0.568), so if normalization regresses, FAISS silently starts scoring
something that is not cosine similarity and the binding 0.65 threshold stops meaning
anything. Nothing would crash — retrieval would just quietly get worse.
"""

import json

import numpy as np
import pytest

from config import EMBEDDING_DIMENSIONS, SIMILARITY_THRESHOLD, get_settings
from services.embeddings import l2_normalize
from services.vector_store import VectorStore


def random_vectors(count: int, scale: float = 0.5, seed: int = 0) -> np.ndarray:
    """Vectors with non-unit magnitude, imitating raw 768-dim API output."""
    rng = np.random.default_rng(seed)
    raw = rng.normal(size=(count, EMBEDDING_DIMENSIONS)).astype(np.float32)
    return (raw / np.linalg.norm(raw, axis=1, keepdims=True) * scale).astype(np.float32)


def fake_chunks(count: int) -> list[dict]:
    return [
        {
            "chunk_id": f"j_{i // 6 + 1:04d}_chunk_{i % 6 + 1:03d}",
            "judgment_id": f"j_{i // 6 + 1:04d}",
            "section": "held",
            "text": f"chunk text {i}",
            "token_count": 10,
            "metadata": {"case_name": f"Case {i}", "court_tier": 1,
                         "date": "2020-01-01", "state": None},
        }
        for i in range(count)
    ]


# --- l2_normalize -----------------------------------------------------------


def test_normalizes_rows_to_unit_length():
    normalized = l2_normalize(random_vectors(10, scale=0.42))
    assert np.allclose(np.linalg.norm(normalized, axis=1), 1.0, atol=1e-5)


def test_handles_a_single_1d_vector():
    vector = random_vectors(1, scale=0.3)[0]
    assert vector.ndim == 1
    normalized = l2_normalize(vector)
    assert normalized.ndim == 1
    assert np.isclose(np.linalg.norm(normalized), 1.0, atol=1e-5)


def test_zero_vector_does_not_divide_by_zero():
    result = l2_normalize(np.zeros((2, EMBEDDING_DIMENSIONS), dtype=np.float32))
    assert np.all(np.isfinite(result))
    assert np.allclose(result, 0.0)


def test_normalization_preserves_direction():
    vectors = random_vectors(5, scale=0.6)
    normalized = l2_normalize(vectors)
    for original, unit in zip(vectors, normalized):
        cosine = float(original @ unit / (np.linalg.norm(original) * np.linalg.norm(unit)))
        assert cosine == pytest.approx(1.0, abs=1e-5)


def test_output_is_float32():
    """FAISS requires float32; a float64 array would raise at add() time."""
    assert l2_normalize(random_vectors(3)).dtype == np.float32


# --- the property the threshold depends on ----------------------------------


def test_inner_product_equals_cosine_only_after_normalization():
    # Deliberately correlated, so the cosine is large enough that the comparison is
    # meaningful. Two random 768-dim vectors are near-orthogonal, which would make
    # both quantities ~0 and the test vacuous.
    base = random_vectors(1, scale=1.0, seed=7)[0]
    noise = random_vectors(1, scale=1.0, seed=8)[0]
    a = (base * 0.5).astype(np.float32)
    b = ((base + 0.3 * noise) * 0.6).astype(np.float32)

    true_cosine = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
    raw_inner_product = float(a @ b)
    normalized_inner_product = float(l2_normalize(a) @ l2_normalize(b))

    assert true_cosine > 0.9  # genuinely similar, so the gap below is about scale
    assert normalized_inner_product == pytest.approx(true_cosine, abs=1e-5)

    # Raw inner product is the cosine scaled by both magnitudes (0.5 x ~0.63), so it
    # understates the true similarity by roughly a third.
    assert raw_inner_product == pytest.approx(
        true_cosine * np.linalg.norm(a) * np.linalg.norm(b), rel=1e-4)
    assert raw_inner_product < true_cosine * 0.5


def test_unnormalized_vectors_would_suppress_the_threshold():
    """Why this matters: raw magnitudes push real matches below 0.65."""
    query = l2_normalize(random_vectors(1, seed=1)[0])
    identical = query * 0.568  # the measured gemini-embedding-001 magnitude

    assert float(query @ l2_normalize(identical)) == pytest.approx(1.0, abs=1e-5)
    # The same chunk, un-normalized, scores below the threshold despite being a
    # perfect semantic match.
    assert float(query @ identical) < SIMILARITY_THRESHOLD


# --- VectorStore ------------------------------------------------------------


def test_add_normalizes_defensively():
    store = VectorStore()
    store.add(fake_chunks(6), random_vectors(6, scale=0.4))
    stored = store.index.reconstruct_n(0, store.index.ntotal)
    assert np.allclose(np.linalg.norm(stored, axis=1), 1.0, atol=1e-5)


def test_add_rejects_mismatched_lengths():
    store = VectorStore()
    with pytest.raises(ValueError):
        store.add(fake_chunks(3), random_vectors(2))


def test_search_returns_descending_similarity():
    store = VectorStore()
    store.add(fake_chunks(12), random_vectors(12, seed=3))
    hits = store.search(random_vectors(1, seed=4)[0], top_k=5)
    assert len(hits) == 5
    assert [h.similarity for h in hits] == sorted((h.similarity for h in hits),
                                                  reverse=True)


def test_search_finds_an_exact_match_at_similarity_one():
    vectors = random_vectors(8, seed=5)
    store = VectorStore()
    store.add(fake_chunks(8), vectors)
    hits = store.search(vectors[3], top_k=1)
    assert hits[0].chunk_id == "j_0001_chunk_004"
    assert hits[0].similarity == pytest.approx(1.0, abs=1e-4)


def test_search_caps_at_the_number_of_chunks():
    store = VectorStore()
    store.add(fake_chunks(3), random_vectors(3))
    assert len(store.search(random_vectors(1)[0], top_k=20)) == 3


def test_empty_store_returns_no_hits():
    assert VectorStore().search(random_vectors(1)[0], top_k=5) == []


def test_save_and_load_round_trip(tmp_path):
    original = VectorStore()
    chunks, vectors = fake_chunks(6), random_vectors(6, seed=9)
    original.add(chunks, vectors)

    path = tmp_path / "index.json"
    original.save(path)
    restored = VectorStore.load(path)

    assert len(restored) == 6
    assert [c["chunk_id"] for c in restored.chunks] == [c["chunk_id"] for c in chunks]
    probe = vectors[2]
    assert restored.search(probe, 1)[0].similarity == pytest.approx(1.0, abs=1e-4)


def test_saved_index_does_not_nest_embeddings_in_chunks(tmp_path):
    """Loading must strip `embedding` back out, or it leaks into API responses."""
    store = VectorStore()
    store.add(fake_chunks(2), random_vectors(2))
    path = tmp_path / "index.json"
    store.save(path)
    assert all("embedding" not in c for c in VectorStore.load(path).chunks)


# --- the committed index ----------------------------------------------------


@pytest.mark.skipif(not get_settings().index_path.exists(),
                    reason="corpus_index.json not built yet")
def test_committed_index_has_72_unit_length_vectors():
    payload = json.loads(get_settings().index_path.read_text(encoding="utf-8"))
    assert payload["chunk_count"] == 72
    assert payload["dimensions"] == EMBEDDING_DIMENSIONS
    assert payload["normalized"] is True

    vectors = np.array([c["embedding"] for c in payload["chunks"]], dtype=np.float32)
    assert vectors.shape == (72, EMBEDDING_DIMENSIONS)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-4)
