# Mini-JuriNex — Flow Charts

Mermaid source. Renders natively on GitHub and in VS Code (Markdown Preview Mermaid Support).

Reflects the **free-tier build** as agreed: SQLite + local disk, FAISS in-memory, Render + Vercel,
`gemini-embedding-001` @ 768d in place of the retired `text-embedding-004`. Spec section references
point into `auxillary/Lawapp_Project/specs/`.

---

## 1. System architecture

```mermaid
flowchart TB
    subgraph client["Browser"]
        SPA["React 18 + TypeScript<br/>Vite · Tailwind · React Router v6<br/>React Query v5"]
    end

    subgraph vercel["Vercel — free tier"]
        STATIC["Static assets<br/>VITE_API_BASE_URL"]
    end

    subgraph render["Render — free tier, Docker"]
        API["FastAPI + Pydantic v2<br/>Python 3.11 · uvicorn"]
        FAISS["FAISS index<br/>72 chunks × 768d<br/>in memory"]
        SQLITE["SQLite<br/>users · cases"]
        DISK["Local disk<br/>data/uploads/"]
        TESS["pypdf → pytesseract<br/>tesseract + poppler binaries"]
    end

    subgraph google["Google — free tier, no billing"]
        OAUTH["OAuth 2.0 + PKCE<br/>openid · email · profile"]
        FLASH["gemini-2.5-flash<br/>temp 0.2"]
        EMBED["gemini-embedding-001<br/>768 dimensions"]
    end

    SPA -->|HTTPS| STATIC
    SPA <-->|"JSON REST /api/v1"| API
    SPA -->|"sign in"| OAUTH
    API --> OAUTH
    API --> SQLITE
    API --> DISK
    API --> TESS
    API --> FAISS
    API -->|"metadata + dimensions"| FLASH
    API -->|"query embeddings"| EMBED
```

**Deviations visible here:** Render replaces Cloud Run (D-002); local disk replaces GCS with signed
URLs (D-001, D-004); `gemini-embedding-001` replaces `text-embedding-004` (D-003). FAISS and SQLite
are both explicitly permitted by `01_architecture.md` §4.5 and §5.

---

## 2. Authentication — OAuth 2.0 Authorization Code + PKCE

```mermaid
sequenceDiagram
    actor U as Lawyer
    participant F as React SPA
    participant B as FastAPI
    participant G as Google OAuth

    U->>F: Click "Sign in with Google"
    F->>B: GET /api/v1/auth/google/authorize?return_to=/
    B->>B: Generate code_verifier + code_challenge
    B-->>F: authorize_url
    F->>G: Redirect to consent screen
    U->>G: Grant openid, email, profile
    G->>B: GET /auth/google/callback?code&state
    B->>G: Exchange code + code_verifier for tokens
    G-->>B: id_token + access_token
    B->>B: Upsert user as user_<uuid4>
    B->>B: Sign JWT, 60 min expiry
    B-->>F: 302 redirect with session established
    F->>B: GET /api/v1/auth/me
    B-->>F: user_id, email, name, picture, created_at

    Note over F: Token held in memory only.<br/>Never localStorage — frontend spec §10.
```

Any `401 unauthenticated` from a protected route sends the SPA to `/login` (F-12).

---

## 3. Upload pipeline

`01_architecture.md` §5 · `03_backend_spec.md` §5.2, §7 · `04_ai_ml_spec.md` §4.1

```mermaid
flowchart TD
    A["User drops or selects a PDF"] --> B{"Client-side validation"}
    B -->|"MIME is not application/pdf"| B1["Only PDF files are accepted."]
    B -->|"size over 20 MB"| B2["File too large. Maximum 20 MB."]
    B -->|"valid"| C["POST /api/v1/cases/upload<br/>multipart/form-data, field: file"]

    C --> D{"Authenticated?"}
    D -->|"no"| D1["401 unauthenticated<br/>SPA redirects to /login"]
    D -->|"yes"| E{"Server-side validation"}
    E -->|"over 20 MB"| E1["413 payload_too_large"]
    E -->|"wrong MIME"| E2["415 unsupported_media_type"]

    E -->|"ok"| F["case_id = 'case_' + uuid4<br/>lowercase, hyphenated"]
    F --> G["Write bytes to<br/>data/uploads/user_id/case_id/original.pdf"]
    G --> H["Extract text per page via pypdf"]
    H --> I{"200 chars or more?"}
    I -->|"no"| J["Fallback: pdf2image + pytesseract"]
    J --> K{"200 chars or more?"}
    K -->|"no"| K1["422 ocr_failed<br/>NOT 400, NOT 500"]
    K -->|"yes"| L
    I -->|"yes"| L["Join pages with page markers"]

    L --> M["Truncate to first 12000 chars"]
    M --> N["gemini-2.5-flash @ temp 0.2<br/>metadata prompt, spec §4.1 verbatim"]
    N --> O{"Valid JSON after fence stripping?"}
    O -->|"no"| P["Retry once, stricter reminder"]
    P --> Q{"Valid now?"}
    Q -->|"no"| Q1["502 upstream_error"]
    Q -->|"yes"| R
    O -->|"yes"| R["Insert case row<br/>status = processed<br/>processed_at set"]
    R --> S["201 Created<br/>case_id · status · uploaded_at"]
    S --> T["SPA polls GET /cases/case_id<br/>then routes to /cases/:caseId"]

    style K1 fill:#7f1d1d,color:#fff
    style E1 fill:#7f1d1d,color:#fff
    style E2 fill:#7f1d1d,color:#fff
    style Q1 fill:#7f1d1d,color:#fff
```

Processing is **synchronous** inside the one request — `03_backend_spec.md` §8. No Celery, no
Pub/Sub. Render's request timeout must exceed the Gemini round trip; the spec says a run over 60
seconds returns 504, "but this should not happen for the sample PDFs provided."

**Contradiction found while drawing this — for `QUESTIONS.md`.** §5.2 specifies the 201 body as
`"status": "processing"`, yet the same section says "the endpoint blocks until processing completes
or fails." The status is therefore **stale the moment it is emitted** — the work is already done —
and the frontend (`02_frontend_spec.md` §5.2) then polls `GET /cases/:id` "until status =
`processed`" for a transition that has already happened. Both sample files show `"processed"`.

Resolution: return `"processing"` literally as §5.2 shows, since sample I/O is diffed and worth 20
points, and keep the frontend poll so the documented state machine still holds. The poll will
simply succeed on its first call. Logged rather than silently "fixed".

---

## 4. Query pipeline — dimensions then retrieval

`01_architecture.md` §7 · `04_ai_ml_spec.md` §4.2, §5

```mermaid
flowchart TD
    A["User clicks Find Precedents"] --> B["POST /cases/case_id/dimensions"]
    B --> C{"status == processed?"}
    C -->|"no"| C1["422 — code UNSPECIFIED by spec<br/>see note below"]
    C -->|"yes"| D["gemini-2.5-flash @ temp 0.2<br/>dimension prompt, spec §4.2 verbatim"]
    D --> E{"Exactly 3 dimensions?"}
    E -->|"no"| F["Re-prompt once"]
    F --> G{"Exactly 3 now?"}
    G -->|"no"| G1["Raise error.<br/>Never silently accept 2 or 4."]
    G -->|"yes"| H
    E -->|"yes"| H["Persist dimensions<br/>200 OK with generated_at"]

    H --> I["POST /cases/case_id/retrieve"]
    I --> J{"Dimensions generated?"}
    J -->|"no"| J1["422 dimensions_missing"]
    J -->|"yes"| K["Loop over the 3 dimensions"]

    K --> L["Embed query<br/>gemini-embedding-001, 768d<br/>task type RETRIEVAL_QUERY"]
    L --> M["Cosine similarity against all 72 chunks"]
    M --> N["Over-retrieve top 20"]
    N --> O["Discard similarity below 0.65"]
    O --> P["Collapse chunks to judgments<br/>keep highest-similarity chunk each"]
    P --> Q["Exclude court_tier 4 — District Court"]
    Q --> R["Rank: court_tier asc<br/>then date DESC<br/>then similarity desc"]
    R --> S["Take top 5"]
    S --> T{"Any judgments left?"}

    T -->|"no"| T1["judgments: []<br/>UI renders verbatim:<br/>No precedents found for this dimension."]
    T -->|"yes"| T2["Truncate snippet to 400 chars<br/>Round similarity to 3 decimals"]

    T1 --> U["Aggregate all 3 dimension results"]
    T2 --> U
    U --> V["200 OK with retrieved_at"]
    V --> W["3 DimensionCards, up to 5 JudgmentItems each"]

    style G1 fill:#7f1d1d,color:#fff
    style J1 fill:#7f1d1d,color:#fff
    style R fill:#1e3a5f,color:#fff
```

The tie-breaker chain in the blue node is graded: **`court_tier` ascending → `date` descending →
`similarity_score` descending**. Date descending is the easy one to miss.

**Two error-code gaps found while drawing this — both for `QUESTIONS.md`:**

- `03_backend_spec.md` §5.4 says "422 if case is not yet `processed`" but **names no `code`**. The
  §4 table offers only `ocr_failed` (wrong — the PDF read fine) and `validation_error` (wrong — it
  is documented as "Pydantic validation failed on request body", and the body here is empty). So no
  listed code fits. Resolution: emit `case_not_processed` and log the invention, rather than
  misuse `validation_error`.
- `dimensions_missing` (§5.5) is **absent from the §4 error table**, so that table is not
  exhaustive. Harmless, but it means the table cannot be used as the single source of truth when
  building the error enum.

---

## 5. Corpus indexing — one-time, offline

`01_architecture.md` §8 · `04_ai_ml_spec.md` §3

```mermaid
flowchart LR
    A["data/judgments_corpus.json<br/>12 judgments"] --> B["For each judgment,<br/>for each of 6 sections"]
    B --> C{"Section token count<br/>via tiktoken cl100k_base"}
    C -->|"under 150 — rule 3"| D["Emit as a single chunk<br/>regardless of size"]
    C -->|"150 to 400 — at or under target"| E["Emit as a single chunk"]
    C -->|"over 400 — rules 2, 5, 6"| F["Split at target 400<br/>overlap exactly 80 tokens<br/>sentence boundary ±30<br/>hard cap 500"]
    D --> G["chunk_id = judgment_id + _chunk_ + NNN"]
    E --> G
    F --> G
    G --> H["Embed, task type RETRIEVAL_DOCUMENT<br/>gemini-embedding-001, 768d"]
    H --> I["data/corpus_index.json<br/>72 chunks, committed to git"]
    I --> J["Loaded into FAISS at container start<br/>zero API calls on cold start"]

    style F fill:#3f3f1e,color:#fff
```

> **Finding (approximate — verify on Day 2).** On a chars÷4 estimate the longest section is ~227
> tokens and 60 of 72 fall under 150, which would mean the yellow node **never executes on real
> data**: every section emits one chunk, giving 72 chunks with indices `001`–`006` per judgment.
>
> These are estimates, not measurements — `tiktoken` is not installed locally yet. Legal text
> tokenizes denser than plain prose (`Section 65B(4)` costs several tokens for few characters), so
> real counts will run **higher** than the estimate. The margin on the load-bearing claim is
> comfortable (227 → 400 needs a 76% underestimate), but "60 of 72 under 150" is fragile and some
> sections will likely cross the minimum. **Re-measure with real `tiktoken` counts on Day 2 before
> relying on the 72-chunk figure**, and fix the exact number in `CLAUDE.md` and
> `plan_to_do/BUILD_PLAN.md`, which currently repeat the estimate.
>
> Either way the overlap, sentence-boundary and 500-cap logic must be implemented correctly and is
> proven by unit tests on synthetic input (`SPEC_COMPLIANCE.md` M-04/05/06, B-20).

---

## 6. Evaluation path — bypasses everything above

`starter_repo/README.md` · `eval/eval.py` is **locked**

```mermaid
flowchart LR
    A["data/eval_set.json<br/>5 queries + ground truth"] --> B["eval.py, unmodified"]
    B --> C["POST /api/v1/eval/retrieve<br/>Bearer EVAL_TOKEN<br/>body: query, top_k=10"]
    C --> D["Embed query, search FAISS"]
    D --> E["Flat top-10 across whole corpus<br/>NO dimension generation<br/>NO court-tier reranking"]
    E --> F["judgment_id · similarity_score<br/>court_tier · date"]
    F --> G["Precision@5 · Recall@10 · MRR"]
    G --> H["eval_results.json"]

    style E fill:#1e3a5f,color:#fff
```

Two things about this endpoint:

- It is documented **only** in `starter_repo/README.md`, nowhere in the four specs. Miss it and the
  locked script errors out and scores 0.0 on all three metrics.
- Whether the 0.65 threshold applies here is genuinely ambiguous. The build argues **no** — the
  starter README calls it "the raw retriever… in isolation from the ranking logic", and the
  threshold belongs to `04_ai_ml_spec.md` §5.2's filter stage. Logged in `QUESTIONS.md`.

`data/eval_set.json` is ground truth and **must never appear inside a prompt** — that is an explicit
disqualifier.

---

## 7. Frontend states

Frontend spec §9 — every data-fetching component handles all four explicitly. No silent
"nothing happens".

```mermaid
stateDiagram-v2
    [*] --> idle
    idle --> validating: drop or select file
    validating --> error: wrong type or over 20 MB
    validating --> uploading: valid
    uploading --> error: 401 / 413 / 415 / 5xx
    uploading --> processing: 201 Created
    processing --> error: 422 ocr_failed
    processing --> success: status == processed
    success --> [*]: navigate to /cases/:caseId
    error --> idle: user dismisses

    state processing {
        [*] --> polling
        polling --> polling: GET /cases/:id
    }
```

Per-`DimensionCard`: `loading` → `success` \| `empty` \| `error`, where `empty` renders the byte-exact
string `No precedents found for this dimension.` and `error` offers a Retry.
