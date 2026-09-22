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

This single key serves both models: `gemini-2.5-flash` for metadata and dimension generation, and
`gemini-embedding-001` for the 768-dimension vectors.

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
py -3.11 -m venv backend\.venv
backend\.venv\Scripts\activate
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

_To be completed — see [BUILD_PLAN.md](plan_to_do/BUILD_PLAN.md) for the intended structure._

## Evaluation

_To be completed once `eval.py` has been run against the deployed backend. Numbers reported will be
whatever the locked harness prints._
