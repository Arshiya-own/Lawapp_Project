# Mini-JuriNex — Starter Repo

This is the scaffold you start from. You will replace this README with your own by submission time.

## What Is Provided

```
starter_repo/
├── README.md                    ← this file (replace with your own)
├── .env.example                 ← copy to .env and fill in
├── .gitignore
├── backend/
│   ├── main.py                  ← FastAPI skeleton
│   └── requirements.txt         ← Python deps
└── eval/
    └── eval.py                  ← LOCKED — do not modify
```

**You must build:**
- A working frontend under `frontend/` (React + TS + Vite per `02_frontend_spec.md`)
- A working backend completing the FastAPI skeleton
- An indexing script that loads `../data/judgments_corpus.json` into your vector store
- A Dockerfile for backend deployment to Cloud Run
- Deployment configuration for the frontend

## Required Submission Structure

By the end of Day 3, your repo should look approximately like:

```
your-repo/
├── README.md                    ← setup + architecture + design decisions
├── DEVIATIONS.md                ← every deviation from spec
├── QUESTIONS.md                 ← ambiguities found + resolutions
├── SPEC_COMPLIANCE.md           ← checklist of what you built vs. skipped
├── eval_results.json            ← output of eval.py
├── .env.example
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── main.py
│   ├── requirements.txt
│   ├── routers/...
│   ├── services/...
│   ├── models/...
│   ├── scripts/
│   │   └── index_corpus.py
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/...
├── data/
│   ├── judgments_corpus.json    ← copied from the provided package
│   └── eval_set.json            ← copied from the provided package
├── samples/                     ← keep for reference
└── eval/
    └── eval.py                  ← LOCKED
```

## Local Development — Suggested Flow

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env
# fill in .env
uvicorn main:app --reload --port 8000
```

### 2. Index the corpus

```bash
# From backend/ directory, once the indexing script is written
python -m scripts.index_corpus --corpus ../data/judgments_corpus.json
```

### 3. Frontend

```bash
# From project root
mkdir frontend && cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install @tanstack/react-query react-router-dom tailwindcss
# configure Tailwind per 02_frontend_spec.md
npm run dev
```

### 4. Run the eval

```bash
# After your backend is deployed
cd eval
python eval.py \
  --api-base-url https://your-backend.run.app/api/v1 \
  --auth-token "eyJ..." \
  --eval-set ../data/eval_set.json \
  --output ../eval_results.json
```

The eval script calls `POST /api/v1/eval/retrieve` with a query and expects a JSON response with a `judgments` array. See `eval/eval.py` docstring for the exact contract.

## The `/eval/retrieve` Endpoint You Must Build

The locked eval script depends on an endpoint not described elsewhere. Here is its contract:

```
POST /api/v1/eval/retrieve
Body: { "query": "...", "top_k": 10 }
Response 200:
{
  "judgments": [
    {
      "judgment_id": "j_0007",
      "similarity_score": 0.842,
      "court_tier": 1,
      "date": "2014-09-18"
    }
  ]
}
```

This endpoint returns **raw retrieval results** — a flat top-k list across the entire indexed corpus. No dimension generation, no court-tier reranking. It exposes your retriever directly so we can evaluate it in isolation from the ranking logic.

**Auth for this endpoint:** use a static bearer token matching env var `EVAL_TOKEN`. This keeps it simple for the eval harness and avoids entangling OAuth.

## Deployment Checklist

- [ ] Backend Dockerfile builds successfully
- [ ] Backend deployed to Cloud Run, URL accessible
- [ ] Frontend deployed, can reach backend
- [ ] OAuth configured for production redirect URI
- [ ] Secrets loaded from Secret Manager (or at minimum not hardcoded)
- [ ] `/api/v1/health` returns 200
- [ ] Upload → dimensions → retrieval flow works end-to-end
- [ ] `eval.py` runs successfully against deployed URL

## Common Pitfalls

1. **CORS misconfiguration** — frontend can't reach backend after deployment. Test with `curl -H "Origin: https://your-frontend.com" https://your-backend.run.app/api/v1/health -v`.
2. **Cold starts on Cloud Run** — first request after idle may be slow. Keep minimum instances at 0 for cost, or 1 if you want fast response for the demo.
3. **Gemini quota limits** — free tier has modest RPM limits. The eval hits 5 queries; stay under quota.
4. **Tokenizer mismatch** — `04_ai_ml_spec.md` § 3.2 specifies `tiktoken cl100k_base`. Use exactly this, not `gpt2` or Gemini's native tokenizer.
5. **Timestamp format** — `01_architecture.md` § 6 specifies `Z` suffix, not `+00:00`. Python's `datetime.isoformat()` by default does NOT give you `Z`. Use `.strftime('%Y-%m-%dT%H:%M:%SZ')` or equivalent.

## Questions?

Use `QUESTIONS.md` to log anything unclear. Do not email asking for help with design decisions — those are what we are evaluating. Email only for clarifications about requirements.
