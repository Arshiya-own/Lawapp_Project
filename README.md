# Mini-JuriNex

A precedent-research tool for Indian lawyers. Upload a case PDF; the app extracts its metadata,
generates exactly three "dimensional queries" describing distinct legal angles, and retrieves
matching passages from a 12-judgment corpus, reranked by court hierarchy.

Built to the specs in `auxillary/Lawapp_Project/specs/`. Deviations from those specs are recorded
in [DEVIATIONS.md](DEVIATIONS.md); ambiguities and their chosen interpretations in
[QUESTIONS.md](QUESTIONS.md); a clause-by-clause compliance table in
[SPEC_COMPLIANCE.md](SPEC_COMPLIANCE.md).

---

## Setup

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | **3.11** | Spec-bound. Docker image is `python:3.11-slim`. |
| Node.js | 18+ | For the Vite frontend. |
| Git | any | |
| Tesseract + Poppler | optional | Only to exercise the OCR fallback locally; the Docker image installs both. |

On Windows, install Python 3.11.9 (the last 3.11 release with a Windows installer) and leave
*"Add python.exe to PATH"* **unchecked** — select it explicitly with `py -3.11` so your default
`python` is unaffected.

### 1. Gemini API key

1. Go to <https://aistudio.google.com/apikey> and sign in with a personal Google account
   (managed Workspace accounts often have API access disabled).
2. **Create API key**, in a new or existing Google Cloud project.
3. Copy the key — it begins `AIza`.

This single key serves both models: `gemini-3.6-flash` for metadata and dimension generation, and
`gemini-embedding-001` for the 768-dimension vectors. (The specs bind `gemini-2.5-flash`, which
now returns 404 for new API keys — see D-008.)

Verify it works for both before continuing:

```powershell
$headers = @{ "x-goog-api-key" = "<your-key>" }
$body = '{"model":"models/gemini-embedding-001","content":{"parts":[{"text":"test"}]},"taskType":"RETRIEVAL_QUERY","outputDimensionality":768}'
Invoke-RestMethod -Method Post -Uri "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent" -Headers $headers -ContentType "application/json" -Body $body
```

### 2. Google OAuth client

1. At <https://console.cloud.google.com>, select (or create) a project — ideally the same one as
   the API key.
2. **APIs & Services → OAuth consent screen**. User type **External**. Fill in app name and
   support/developer emails; skip logo and domains.
3. Add exactly three scopes — `openid`, `userinfo.email`, `userinfo.profile`. The spec
   (`01_architecture.md` §4.3) says "nothing more".
4. **Publish the app.** All three scopes are non-sensitive, so publishing requires no Google
   verification review. Left in Testing mode, only pre-registered test users can sign in — which
   would lock a reviewer out of the demo.
5. **Credentials → Create Credentials → OAuth client ID**, application type **Web application**.

   Not "Single-Page Application", despite the frontend being an SPA. The Web type is what issues a
   `client_secret`, and the authorization-code exchange happens server-side at
   `/api/v1/auth/google/callback` (`03_backend_spec.md` §5.1). A secret shipped in a browser bundle
   would defeat PKCE entirely.

6. Add the redirect URI, matched by Google as an exact string:

   ```
   http://localhost:8000/api/v1/auth/google/callback
   ```

   Leave *Authorized JavaScript origins* empty — this is a server-side redirect flow. Add the
   deployed callback URL here too once the backend is hosted.

7. Save the **Client ID** and **Client secret**.

### 3. Environment file

```powershell
Copy-Item .env.example .env
```

Fill in five values — `GEMINI_API_KEY`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`
from steps 1–2, plus two you generate yourself:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`JWT_SIGNING_SECRET` signs session tokens; `EVAL_TOKEN` is the static bearer token guarding
`POST /api/v1/eval/retrieve` for the eval harness. Everything else can stay at its default.

`.env` is gitignored and must never be committed — see [Security](#security).

### 4. Backend

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt
cd backend
uvicorn main:app --reload --port 8000
```

### 5. Index the corpus

Vectors are precomputed and committed, so a cold start costs zero API calls. To regenerate:

```powershell
cd backend
python -m scripts.index_corpus --corpus ..\data\judgments_corpus.json
```

### 6. Frontend

```powershell
cd frontend
npm install
npm run dev
```

### 7. Tests

```powershell
cd backend
pytest
```

---

## Security

- `.env` is gitignored and absent from all git history.
- The OAuth `client_secret` lives only on the backend; the frontend never sees it.
- Session tokens are held in memory, never in `localStorage` (`02_frontend_spec.md` F-17).
- Gemini is called only from the backend.

---

## Architecture

```
  Browser (Vercel)                    Render (Docker)
  ────────────────                    ───────────────
  React 18 + Vite                     FastAPI + uvicorn
    │                                   │
    │  1. POST /cases/upload ──────────►│  pypdf text layer
    │                                   │    └─ fallback: pdf2image + pytesseract
    │                                   │  Gemini §4.1 prompt ──► metadata
    │◄───────────── 201 case_id ────────│  SQLite
    │                                   │
    │  2. POST /cases/{id}/dimensions ─►│  Gemini §4.2 prompt ──► exactly 3 queries
    │                                   │
    │  3. POST /cases/{id}/retrieve ───►│  embed query (RETRIEVAL_QUERY, 768d, L2)
    │                                   │  FAISS IndexFlatIP over 72 chunks
    │                                   │    └─ threshold 0.65 → collapse → rank → top 5
    │◄──────── 3 dimensions × ≤5 ───────│
```

**Retrieval pipeline.** The 12-judgment corpus is chunked per section (`headnote`, `facts`,
`issues`, `held`, `reasoning`, `order`), producing 72 chunks. Each is embedded at 768
dimensions and **L2-normalized**, then stored in a FAISS inner-product index — which equals
cosine similarity only on unit vectors. Vectors are precomputed and committed, so a cold
start makes zero embedding calls.

**Ranking** is `court_tier` ascending → `date` **descending** → `similarity_score`
descending, with District Courts excluded. Tier is recomputed from the uploaded case's
state rather than read from the corpus, because "same-state High Court" is a property of
the query, not the judgment.

Design decisions that depart from the specs are in [DEVIATIONS.md](DEVIATIONS.md);
ambiguities and how they were resolved are in [QUESTIONS.md](QUESTIONS.md).

### Session model

Authorization Bearer JWT, 60-minute expiry (`01_architecture.md` §4.3 permits either this
or cookies). The OAuth code-for-token exchange happens on the backend, which holds the
`client_secret`; the callback redirects to the frontend with `?token=`, which the SPA reads
into memory and strips from the URL. Tokens are never persisted — a refresh signs the user
out, which is the cost of §10's `localStorage` ban.

---

## Deployment

### Backend (Render)

Docker runtime, **not** native Python — `pytesseract` and `pdf2image` need the `tesseract`
and `poppler` binaries, which Render's native environments cannot install.

1. New **Web Service** → connect this repository → **Docker**.
2. Dockerfile path `./backend/Dockerfile`, **Docker context `.`** (the repository root, so
   the image can copy `data/corpus_index.json`).
3. Health check path `/api/v1/health`.
4. Set the environment variables listed in [render.yaml](render.yaml). The secrets are
   marked `sync: false` and must be entered in the dashboard.
5. Set `GOOGLE_OAUTH_REDIRECT_URI` to `https://<service>.onrender.com/api/v1/auth/google/callback`
   and add that exact string to the Google OAuth client's authorised redirect URIs.

### Frontend (Vercel)

1. Import the repository, **root directory `frontend`**.
2. Set `VITE_API_BASE_URL` to `https://<service>.onrender.com/api/v1`.
3. Set the backend's `FRONTEND_BASE_URL` to the Vercel origin — it is both the CORS
   allow-list entry and the post-login redirect target.

### Free-tier behaviour worth knowing

- The service **spins down after 15 minutes idle** and takes ~1 minute to wake. Warm it
  before running the eval or the first query pays that cost.
- The filesystem is **ephemeral**: uploaded PDFs and the SQLite database are lost on every
  redeploy, restart and spin-down (see D-001). The corpus index is unaffected — it ships
  inside the image.

---

## Evaluation

Run against the deployed backend:

```powershell
cd eval
python eval.py `
  --api-base-url https://<service>.onrender.com/api/v1 `
  --auth-token $env:EVAL_TOKEN `
  --eval-set ../data/eval_set.json `
  --output ../eval_results.json
```

Results against the local backend, from the unmodified harness:

| Metric | Value |
|---|---|
| Mean Precision@5 | 0.36 |
| Mean Recall@10 | 1.0 |
| Mean Reciprocal Rank | 1.0 |

**Precision@5 is at its theoretical maximum on all five queries.** Each query has only 1–3
relevant judgments, and `precision_at_k` divides hits by `k`, so the ceiling is
`len(relevant) / 5` — 0.60, 0.40, 0.20, 0.40, 0.20 respectively, each of which the
retriever attains. Recall@10 and MRR are both 1.0: every relevant judgment is retrieved,
and ranked above every irrelevant one. See QUESTIONS.md Q-006.

## Tests

```powershell
cd backend
pytest        # 71 tests: chunker, vector store, ranker
```

The chunker and ranker suites lean on **synthetic** fixtures on purpose. No corpus section
reaches the 400-token target, so the overlap, sentence-boundary and 500-cap rules never
fire on real data; and no District Court judgment exists, so tier-4 exclusion is
unreachable. Testing only against the corpus would leave those rules unexercised.
