# Mini-JuriNex — 4-Day Build Plan (free-tier stack)

> **Status:** plan agreed, implementation **not started**. Nothing under `backend/` or `frontend/`
> exists yet. Stack forks are settled (see *Free-tier stack*). Day 1 begins with `git init`, the repo
> scaffold and the Gemini + OAuth credential walkthrough.
>
> **Blocked on manual setup:** Gemini API key, Google OAuth client, Render + Vercel + GitHub
> accounts, Python 3.11. See the handover checklist at the end of this file.

## Context

This is a hiring take-home for JuriNex, delivered as a spec package in `auxillary/Lawapp_Project/`.
The exercise is deliberately **not** a design task: four specs (~1,270 lines) fix the architecture,
API contract, prompts, chunking rules and ranking logic, and grading rewards *fidelity*, not
invention. Scoring is out of 100, with 50 of those points on spec adherence + sample I/O, 15 on
retrieval metrics, and 35 on deviation/production/code/docs quality.

The recruiter email adds three constraints beyond the original brief:

- Build on a **free alternative** stack (the specs mandate paid GCP: Cloud Run, GCS, Vertex, Document AI)
- **4 days**, then share the repository
- A **recorded walkthrough** plus a **30-minute interview**

Decisions already made: SQLite + local disk on Render, starting from Day 1, Google credentials need a
click-by-click walkthrough (none set up yet), and `backend/` and `frontend/` sit as **siblings of
`auxillary/`** with the provided package kept in the tree.

### Investigation findings that shape the build

1. **`text-embedding-004` was shut down on 2026-01-14.** The AI/ML spec binds it in §2, §5.1, §12
   and the checklist has row M-01 for it. It cannot be implemented. Replacement:
   `gemini-embedding-001` with `output_dimensionality=768` — the only current model that keeps both
   the 768 dimensions (§2) *and* parameter-based `RETRIEVAL_QUERY`/`RETRIEVAL_DOCUMENT` task types
   (§5.1). `gemini-embedding-2` drops task-type parameters, which would cost a second deviation.

2. **No corpus section exceeds 400 tokens** (longest ~227; 60 of 72 sections are under the 150-token
   minimum). Per chunking rule 3, **every section emits exactly one chunk** → 72 chunks total,
   indices `_chunk_001`..`_chunk_006` per judgment. The 80-token overlap, the ±30-token sentence
   boundary preference and the 500-token cap **never execute on this corpus**. They must still be
   implemented correctly and proven by unit tests on synthetic input (checklist M-04/05/06, B-20).

3. **The sample `chunk_id`s are not reproducible.** Mapping index→section in the §3.1 order
   (headnote, facts, issues, held, reasoning, order), only 1 of 4 sample chunk_ids matches where its
   snippet text actually lives in the corpus: `j_0007_chunk_004` claims *held* but its text is in
   *reasoning*; `j_0011_chunk_002` claims *facts*, text is in *held*; `j_0004_chunk_006` claims
   *order*, text is in *reasoning*. Only `j_0009_chunk_005` is consistent. So the samples are
   **illustrative fixtures**; sample grading must be structural (field names, nesting, types), which
   matches the brief's own wording. Do not burn time chasing byte-exact snippet equality.

4. **Both sample PDFs are ReportLab text-layer PDFs** (4 pages, ~6.5K chars each) — comfortably over
   the 200-char OCR-failure threshold. `pypdf` extracts them directly. Rasterising them through
   pdf2image + tesseract at 200 DPI risks OOM on Render's 512 MB free tier, so the pipeline goes
   **text-layer first, pytesseract fallback**. The fallback is what keeps it correct if a scanned
   variant is substituted (the package's own PDF-generation notes keep one in reserve).

5. **Corpus is clean** — valid UTF-8, 45 proper em-dashes, tiers only {1,2,3}, `state` present
   (Maharashtra / Delhi / null). No encoding bug to report.

### One thing to be aware of

`auxillary/Lawapp_Project/README.md` is the **hiring manager's** copy. It lists the 7 deliberately
planted comprehension gates and the intended ambiguity, and `templates/QUESTIONS.md` ships the model
answer as its worked example. Since `auxillary/` stays in the tree, that file ships with the repo —
which is fine (they sent it), but it makes two things worth doing:

- Every finding in `QUESTIONS.md` is one verified independently against the corpus, samples and live
  Google docs. Findings 1–4 above are **not** on the manager's gate list, which is the demonstrable
  part. The planted gates get implemented in code rather than recited in prose.
- "How did you find these?" is a likely interview question. The honest answer is easy to give.

If you would rather not ship the manager's notes, adding `auxillary/` to `.gitignore` is a one-line
change either way.

---

## Free-tier stack

| Spec requires | Build uses | Deviation? |
|---|---|---|
| `gemini-2.5-flash` @ temp 0.2 | same, free tier | none |
| `text-embedding-004` (768d) | `gemini-embedding-001` @ 768d | **D-003** (model retired) |
| Google OAuth 2.0 + PKCE | same, free, no billing | none |
| OCR: Document AI *or* pytesseract | pypdf text layer → pytesseract fallback | **D-006** (fast path) |
| Vector store: Vertex/Chroma/pgvector/FAISS | FAISS in-memory | none (§4.5 permits) |
| Metadata store: dict *or* Firestore | SQLite | none (§5 "implementer's choice") |
| GCS + 15-min signed URLs | local disk, authed streaming endpoint | **D-001**, **D-004** |
| Cloud Run (both halves) | Render Docker (api) + Vercel (web) | **D-002** |
| Index at container start | `index_corpus.py` run offline, vectors committed | **D-005** |

Six deviations, all small; **none** touch the API contract, chunking rules or ranking logic, which is
where the 50 points of adherence + sample-I/O actually sit.

Rate-limit note: Flash free tier is ~10 RPM / 1,500 RPD. Committing the 72 precomputed vectors means
a cold start costs **zero** API calls — which also satisfies §6's "index is not rebuilt per request"
better than re-embedding at boot would.

---

## Repository layout

Git repo rooted at `lawapp/` (not currently a repo — needs `git init`). `backend/` and
`frontend/` are siblings of `auxillary/`:

```
lawapp/
├── auxillary/                       <- provided package, kept as delivered
│   └── Lawapp_Project/{brief,specs,samples,data,starter_repo,templates}
├── plan_to_do/
│   └── BUILD_PLAN.md                <- this file
├── CLAUDE.md                        <- project memory (binding numbers, contract, findings)
├── backend/
│   ├── Dockerfile                   <- python:3.11-slim + tesseract-ocr + poppler-utils
│   ├── main.py  requirements.txt
│   ├── config.py                    <- pydantic-settings, fails fast on missing secrets
│   ├── db.py                        <- SQLite schema + connection
│   ├── middleware.py                <- request logging, request_id, error envelope
│   ├── routers/    auth.py  cases.py  evaluation.py  admin.py
│   ├── services/   ocr.py  gemini_client.py  chunker.py  vector_store.py
│   │                ranker.py  storage.py
│   ├── models/     schemas.py       <- Pydantic v2, mirrors backend spec §6 exactly
│   ├── scripts/    index_corpus.py
│   └── tests/      test_chunker.py  test_ranker.py  test_upload_integration.py
├── frontend/                        <- exact tree from frontend spec §3
│   ├── package.json  tsconfig.json  vite.config.ts  tailwind.config.js  index.html
│   └── src/{main.tsx,App.tsx,api,auth,pages,components,types}
├── data/        judgments_corpus.json  eval_set.json  corpus_index.json (committed vectors)
├── samples/     copied from the package, per starter_repo/README.md
├── eval/        eval.py             <- LOCKED, copied byte-identical
├── README.md  DEVIATIONS.md  QUESTIONS.md  SPEC_COMPLIANCE.md  eval_results.json
└── .env.example  .gitignore
```

`data/`, `samples/` and `eval/` are copied to the root rather than referenced inside `auxillary/`,
because `starter_repo/README.md` specifies that structure and the locked `eval.py` resolves its
eval set as `../data/eval_set.json`. `.gitignore` covers `.env`, `*.db`, `data/uploads/`,
`__pycache__/`, `node_modules/`, `dist/`.

---

## Day 1 — credentials, scaffold, upload pipeline

1. **Credential walkthrough** written into `README.md` as a numbered setup section.
2. `git init`, repo scaffold, `.gitignore`, copy `data/`, `samples/`, `eval/eval.py` verbatim from
   the package.
3. `models/schemas.py` first — transcribe backend spec §6 literally. This is the contract everything
   else is checked against. Includes a `utc_z()` serializer producing `%Y-%m-%dT%H:%M:%SZ`
   (gate 1: no `+00:00`, no milliseconds).
4. `db.py` + SQLite tables `users`, `cases`. IDs via `f"user_{uuid4()}"` / `f"case_{uuid4()}"`
   (gate 3: lowercase, hyphenated).
5. `middleware.py`: request logging per architecture §10, plus a global handler emitting the
   `{"error": {"code","message","details"}}` envelope for every status in backend spec §4.
6. OAuth: authorize / callback / me / logout, Authorization-Bearer JWT, 60-min expiry.
7. `services/ocr.py`: pypdf per page → page-marker join → pytesseract fallback →
   **422 `ocr_failed`** if under 200 chars (gate 2).
8. `services/gemini_client.py` + metadata extraction using the §4.1 prompt verbatim, temp 0.2,
   fence-stripping, one retry then 502.
9. `POST /cases/upload` (413 / 415 / 422 paths), `GET /cases/{id}` (404 for other users' cases, not
   403), `GET /cases`.

**Checkpoint:** `sample_case_1.pdf` uploads and the response structurally matches
`samples/sample_case_metadata.json`.

## Day 2 — retrieval

1. `services/chunker.py` — all seven rules from §3.2, tiktoken `cl100k_base`, per-section
   independence, **80-token** overlap, ±30-token sentence-boundary preference, 150/400/500 bounds,
   `{judgment_id}_chunk_{NNN}` ids in §3.1 section order.
2. `tests/test_chunker.py` — must use **synthetic long sections** to exercise overlap and the 500
   cap, since the real corpus never triggers them (finding 2). Also assert the real corpus yields
   exactly 72 single-section chunks.
3. `scripts/index_corpus.py` — chunk, embed with `RETRIEVAL_DOCUMENT`, write `data/corpus_index.json`
   with the §3.3 chunk-metadata shape. Run once; commit the output.
4. `services/vector_store.py` — FAISS loaded from the committed index at startup; cosine similarity.
5. Dimension generation with the §4.2 prompt verbatim; **exactly 3**, re-prompt once, then error —
   never silently fall back to 2 or 4 (gate 6).
6. `services/ranker.py` — tier ascending → **date descending** (gate 7) → similarity descending;
   exclude tier 4; recompute tier 2/3 from the case's state rather than trusting the corpus field.
7. `tests/test_ranker.py` — covers the tie-breaker chain and tier-4 exclusion (tier 4 is absent from
   the corpus, so this needs synthetic rows too).
8. `POST /cases/{id}/dimensions`, `POST /cases/{id}/retrieve`, `POST /eval/retrieve` (static
   `EVAL_TOKEN`).

**Checkpoint:** retrieval response structurally matches `samples/sample_retrieval_response.json`;
`eval.py` runs green against localhost.

## Day 3 — frontend, deploy

1. Frontend at the exact §3 tree: 3 routes, `AuthContext`, React Query, Tailwind. Tokens in memory
   only — never `localStorage` (F-17).
2. All five components per §6. Empty state verbatim `"No precedents found for this dimension."`
   (gate 4). Similarity to 3 decimals. Modal closes on ESC / backdrop / button and traps focus.
3. Every data-fetching component handles loading / empty / error / success explicitly (§9).
4. `backend/Dockerfile` (python:3.11-slim + tesseract-ocr + poppler-utils), deploy to Render as a
   **Docker** service — Render's native Python runtime cannot install those binaries.
5. Deploy frontend to Vercel; set `VITE_API_BASE_URL`; lock CORS to the Vercel origin; add the Render
   callback URL to the OAuth client.
6. `tests/test_upload_integration.py` against the sample PDF.

**Checkpoint:** public demo URL, full upload → dimensions → retrieve flow working.

## Day 4 — eval, docs, video, interview prep

1. Run `eval.py` against the deployed URL → `eval_results.json`. Report real numbers, whatever they
   are; fabrication is an explicit disqualifier.
2. **Calibration check:** log the similarity distribution for the 5 eval queries. If few clear 0.65,
   that is a finding for `QUESTIONS.md`, not a reason to quietly move the threshold.
3. `DEVIATIONS.md` — the six above, each with spec ref / specified / implemented / reason / tradeoff /
   effort-to-comply.
4. `QUESTIONS.md` — the retired embedding model; the unreachable chunking branches; the
   non-reproducible sample chunk_ids; whether the 0.65 threshold applies to `/eval/retrieve` (argued
   **no**: the starter README calls it "the raw retriever... in isolation from the ranking logic", and
   the threshold is part of §5.2's filter stage); the fewer-than-5-pass-threshold ambiguity; corpus
   `court_tier` baked for a Maharashtra-origin case; tier 4 untestable; sample dimension 3 shown empty
   though `eval_003` says `j_0001` is on point.
5. `SPEC_COMPLIANCE.md` — all 77 rows, honestly marked.
6. `README.md` — setup, credential walkthrough, architecture diagram, how to run eval.
7. Video script (~5 min: happy path, then one DEVIATIONS entry) and interview prep notes covering the
   chunking rules, the ranking tie-breaker chain, why the embedding model was substituted, and how
   the spec findings were discovered. **Claude writes the script; you record** — video is manual.

---

## Verification

- `pytest` from `backend/` — chunker, ranker, upload integration all green.
- Structural diff: upload `sample_case_1.pdf`, compare each stage against the four files in
  `samples/` on **field names, nesting and types** (not snippet text — finding 3).
- Contract spot-checks: `case_` + lowercase hyphenated UUIDv4; every timestamp ending `Z` with no
  milliseconds; OCR failure on a garbage PDF returning 422 `ocr_failed`; another user's case
  returning 404; a 25 MB file returning 413; a `.txt` returning 415.
- `python eval.py --api-base-url <render>/api/v1 --auth-token <EVAL_TOKEN> --eval-set
  ../data/eval_set.json --output ../eval_results.json` — runs unmodified.
- Frontend: force each of loading / empty / error / success; confirm the empty string is byte-exact;
  keyboard-only pass through the modal.
- Secret scan before pushing: no key, token or `.env` committed anywhere in history.

---

## Manual setup checklist (blocks Day 1)

These cannot be automated — they need a human in a browser.

| # | Task | Where | Notes |
|---|---|---|---|
| 1 | Gemini API key | aistudio.google.com/apikey | Free, no card. Paste into `.env` as `GEMINI_API_KEY` |
| 2 | OAuth 2.0 Web client | console.cloud.google.com | Free, no billing. Client ID + secret |
| 3 | OAuth consent screen | same | External, Testing mode; add your own email as a test user |
| 4 | Redirect URIs | same | `http://localhost:8000/api/v1/auth/google/callback` now; Render URL on Day 3 |
| 5 | Python 3.11 | python.org | Local machine has 3.14.6; spec binds 3.11 |
| 6 | Tesseract + Poppler | local install | Only for local OCR fallback testing; Docker handles production |
| 7 | GitHub account + empty repo | github.com | For the submission link |
| 8 | Render account | render.com | Free tier, no card. Docker service |
| 9 | Vercel account | vercel.com | Free tier, no card. Frontend |
| 10 | Screen recorder | Loom / OBS | For the ~5-min walkthrough on Day 4 |
