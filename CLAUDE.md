# CLAUDE.md — Mini-JuriNex

## What this project is

A hiring take-home for JuriNex: a web app that helps an Indian lawyer find relevant precedents.
Upload a case PDF → OCR → Gemini extracts metadatsa → Gemini generates exactly 3 "dimensional
queries" → each is embedded and searched against a 12-judgment corpus → results reranked by court
hierarchy.

**This is a specification-fidelity exercise, not a design task.** The specs in
`auxillary/Lawapp_Project/specs/` have already made every structural decision. The rubric rewards
precise translation of written requirements into working software.

Three rules that override normal engineering instincts here:

1. **Follow the specs literally.** If a spec says X and Y is better, implement X. Note Y in
   `DEVIATIONS.md` as a future proposal.
2. **Do not scope-creep.** Features not in the spec are a *negative* signal. Out-of-scope list is
   `01_architecture.md` §12.
3. **Never deviate silently.** Every deviation → `DEVIATIONS.md`. Every ambiguity → `QUESTIONS.md`
   with the interpretation chosen and why.

Full build plan: `plan_to_do/BUILD_PLAN.md`.

## Working convention — the `concept/` folder

**Every question the user asks, and every concept they ask to have explained, gets written to
`concept/` as a markdown note — not just answered in chat.**

This is deliberate: there is a **30-minute interview** on this project at the end, so `concept/`
accumulates into a revision folder. An answer that exists only in terminal scrollback is lost by
then.

Rules:

- One concept per file, named as a kebab-case slug: `concept/cosine-similarity.md`,
  `concept/why-80-token-overlap.md`, `concept/court-tier-ranking.md`.
- Write the note **as well as** answering in chat — the chat reply can be short, the note is the
  durable artifact.
- Anchor each note to this project, not generic theory: say where the concept shows up in the specs
  or the code, and cite the file. A note on chunking should reference
  `04_ai_ml_spec.md` §3.2 and `backend/services/chunker.py`.
- If a question revisits an existing note, **update that file** rather than creating a near-duplicate.
- Include the likely interview follow-up and its answer where one is obvious. That is the point of
  the folder.

## Binding numbers — do not drift

These are the easiest things to get silently wrong and they are graded directly.

| Item | Value |
|---|---|
| Target / min / max chunk size | 400 / 150 / 500 tokens |
| Chunk overlap | **80 tokens** — not characters, not words |
| Sentence-boundary search window | ±30 tokens of target |
| Tokenizer | tiktoken `cl100k_base` (not gpt2, not Gemini native) |
| Similarity threshold | 0.65 |
| Over-retrieval top-k | 20 |
| Final top-k per dimension | 5 |
| Dimensions per case | **exactly 3** — re-prompt once, then error; never fall back to 2 or 4 |
| Generation temperature | 0.2 (not 0, not >0.5) |
| Embedding dimensions | 768 |
| Ranking order | `court_tier` asc → **`date` desc** → `similarity_score` desc |
| Court tier 4 (District) | excluded entirely before ranking |
| Snippet max length | 400 chars, prefer sentence boundary in last 50 |
| Similarity precision | 3 decimals |
| Upload limit | 20 MB, `application/pdf` only |
| JWT expiry | 60 minutes |
| OCR failure threshold | extracted text < 200 chars |

## API contract

- Base path `/api/v1`. All field names `snake_case`. All bodies UTF-8 JSON.
- **Timestamps:** `%Y-%m-%dT%H:%M:%SZ`. No `+00:00`, no milliseconds. Python's
  `datetime.isoformat()` does *not* produce this — use `strftime`.
- **IDs:** `case_<uuidv4>` and `user_<uuidv4>`, lowercase and hyphenated. Judgments are `j_XXXX` as
  given in the corpus. Chunks are `{judgment_id}_chunk_{NNN}`, zero-padded 3-digit, starting `001`.
- **Error envelope:** `{"error": {"code": str, "message": str, "details": obj}}` for every error.
- **Status codes that are easy to get wrong:**
  - OCR failure → **422** with `code: "ocr_failed"` (not 400, not 500)
  - Another user's case → **404** (not 403 — avoid leaking existence)
  - Oversized file → 413, wrong MIME → 415, dimensions not yet generated → 422 `dimensions_missing`
  - Gemini or storage upstream failure → 502 `upstream_error`

## Strings graded verbatim

- Empty dimension state: `No precedents found for this dimension.`
- OCR error (frontend): `We couldn't extract text from this PDF. It may be corrupted or image-only with illegible scans.`
- Login failure: `Sign-in failed. Please try again.`
- Upload validation: `Only PDF files are accepted.` / `File too large. Maximum 20 MB.`

Prompts in `04_ai_ml_spec.md` §4.1 and §4.2 are used **verbatim**.

## Stack

Fixed by spec: FastAPI + Python 3.11 + Pydantic v2 + uvicorn; React 18 + TypeScript strict + Vite +
Tailwind v3 + React Router v6 + React Query v5; Google OAuth 2.0 with PKCE; `gemini-2.5-flash`.

Free-tier substitutions (the email required a free build; specs mandate paid GCP):

| Spec | Actual | Deviation |
|---|---|---|
| `text-embedding-004` | `gemini-embedding-001` @ `output_dimensionality=768` | D-003 |
| GCS + signed URLs | local disk + authed streaming endpoint | D-001, D-004 |
| Cloud Run | Render (Docker) + Vercel | D-002 |
| Index at container start | `index_corpus.py` offline, vectors committed | D-005 |
| Document AI | pypdf text layer → pytesseract fallback | D-006 |
| Vertex Vector Search | FAISS in-memory | none — §4.5 permits |
| Firestore | SQLite | none — §5 permits "implementer's choice" |

Backend **must** deploy as Docker on Render: `pytesseract` needs the `tesseract` and `poppler`
binaries, which Render's native Python runtime cannot install.

## Established findings — do not re-derive

1. **`text-embedding-004` was shut down 2026-01-14.** The spec binds a model that no longer exists.
   `gemini-embedding-001` is the replacement because it is the only current model keeping *both* 768
   dimensions and parameter-based `RETRIEVAL_QUERY` / `RETRIEVAL_DOCUMENT` task types.
   `gemini-embedding-2` drops task-type parameters.
2. **No corpus section exceeds 400 tokens** (longest ~227; 60 of 72 under 150). Every section emits
   exactly one chunk → **72 chunks**, indices `001`–`006` per judgment. The overlap, sentence-boundary
   and 500-cap branches never execute on real data — unit tests must use synthetic long sections.
3. **Sample `chunk_id`s are not reproducible.** Only `j_0009_chunk_005` of 4 matches where its snippet
   actually lives. Sample matching is **structural** (field names, nesting, types), not byte-exact.
4. **Both sample PDFs have a real text layer** (ReportLab, 4 pages, ~6.5K chars). `pypdf` suffices;
   rasterising risks OOM on Render's 512 MB.
5. **Corpus is clean** — valid UTF-8, 45 em-dashes, tiers only {1,2,3}. No encoding bug.
6. Corpus `court_tier` is **baked for a Maharashtra-origin case**. Tier 2/3 is defined relative to the
   uploaded case's state, so the ranker recomputes it from `state` rather than trusting the field.
7. Tier 4 never appears in the corpus, so the exclusion rule needs synthetic test rows.

## Commands

```bash
# Backend
cd backend && uvicorn main:app --reload --port 8000
pytest                                    # chunker, ranker, upload integration

# Index the corpus (run once, commit data/corpus_index.json)
cd backend && python -m scripts.index_corpus --corpus ../data/judgments_corpus.json

# Frontend
cd frontend && npm run dev

# Eval (eval/eval.py is LOCKED — never modify)
cd eval && python eval.py \
  --api-base-url <backend>/api/v1 --auth-token $EVAL_TOKEN \
  --eval-set ../data/eval_set.json --output ../eval_results.json
```

## Disqualifiers

- API keys or `.env` committed anywhere in git history
- API contract mismatches (wrong field names, wrong response shapes)
- **Eval set content used inside any prompt** — `data/eval_set.json` is ground truth, never input
- Silent deviations with no `DEVIATIONS.md` entry
- Fabricated evaluation numbers — report whatever `eval.py` actually prints
- No deployed demo at submission
- Redesigning what the spec already decided

## Also forbidden by spec

Fine-tuning; keyword-matching the corpus JSON at query time instead of using the vector store;
hardcoding expected outputs; using the generation model to grade retrievals live; calling Gemini in
loops over chunks during retrieval (vector math is local); `localStorage` for auth tokens; calling
Gemini from the frontend; `dangerouslySetInnerHTML` with API content.
