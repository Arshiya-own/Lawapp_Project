# Mini-JuriNex Hiring Project — Package Overview

This package contains everything you need to run the 3-day hiring project for JuriNex.

## Package Contents

```
Lawapp_Project/
├── README.md                          ← you are here
├── brief/
│   └── 00_project_brief.md            ← the candidate-facing brief
├── specs/
│   ├── 01_architecture.md             ← system architecture + data flow
│   ├── 02_frontend_spec.md            ← UI pages, components, states
│   ├── 03_backend_spec.md             ← API contracts, auth, error codes
│   └── 04_ai_ml_spec.md               ← chunking, prompts, retrieval, ranking
├── samples/
│   ├── sample_case_metadata.json      ← expected output of upload pipeline
│   ├── sample_dimensions.json         ← expected dimension query output
│   ├── sample_retrieval_response.json ← expected retrieval output
│   └── sample_final_response.json     ← expected final ranked response
├── data/
│   ├── judgments_corpus.json          ← 12 pre-extracted judgments + metadata
│   └── eval_set.json                  ← 5 eval queries with ground truth
├── starter_repo/
│   ├── README.md                      ← starter repo instructions
│   ├── .env.example
│   ├── .gitignore
│   ├── backend/
│   │   ├── main.py                    ← FastAPI skeleton
│   │   └── requirements.txt
│   └── eval/
│       └── eval.py                    ← locked eval script (do not modify)
└── templates/
    ├── DEVIATIONS.md                  ← candidates fill in
    ├── QUESTIONS.md                   ← candidates fill in
    └── SPEC_COMPLIANCE.md             ← candidates fill in
```

## How to Use This Package

**For you (hiring manager):**

1. Read through the specs yourself. Run a dry implementation (or have an engineer do it) before sending to candidates. This validates the specs are buildable in 3 days and establishes realistic rubric thresholds.
2. Fill in the placeholders marked `[...]` in `00_project_brief.md` (recruiter email, deadline).
3. Expand `judgments_corpus.json` from 12 to 25 judgments if you want a larger retrieval pool (current 12 is workable).
4. Add or verify more eval queries in `eval_set.json` (current 5 is the minimum; 8–10 is better).
5. Zip everything and send to candidates on Day 0.

**For candidates (when you hand this to them):**

They receive the entire package except they should **not** be able to see your answer keys. Specifically:
- Keep for your grading use only: none of the files here are answer keys per se — the samples are intended as given reference outputs. But if you add more detailed expected outputs for your eval queries later, keep those private.

## Comprehension Gates Embedded in the Specs

Seven subtle requirements are embedded in the specs. Candidates who read carefully will catch these; candidates who skim will miss them. Catching any of them earns rubric bonus points.

| # | Spec | Requirement | Where |
|---|---|---|---|
| 1 | Architecture | All API timestamps must be UTC ISO 8601 with `Z` suffix (not `+00:00`) | § 6 "Data & Time Conventions" |
| 2 | Backend | OCR failures return HTTP **422**, not 400 or 500 | § 4 "Error Model" |
| 3 | Backend | Case IDs must be prefixed `case_` followed by a UUIDv4 | § 5.2 "Upload Endpoint" |
| 4 | Frontend | Empty state text must be verbatim: `"No precedents found for this dimension."` | § 5.3 "Results Page — Empty State" |
| 5 | AI/ML | Chunk overlap is exactly **80 tokens** (not characters, not words) | § 3.2 "Chunking Rules" |
| 6 | AI/ML | Exactly **3** dimension queries. Not 2, not 5. | § 4.1 "Dimensional Query Generation" |
| 7 | AI/ML | When `court_tier` is tied in ranking, break ties by `date` descending | § 5.3 "Ranking Tie-Breaker" |

**One genuine ambiguity** is also present: the AI/ML spec says "top-5 per dimension" but does not specify behavior when fewer than 5 chunks pass the similarity threshold of 0.65. Strong candidates will flag this in `QUESTIONS.md`.

## Grading Workflow

1. Clone candidate repo.
2. Verify deployed demo works — upload sample case, observe dimensions + results.
3. Run your grading script (you'll build this once) against their deployed URL:
   - POSTs the sample case PDF
   - Diffs each stage output against your saved samples
   - Records structural matches and mismatches
4. Run `eval.py` against their system → get Precision@5, Recall@10, MRR.
5. Read their `DEVIATIONS.md`, `QUESTIONS.md`, `SPEC_COMPLIANCE.md` — this is 25+ of the 100 rubric points.
6. Score per the rubric in `00_project_brief.md` § 7.

Total candidate grading time: ~45 minutes per candidate after scripts are built.

## Notes on Data Realism

The judgments in `judgments_corpus.json` are **synthetic but structurally realistic** — party names, facts, and reasoning are invented but follow the patterns of genuine Indian judgments (headnote, facts, issues, held, reasoning, order). This is deliberate:
- Avoids copyright and defamation issues around real parties
- Prevents candidates from Googling case names and shortcutting retrieval
- Lets you control the eval set precisely

If you want to swap in real judgments later (public domain from IndianKanoon), the schema will still hold.

## Version

Package v1.0 — Generated as a starting point. Expect to iterate based on your first 2–3 candidate runs.
