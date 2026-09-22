# SPEC COMPLIANCE CHECKLIST

This is an honest checklist of what you built vs. what you skipped. Scored under "Documentation quality" (7 pts) and factored into "Specification adherence" (30 pts).

Fill in each row:
- ✅ = Done per spec
- ⚠️ = Done with a deviation (must have a D-NNN entry in `DEVIATIONS.md`)
- ❌ = Not done (state why in the Notes column — time, difficulty, etc.)

---

**Nothing is skipped.** All 77 items are implemented; six are marked ⚠️ because they
were implemented differently from the spec, each with a `D-NNN` entry.

Four of the six come from one constraint — the engagement required a free stack while the
specs assume a billing-enabled GCP project (A-04, A-10, and their AI/ML counterparts).
The other two are forced by upstream changes since the specs were written: both
`text-embedding-004` and `gemini-2.5-flash` are now uncallable and were replaced.

No deviation touches the API contract, the chunking rules, or the ranking logic.

---

## 01 — Architecture (`01_architecture.md`)

| ID | Requirement | Status | Notes |
|---|---|---|---|
| A-01 | React 18 + TypeScript + Vite + Tailwind frontend | ✅ | React pinned to 18.3.1 — Vite scaffolds 19 by default. `strict: true` set explicitly in `tsconfig.app.json`. Tailwind v3.4. |
| A-02 | FastAPI backend on Python 3.11 | ✅ | Image is `python:3.11-slim`. |
| A-03 | Google OAuth 2.0 with PKCE | ✅ | S256 challenge. Verifier stored server-side in `oauth_states`, single-use — not round-tripped through the browser in `state`, which would let anyone intercepting the code also read the verifier. |
| A-04 | GCS for raw PDF storage with signed URLs | ⚠️ | **D-001, D-004** — local disk, same object-key layout; authenticated streaming instead of signed URLs. |
| A-05 | Vector store (one of: Vertex / Chroma / pgvector / FAISS) | ✅ | **FAISS** `IndexFlatIP`, 72 chunks. Permitted by § 4.5. |
| A-06 | `text-embedding-004` for embeddings | ⚠️ | **D-003** — shut down 2026-01-14, returns 404. Replaced with `gemini-embedding-001` @ 768d, same task types. |
| A-07 | `gemini-2.5-flash` for generation | ⚠️ | **D-008** — 404 "no longer available to new users". Replaced with `gemini-3.6-flash`, temperature 0.2 preserved. |
| A-08 | Timestamps in ISO 8601 UTC with `Z` suffix | ✅ | Enforced at the model boundary via `UtcZ` / `strftime`, so no endpoint can emit `+00:00` individually. |
| A-09 | UUIDv4 IDs with per-entity prefixes | ✅ | `case_<uuid4>` / `user_<uuid4>`, lowercase and hyphenated. Asserted by regex in tests. |
| A-10 | Cloud Run deployment (backend) | ⚠️ | **D-002** — Render Docker web service. Docker specifically, since native runtimes cannot install tesseract/poppler. |
| A-11 | Secrets via env vars, nothing committed | ✅ | `.env` gitignored and absent from all history; `render.yaml` marks every secret `sync: false`. |
| A-12 | Request logging with method, path, status, latency, user_id | ✅ | JSON lines, plus `request_id`; Gemini calls log model/token estimate/latency and OCR logs duration/pages (§ 10). |
| A-13 | CORS restricted to frontend origin | ✅ | Single origin from `FRONTEND_BASE_URL`, no wildcard. |
| A-14 | File upload limit 20 MB, PDF only | ✅ | Enforced both client-side and server-side. |
| A-15 | 404 (not 403) when user accesses another user's case | ✅ | `user_id` is part of the SQL lookup rather than a separate check, so it cannot be forgotten by a caller. |

## 02 — Frontend (`02_frontend_spec.md`)

| ID | Requirement | Status | Notes |
|---|---|---|---|
| F-01 | Routes: `/login`, `/`, `/cases/:caseId` | ✅ | Exactly three; unknown paths redirect to `/`. |
| F-02 | Login page with Google sign-in button | ✅ | idle / authenticating / error states. Failure text verbatim. |
| F-03 | Upload page with drop zone, 20 MB / PDF validation | ✅ | Validated client-side before the request; both messages verbatim. |
| F-04 | Past cases list on Upload page | ✅ | Most recent first (backend orders by `uploaded_at DESC`). Empty text verbatim. |
| F-05 | Results page with CaseMetadataCard | ✅ | Synopsis clamps to 3 lines with a Show more / Show less expander. |
| F-06 | DimensionCard — 3 cards with query, rationale, ranked judgments | ✅ | |
| F-07 | JudgmentItem with citation, court, date, similarity pill | ✅ | 140-character snippet preview per § 6.4. |
| F-08 | JudgmentSnippetModal with ESC/backdrop/close button | ✅ | All three close paths, plus a focus trap. Full-screen under `sm`. |
| F-09 | All four states for every data-fetching component | ✅ | loading / empty / error / success handled explicitly; dimension cards render placeholders while generating rather than showing a blank screen. |
| F-10 | Empty state text verbatim | ✅ | `EMPTY_DIMENSION_TEXT` constant, asserted byte-exact. |
| F-11 | Similarity score displayed to 3 decimal places | ✅ | `toFixed(3)` in both the item and the modal. |
| F-12 | Auth redirect to `/login` on 401 | ✅ | A 401 from any endpoint clears the session through a handler on the api client; `returnTo` is preserved. |
| F-13 | Header with logo, user email, sign-out | ✅ | 64px, sticky. |
| F-14 | Responsive layout (mobile single-column, desktop max 1024 px) | ✅ | Tailwind default breakpoints; `max-w-content` = 1024px. |
| F-15 | WCAG AA color contrast; keyboard navigation | ✅ | Focus rings deliberately preserved (`:focus-visible`, never `outline: none`); modal traps focus; all controls are real `button`/`input` elements with labels. Contrast uses the Tailwind slate scale at ratios that meet AA (slate-500 on white ≈ 4.76:1) — reasoned from the palette, not verified with an automated auditor. |
| F-16 | No API keys in frontend code | ✅ | Gemini is called only from the backend. |
| F-17 | No auth tokens in localStorage | ✅ | Token lives in React state + a module variable. The callback's `?token=` is stripped via `history.replaceState` so it does not persist in the URL or browser history. |

## 03 — Backend (`03_backend_spec.md`)

| ID | Requirement | Status | Notes |
|---|---|---|---|
| B-01 | Base path `/api/v1` | ✅ | |
| B-02 | `GET /auth/google/authorize` | ✅ | Returns JSON `authorize_url`; accepts `return_to`. |
| B-03 | `GET /auth/google/callback` | ✅ | Backend performs the code exchange — Google's Web client type requires `client_secret` even under PKCE, so doing it in the browser would leak it. |
| B-04 | `GET /auth/me` | ✅ | |
| B-05 | `POST /auth/logout` | ✅ | Stateless; documented in README. |
| B-06 | `POST /cases/upload` with multipart | ✅ | 201 with `status: "processing"` per the § 5.2 example (see Q-003). |
| B-07 | `GET /cases/{case_id}` | ✅ | Structurally matches `sample_case_metadata.json`. |
| B-08 | `GET /cases` (list) | ✅ | Owner-scoped, `uploaded_at` descending. |
| B-09 | `POST /cases/{case_id}/dimensions` | ✅ | Idempotent; regenerates and overwrites. |
| B-10 | `POST /cases/{case_id}/retrieve` | ✅ | 422 `dimensions_missing` if called first. Matches `sample_retrieval_response.json`. |
| B-11 | `POST /eval/retrieve` (required by eval.py) | ✅ | Static `EVAL_TOKEN` via constant-time compare. No threshold, no reranking (Q-005). |
| B-12 | Case IDs prefixed `case_` + UUIDv4 | ✅ | |
| B-13 | Error envelope format | ✅ | Registered globally, so even an unrouted 404 uses it rather than FastAPI's `{"detail": ...}`. `details` always present, `{}` when empty (Q-002). |
| B-14 | OCR failure returns HTTP 422 with code `ocr_failed` | ✅ | Includes corrupted PDFs: `pypdf` parse errors degrade to "no text" rather than escaping as a 500. |
| B-15 | 413 for file > 20 MB | ✅ | |
| B-16 | 415 for non-PDF | ✅ | |
| B-17 | Pydantic v2 validation | ✅ | 2.13.5. Similarity rounding and timestamp formatting are enforced in the models. |
| B-18 | CORS with methods `GET, POST, OPTIONS` | ✅ | |
| B-19 | At least one integration test covering upload → metadata | ✅ | `tests/test_upload_integration.py` — 19 tests against the real `sample_case_1.pdf`, real pypdf, real SQLite. Gemini is mocked so the suite is deterministic and offline-capable. |
| B-20 | At least one unit test for chunking | ✅ | `tests/test_chunker.py` — 21 tests. |
| B-21 | At least one unit test for ranker | ✅ | `tests/test_ranker.py` — 34 tests. |

## 04 — AI/ML (`04_ai_ml_spec.md`)

| ID | Requirement | Status | Notes |
|---|---|---|---|
| M-01 | Embedding model: `text-embedding-004` (768d) | ⚠️ | **D-003** — model retired. `gemini-embedding-001` @ `output_dimensionality=768`. 768 dimensions preserved. |
| M-02 | Generation model: `gemini-2.5-flash` at temperature 0.2 | ⚠️ | **D-008** — model 404s for new keys. `gemini-3.6-flash`; **temperature 0.2 verified still accepted**, so that half of the requirement is met exactly. |
| M-03 | Tokenizer: tiktoken `cl100k_base` | ✅ | Used for every token count in chunking. |
| M-04 | Target chunk size 400 tokens, min 150, max 500 | ✅ | Unreachable on the real corpus (longest section is 171 tokens); tested with synthetic sections. |
| M-05 | Chunk overlap exactly 80 tokens | ✅ | Plus a test asserting it is *not* 80 characters and *not* 80 words. |
| M-06 | Sentence-boundary preference within ±30 tokens of target | ✅ | Nearest boundary wins; falls back to the target when none exists. Both paths tested. |
| M-07 | No overlap across section boundaries | ✅ | Tested with two sections holding identical text, so a leak would show up as a false match. |
| M-08 | Chunk IDs: `{judgment_id}_chunk_NNN`, 3-digit zero-padded | ✅ | Monotonic per judgment across sections; `001`–`006` on the real corpus. |
| M-09 | Chunk metadata includes court, court_tier, date, jurisdiction, state | ✅ | Plus citation and case_name, per § 3.3. |
| M-10 | Metadata extraction prompt per § 4.1 | ✅ | Verbatim, including doubled braces. Input truncated to 12,000 characters. |
| M-11 | Dimension generation prompt per § 4.2, exactly 3 dimensions | ✅ | Verbatim, including the `//` comment inside its JSON block. |
| M-12 | Re-prompt once on malformed dimension output | ✅ | Wrong count discards the whole response and re-prompts once, then 502 — never trimmed to 3 or padded. |
| M-13 | Query embedding with task type `RETRIEVAL_QUERY` | ✅ | |
| M-14 | Document embedding with task type `RETRIEVAL_DOCUMENT` | ✅ | |
| M-15 | Over-retrieval top-20 before filtering | ✅ | |
| M-16 | Similarity threshold 0.65 | ✅ | Meaningful only because vectors are L2-normalized — `gemini-embedding-001` returns non-unit vectors at 768d (measured norm ≈0.568), and FAISS inner product equals cosine only on unit vectors. See D-003. |
| M-17 | Collapse chunks to judgments (keep highest-similarity chunk) | ✅ | |
| M-18 | Rank by court_tier ascending | ✅ | Tier is **recomputed** from the uploaded case's state, not read from the corpus, since "same-state HC" is a property of the query. |
| M-19 | Tie-breaker 1: date descending | ✅ | Three dedicated tests, including one asserting the order is not ascending. |
| M-20 | Tie-breaker 2: similarity_score descending | ✅ | |
| M-21 | Exclude court_tier 4 (District Court) entirely | ✅ | Absent from the corpus, so tested with synthetic rows — including one scoring 0.99 that must still be dropped. |
| M-22 | Top 5 judgments per dimension | ✅ | |
| M-23 | Similarity rounded to 3 decimals in responses | ✅ | Enforced by a Pydantic field validator, so it cannot be missed per-endpoint. |
| M-24 | Snippet truncation at 400 chars with sentence-boundary preference | ✅ | Boundary within the last 50 characters, else hard-truncate plus ellipsis. |

---

## Summary

- **Total items:** 77
- **Done (✅):** 71
- **Deviated (⚠️):** 6 — A-04, A-06, A-07, A-10, M-01, M-02
- **Skipped (❌):** 0

Nothing foundational is missing: the upload → OCR → metadata → dimensions → retrieval →
ranking pipeline is complete end to end, and `eval.py` runs unmodified against it.

The six deviations reduce to three underlying causes:

1. **No billing-enabled GCP project** (A-04, A-10) — local disk replaces GCS, Render
   replaces Cloud Run. The functional consequence worth knowing is that Render's free tier
   has an ephemeral filesystem, so uploaded PDFs and the SQLite database do not survive a
   restart or spin-down (D-001). The corpus index is unaffected; it ships inside the image.
2. **`text-embedding-004` was shut down** (A-06, M-01) — no implementation is possible.
3. **`gemini-2.5-flash` now 404s for new API keys** (A-07, M-02) — the replacement is the
   one Google's own error message names.

Tests: **90 passing** (21 chunker, 16 vector store, 34 ranker, 19 upload integration).
