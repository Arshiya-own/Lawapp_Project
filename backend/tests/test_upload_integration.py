"""Upload integration test (03_backend_spec.md § 11).

Exercises the real HTTP stack: routing, auth, multipart parsing, `pypdf` extraction of
the actual `sample_case_1.pdf`, SQLite persistence, and the response envelope.

**Gemini is mocked, deliberately.** Hitting the live API would make the suite slow,
non-deterministic and quota-consuming, and would fail offline — while testing Google's
model rather than this code. The prompts themselves are asserted separately, so what
the mock replaces is the network call, not the contract.

Embeddings are mocked too, but with a *real* vector taken from the committed index, so
retrieval runs genuine FAISS search and genuine ranking against real data.
"""

import json
import re
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

import db
import main
from security import create_access_token
from services import embeddings, gemini_client
from services.vector_store import get_store

SAMPLES = Path(__file__).resolve().parent.parent.parent / "samples"
SAMPLE_PDF = SAMPLES / "sample_case_1.pdf"

CASE_ID_PATTERN = re.compile(
    r"^case_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

FAKE_METADATA = {
    "parties": "Rahul Bhikulal Kasat vs. The State of Maharashtra",
    "court": "Supreme Court of India",
    "jurisdiction": "Criminal",
    "sections_invoked": ["IPC 120B", "IPC 302", "IEA 65B"],
    "synopsis": "SLP (Criminal) challenging the High Court's dismissal of bail.",
}

FAKE_DIMENSIONS = [
    {"dimension_number": 1, "query": "Section 65B certificate compliance",
     "rationale": "Electronic evidence admissibility is contested."},
    {"dimension_number": 2, "query": "Criminal conspiracy proof standard",
     "rationale": "Conviction rests on IPC 120B."},
    {"dimension_number": 3, "query": "Further investigation under CrPC 173(8)",
     "rationale": "Belated production of certificates is in issue."},
]


def keyshape(value):
    """Field names, nesting and types — not values (see QUESTIONS.md on sample matching)."""
    if isinstance(value, dict):
        return {key: keyshape(item) for key, item in value.items()}
    if isinstance(value, list):
        return [keyshape(value[0])] if value else []
    return type(value).__name__


@pytest.fixture(autouse=True)
def mock_gemini(monkeypatch):
    monkeypatch.setattr(gemini_client, "extract_metadata",
                        lambda _text: dict(FAKE_METADATA))
    monkeypatch.setattr(gemini_client, "generate_dimensions",
                        lambda _metadata: [dict(d) for d in FAKE_DIMENSIONS])

    # A real indexed vector, so search and ranking run on real data and the top hit is
    # a genuine match rather than an arbitrary one.
    store = get_store()
    probe = store.index.reconstruct(0).astype(np.float32)
    monkeypatch.setattr(embeddings, "embed_query", lambda _text: probe)


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def auth(client):
    user = db.upsert_user("integration@example.com", "Integration Test", "")
    return {"Authorization": f"Bearer {create_access_token(user['user_id'])}"}


@pytest.fixture
def pdf_bytes() -> bytes:
    return SAMPLE_PDF.read_bytes()


def upload(client, auth, data: bytes, name="sample_case_1.pdf",
           mime="application/pdf"):
    return client.post("/api/v1/cases/upload", headers=auth,
                       files={"file": (name, data, mime)})


# --- the required case: upload the sample PDF, assert the response shape ----


def test_sample_pdf_uploads_and_returns_201(client, auth, pdf_bytes):
    response = upload(client, auth, pdf_bytes)
    assert response.status_code == 201

    body = response.json()
    assert set(body) == {"case_id", "status", "uploaded_at"}
    assert CASE_ID_PATTERN.match(body["case_id"]), body["case_id"]
    assert TIMESTAMP_PATTERN.match(body["uploaded_at"]), body["uploaded_at"]
    # § 5.2 shows "processing" in the 201 body even though § 8 is synchronous (Q-003).
    assert body["status"] == "processing"


def test_case_detail_matches_the_sample_fixture_structurally(client, auth, pdf_bytes):
    case_id = upload(client, auth, pdf_bytes).json()["case_id"]
    detail = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()

    expected = json.loads(
        (SAMPLES / "sample_case_metadata.json").read_text(encoding="utf-8"))
    assert keyshape(detail) == keyshape(expected)

    assert detail["status"] == "processed"
    assert TIMESTAMP_PATTERN.match(detail["processed_at"])
    assert detail["dimensions"] is None
    assert detail["retrieval"] is None


def test_real_pdf_text_layer_is_extracted(client, auth, pdf_bytes):
    """Guards the OCR path: pypdf must actually read the ReportLab text layer."""
    from services import ocr

    result = ocr.extract_text(pdf_bytes)
    assert result.method == "text_layer"
    assert result.pages_processed == 4
    assert len(result.text) > 200
    assert not ocr.is_failure(result)
    assert "--- Page 1 ---" in result.text


# --- error paths (§ 5.2, § 4) -----------------------------------------------


def test_unauthenticated_upload_is_401(client, pdf_bytes):
    response = client.post("/api/v1/cases/upload",
                           files={"file": ("a.pdf", pdf_bytes, "application/pdf")})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_non_pdf_is_415(client, auth):
    response = upload(client, auth, b"not a pdf", name="notes.txt", mime="text/plain")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"
    assert response.json()["error"]["message"] == "Only PDF files are accepted."


def test_oversized_file_is_413(client, auth):
    oversized = b"%PDF-1.4\n" + b"\0" * (21 * 1024 * 1024)
    response = upload(client, auth, oversized, name="big.pdf")
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
    assert response.json()["error"]["message"] == "File too large. Maximum 20 MB."


def test_corrupted_pdf_is_422_ocr_failed(client, auth):
    """§ 4 lists 'corrupted' under 422 — a pypdf crash must not surface as 500."""
    response = upload(client, auth, b"%PDF-1.4\ntruncated", name="broken.pdf")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ocr_failed"


def test_failed_upload_persists_no_case(client, auth):
    """Q-001: a case that fails to process is not stored."""
    before = len(client.get("/api/v1/cases", headers=auth).json()["cases"])
    upload(client, auth, b"%PDF-1.4\ntruncated", name="broken.pdf")
    after = len(client.get("/api/v1/cases", headers=auth).json()["cases"])
    assert after == before


def test_every_error_uses_the_envelope(client, auth):
    response = upload(client, auth, b"x", name="a.txt", mime="text/plain")
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}


# --- ownership (§ 11) -------------------------------------------------------


def test_another_users_case_is_404_not_403(client, auth, pdf_bytes):
    case_id = upload(client, auth, pdf_bytes).json()["case_id"]

    other = db.upsert_user("intruder@example.com", "Intruder", "")
    other_auth = {"Authorization": f"Bearer {create_access_token(other['user_id'])}"}

    response = client.get(f"/api/v1/cases/{case_id}", headers=other_auth)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_case_list_is_scoped_to_the_owner(client, auth, pdf_bytes):
    upload(client, auth, pdf_bytes)
    other = db.upsert_user("stranger@example.com", "Stranger", "")
    other_auth = {"Authorization": f"Bearer {create_access_token(other['user_id'])}"}

    assert client.get("/api/v1/cases", headers=other_auth).json()["cases"] == []
    assert len(client.get("/api/v1/cases", headers=auth).json()["cases"]) >= 1


def test_unknown_case_is_404(client, auth):
    response = client.get("/api/v1/cases/case_does-not-exist", headers=auth)
    assert response.status_code == 404


# --- the rest of the pipeline ----------------------------------------------


def test_retrieve_before_dimensions_is_422_dimensions_missing(client, auth, pdf_bytes):
    case_id = upload(client, auth, pdf_bytes).json()["case_id"]
    response = client.post(f"/api/v1/cases/{case_id}/retrieve", headers=auth)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "dimensions_missing"


def test_dimensions_then_retrieve(client, auth, pdf_bytes):
    case_id = upload(client, auth, pdf_bytes).json()["case_id"]

    dimensions = client.post(f"/api/v1/cases/{case_id}/dimensions", headers=auth)
    assert dimensions.status_code == 200
    body = dimensions.json()
    assert len(body["dimensions"]) == 3
    assert [d["dimension_number"] for d in body["dimensions"]] == [1, 2, 3]
    assert TIMESTAMP_PATTERN.match(body["generated_at"])

    retrieval = client.post(f"/api/v1/cases/{case_id}/retrieve", headers=auth)
    assert retrieval.status_code == 200
    results = retrieval.json()["results"]
    assert len(results) == 3

    expected = json.loads(
        (SAMPLES / "sample_retrieval_response.json").read_text(encoding="utf-8"))
    assert keyshape(retrieval.json()) == keyshape(expected)

    for result in results:
        assert len(result["judgments"]) <= 5  # § 12: max 5 per dimension
        for judgment in result["judgments"]:
            assert judgment["court_tier"] != 4  # § 5.3: District Courts excluded
            assert round(judgment["similarity_score"], 3) == judgment["similarity_score"]


def test_dimensions_are_stored_on_the_case(client, auth, pdf_bytes):
    case_id = upload(client, auth, pdf_bytes).json()["case_id"]
    client.post(f"/api/v1/cases/{case_id}/dimensions", headers=auth)

    detail = client.get(f"/api/v1/cases/{case_id}", headers=auth).json()
    assert detail["dimensions"] is not None
    assert len(detail["dimensions"]) == 3


# --- eval endpoint ----------------------------------------------------------


def test_eval_retrieve_requires_the_token(client):
    response = client.post("/api/v1/eval/retrieve", json={"query": "x", "top_k": 10})
    assert response.status_code == 401


def test_eval_retrieve_rejects_a_wrong_token(client):
    response = client.post("/api/v1/eval/retrieve",
                           headers={"Authorization": "Bearer wrong-token"},
                           json={"query": "x", "top_k": 10})
    assert response.status_code == 401


def test_eval_retrieve_returns_the_harness_contract(client):
    from config import get_settings

    response = client.post(
        "/api/v1/eval/retrieve",
        headers={"Authorization": f"Bearer {get_settings().eval_token}"},
        json={"query": "Section 65B certificate", "top_k": 10},
    )
    assert response.status_code == 200

    judgments = response.json()["judgments"]
    assert 0 < len(judgments) <= 10
    for judgment in judgments:
        assert set(judgment) == {"judgment_id", "similarity_score", "court_tier", "date"}

    # The harness scores distinct judgment_ids, so duplicates would waste top-k slots.
    ids = [j["judgment_id"] for j in judgments]
    assert len(ids) == len(set(ids))

    scores = [j["similarity_score"] for j in judgments]
    assert scores == sorted(scores, reverse=True)


def test_health_is_public(client):
    assert client.get("/api/v1/health").json() == {"status": "ok"}
