# Mini-JuriNex — 3-Day Implementation Project

**Role:** Full-Stack / AI Engineer
**Duration:** 3 days (≈ 24 hours of focused work)
**Stack:** As specified in the provided documents

---

## 1. What We Are Testing

This is not a design exercise. JuriNex already has:

- An architecture document
- A frontend specification
- A backend specification
- An AI/ML specification
- Sample inputs and expected outputs

**Your job is to read these documents carefully and implement what they describe.**

This mirrors how you will actually work at JuriNex: specifications exist, decisions have been made, and you build to them. We are evaluating how precisely you can translate written requirements into working software — which is a different and more important skill than designing from scratch.

---

## 2. What You Will Receive on Day 0

| Document | Purpose |
|---|---|
| `specs/01_architecture.md` | System architecture, component boundaries, data flow |
| `specs/02_frontend_spec.md` | Pages, components, states, routing, UX flows |
| `specs/03_backend_spec.md` | API contracts, request/response schemas, error codes, auth flow |
| `specs/04_ai_ml_spec.md` | Chunking strategy, embedding model, prompts, retrieval pipeline, ranking rules |
| `samples/` | Sample parsed metadata, sample dimensions, sample retrieval output, sample final response |
| `data/judgments_corpus.json` | 12 judgments, pre-extracted, with metadata |
| `data/eval_set.json` | 5 queries with ground-truth judgment IDs |
| `starter_repo/` | Folder scaffold + `eval.py` (do not modify) |
| `templates/` | Starter files for `DEVIATIONS.md`, `QUESTIONS.md`, `SPEC_COMPLIANCE.md` |

Read every spec before writing code. Time spent reading on Day 1 pays back on Day 3.

---

## 3. Core Rules

1. **Follow the specs.** API contracts, component structure, prompts, chunking rules, and ranking logic are defined. Implement them as described.

2. **Match the samples.** If a sample shows a response as a specific JSON structure, your system must return the same structure — field names, nesting, types. We will run automated diffs against the samples.

3. **Deviations must be documented.** Small, justified deviations are acceptable (clearer variable name, better error message). Large deviations are not (different vector store, different chunking, different API shape). Every deviation goes in `DEVIATIONS.md` with: *what you changed, why, what tradeoff.*

4. **When a spec is ambiguous, log it.** Note in `QUESTIONS.md`, make a reasonable choice consistent with the spec's intent, explain your reasoning. Do not silently invent.

5. **Do not scope-creep.** If a feature is not in the spec, do not add it. Unasked-for "improvements" are a negative signal.

---

## 4. What You Will Build

The system described in the specs lets a lawyer:

1. Sign in with Google.
2. Upload a case file PDF.
3. See extracted case metadata (parties, court, sections, synopsis).
4. Get generated dimensional queries targeting legal propositions.
5. See precedents retrieved per dimension, ranked by court hierarchy.
6. Click a judgment to see the source snippet.

Exact API shapes, prompts, chunking rules, and ranking logic are in the specs. Do not reconstruct them from this section — read the documents.

---

## 5. Suggested Day-by-Day Plan

**Day 1 — Read, set up, foundation (≈ 8 hrs)**
- Read all 4 specs end-to-end, take notes (1.5 hrs — do not skip)
- GCP + project + repo setup per `01_architecture.md` (1 hr)
- Google OAuth per `03_backend_spec.md` (2 hrs)
- PDF upload + OCR per backend + AI/ML specs (2 hrs)
- Metadata extraction per `04_ai_ml_spec.md` prompt (1.5 hrs)
- **Checkpoint:** sample case uploads, matches sample metadata structure.

**Day 2 — Retrieval per spec (≈ 8 hrs)**
- Indexing script following chunking rules exactly (2.5 hrs)
- Dimensional query generator using spec's prompt template (2 hrs)
- Retrieval endpoint matching API contract (2 hrs)
- Frontend components per `02_frontend_spec.md` (1.5 hrs)
- **Checkpoint:** retrieval response matches sample output structurally.

**Day 3 — Rank, eval, ship (≈ 8 hrs)**
- Court-hierarchy reranker per AI/ML spec (1.5 hrs)
- Frontend polish per frontend spec (states: loading, empty, error) (2 hrs)
- Run `eval.py`, produce `eval_results.json` (1.5 hrs)
- Deploy per architecture deployment section (1.5 hrs)
- README + `DEVIATIONS.md` + `QUESTIONS.md` + `SPEC_COMPLIANCE.md` + Loom (1.5 hrs)
- **Checkpoint:** public demo URL, compliance checklist passed, eval report submitted.

---

## 6. Deliverables

Submit a single email with:

1. **GitHub repo** containing:
   - Full implementation
   - `DEVIATIONS.md` — every deviation from spec + reason + tradeoff
   - `QUESTIONS.md` — ambiguities + how you resolved them
   - `SPEC_COMPLIANCE.md` — checklist of what you implemented vs. skipped
   - `eval_results.json`
   - `README.md` — setup instructions, architecture diagram, how to run eval
2. **Deployed demo URL** — working at submission time.
3. **5-minute Loom** — demo happy path end-to-end, then walk through one entry in `DEVIATIONS.md`.

---

## 7. Evaluation Rubric (100 points)

| Dimension | Weight | What we look for |
|---|---:|---|
| **Specification adherence** | 30 | API contracts match. Prompts match. Chunking rules followed. Frontend components match spec. |
| **Sample I/O correctness** | 20 | Outputs at each pipeline stage structurally match the provided samples. We will diff them. |
| **Retrieval quality on eval set** | 15 | Precision@5, Recall@10, MRR on `eval_set.json`. |
| **Deviation quality** | 10 | When you deviated, was it justified? Is the tradeoff articulated? Silent deviations lose heavily. |
| **Production readiness** | 10 | Secrets handled per architecture doc. Errors handled per backend spec. |
| **Code quality** | 8 | Readable, typed where it helps, tests on critical paths. |
| **Documentation quality** | 7 | `DEVIATIONS.md`, `QUESTIONS.md`, `SPEC_COMPLIANCE.md`, README are honest and useful. |

**Bonus (+5):** catching genuine bugs or ambiguities in our specs and flagging them well in `QUESTIONS.md`. We deliberately left a few.

---

## 8. What Will Disqualify You

- API keys committed to the repo.
- API contract mismatches with our backend spec (wrong field names, wrong response shapes).
- Eval set content used inside prompts.
- Silent deviations from spec — no `DEVIATIONS.md` entry.
- Fabricated evaluation numbers.
- No deployed demo by submission.
- Re-designing things the spec already decided without strong justification in `DEVIATIONS.md`.

---

## 9. FAQ

**The spec says X but I think Y is better.** Implement X. If you feel strongly, ship X, then note Y in `DEVIATIONS.md` as a future proposal. We evaluate proposals; we do not evaluate unilateral substitutions.

**The spec is unclear.** Note in `QUESTIONS.md`, pick the interpretation closest to the rest of the spec, proceed. Finding real ambiguities earns points.

**Can I use LangChain / LlamaIndex?** Only if the AI/ML spec allows it. Check `04_ai_ml_spec.md`.

**Do I need Indian legal expertise?** No. Specs contain everything you need about legal structure.

**Sample output has a typo.** Flag in `QUESTIONS.md`. Match the sample as given. Don't "fix" silently.

**What if I can't finish?** Submit what you have. `SPEC_COMPLIANCE.md` honestly lists done vs. skipped. A small, spec-faithful, working slice beats a large, spec-deviant, broken system.

---

## 10. Submission

Email deliverables to **[recruiter email]** by **[deadline]**. Include repo link, demo URL, and Loom link in the email body.

Good luck.
