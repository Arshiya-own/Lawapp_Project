# QUESTIONS

Ambiguities you encountered in the specs and how you resolved them. We deliberately left some gaps; finding and flagging them earns bonus points (+5 per the rubric).

This file is **not** for questions you email to us. It is for ambiguities you resolved independently.

## Format

Copy this block for each question:

```
### [Q-NNN] Short title

**Spec reference:** e.g. `04_ai_ml_spec.md § 5.2 — Vector Search`

**Ambiguity:** [what was unclear]

**Interpretations considered:**
1. [interpretation A]
2. [interpretation B]

**Your choice:** [which you picked]

**Reasoning:** [why, with reference to other parts of the spec when possible]

**Confidence:** [high / medium / low]
```

---

## Questions

### [Q-001] Is a case persisted when OCR fails?

**Spec reference:** `03_backend_spec.md` § 5.2 (upload), § 5.3 (case read), § 8 (async)

**Ambiguity:** `status` appears with two values — `"processing"` in the 201 upload response and
`"processed"` in the case-read response. OCR failure returns 422 `ocr_failed`. The spec never
says whether a row is written for a case whose OCR failed, and never defines a `"failed"` status.

**Interpretations considered:**
1. Persist the case with a third status, `"failed"`, so it appears in `GET /api/v1/cases`.
2. Do not persist at all — the 422 is terminal and no case record is created.

**Your choice:** Interpretation 2. `CaseStatus` is `Literal["processing", "processed"]`.

**Reasoning:** § 8 makes processing fully synchronous within the upload request, and § 5.2
lists OCR failure under **error responses** rather than as a success carrying a failed status.
A `"failed"` value appears nowhere in the spec or in any of the four sample fixtures. Adding
one would invent contract surface the frontend has no state for — `02_frontend_spec.md` defines
loading / empty / error / success, not a persisted failure row. Returning 422 without persisting
keeps `GET /api/v1/cases` meaning "cases you can actually work with".

**Confidence:** High.

---

### [Q-002] Is `details` always present in the error envelope?

**Spec reference:** `03_backend_spec.md` § 4 — Error Model

**Ambiguity:** The envelope is shown as `{"error": {"code", "message", "details"}}`, but
`details` is annotated `{ "optional": "structured context" }`. It is unclear whether the key
should be omitted when there is no context, or present and empty.

**Interpretations considered:**
1. Omit the `details` key entirely when empty.
2. Always emit `details`, defaulting to `{}`.

**Your choice:** Interpretation 2 — `details` is always present, `{}` when there is nothing to add.

**Reasoning:** A response shape that is constant across every error is easier for a client to
consume than one where a key appears conditionally; the frontend can read `error.details`
without a guard. "Optional" is read as describing the *content* being situational rather than
the key being absent. The cost either way is negligible, and a stable shape is the safer default
for a contract that is graded on structure.

**Confidence:** Medium — this one could reasonably go the other way.

---

### [Q-003] Upload returns `status: "processing"` although processing is synchronous

**Spec reference:** `03_backend_spec.md` § 5.2 (201 body), § 8 (Background Jobs / Async)

**Ambiguity:** § 8 states all processing is synchronous within the upload request and
§ 5.2 says "the endpoint blocks until processing completes or fails" — yet the 201 example
body in the same section shows `"status": "processing"`. By the time that response is
serialized the case is already processed, so the literal example contradicts the behaviour
the same section describes.

**Interpretations considered:**
1. Return `"processing"` verbatim as the § 5.2 example shows, even though it is stale the
   moment it is sent.
2. Return `"processed"`, since that is factually true once the blocking work has finished.

**Your choice:** Interpretation 1 — the upload response carries `"processing"`; the stored
row is `"processed"` and `GET /api/v1/cases/{case_id}` reflects that immediately.

**Reasoning:** The response shapes are graded against the documented examples, and § 5.2's
example is unambiguous about the literal value. CLAUDE.md's first working rule is to follow
the spec literally even where something else would be better. The cost is nil in practice:
any client that re-reads the case sees `"processed"` on the very next call, and the
frontend's own flow (`02_frontend_spec.md`) navigates to the case detail view after upload.

**Confidence:** Medium — a grader could reasonably have intended `"processing"` only as
placeholder prose rather than a binding value.

---

### [Q-004] The uploaded case's state is rarely derivable from `court` alone

**Spec reference:** `04_ai_ml_spec.md` § 5.3 — Ranking, court tier assignment;
`04_ai_ml_spec.md` § 4.1 — Metadata Extraction Prompt

**Ambiguity:** § 5.3 says tier 2 is "High Court of the same state as the uploaded case",
and that the state "is determined by the case's `court` metadata", giving two example
forms: `"Bombay High Court"` and `"Supreme Court of India with Maharashtra origin"`.

But `court` is produced by the § 4.1 extraction prompt, which asks only for "the court
name in which this case is filed (or being challenged from)" — it never asks for the
originating state. In practice the model returns a bare court name. For
`sample_case_1.pdf` it returns `"Supreme Court of India"`, with no origin, even though
the case is plainly a Maharashtra matter (the respondent is "The State of Maharashtra"
and the challenge is to a Bombay High Court order).

So for any Supreme Court case the state is undetermined, § 5.3's fallback applies, and
**tier 2 can never be assigned** — Bombay HC and Delhi HC both rank as tier 3.

**Interpretations considered:**
1. Use `court` only, exactly as § 5.3 states, and accept that the state is often
   undetermined.
2. Widen the search to other extracted metadata — `parties` and `synopsis` both mention
   the state for this sample — so tier 2 becomes reachable.
3. Change the § 4.1 prompt to ask for an origin state as well.

**Your choice:** Interpretation 1. `resolve_case_state()` reads `court` and nothing else.

**Reasoning:** § 5.3 names `court` as the source without qualification, and § 5.3 also
supplies the behaviour for exactly this situation — "If the case's state cannot be
determined, treat all non-SC High Courts as tier 3" — which would be redundant if the
state were always derivable. That fallback existing is the strongest evidence the authors
expected it to fire.

Interpretation 3 is ruled out separately: § 4.1 prompts are used verbatim, so changing
the prompt is not available. Interpretation 2 is defensible and would demonstrate tier 2
more often, but it invents a resolution order the spec does not describe, and guessing a
case's home state from party names would mis-fire whenever a state is a litigant in a
matter originating elsewhere.

The tier logic itself is fully implemented and tested for all four tiers
(`tests/test_ranker.py`), so tier 2 is reachable the moment `court` names a High Court —
it is the extraction that limits it, not the ranker.

**Confidence:** Medium-high on the reading; the practical consequence is worth flagging
because a reviewer testing with `sample_case_1.pdf` will only ever see tiers 1 and 3.

---

### [Q-005] Does the 0.65 similarity threshold apply to `/eval/retrieve`?

**Spec reference:** `04_ai_ml_spec.md` § 5.2 step 3; `starter_repo/README.md` — "The
`/eval/retrieve` Endpoint You Must Build"

**Ambiguity:** § 5.2 step 3 applies a 0.65 threshold during vector search. But
`/api/v1/eval/retrieve` is described only in the starter README, which is silent on the
threshold while calling the endpoint "raw retrieval results... no dimension generation,
no court-tier reranking. It exposes your retriever directly so we can evaluate it in
isolation from the ranking logic."

**Interpretations considered:**
1. Apply the threshold, since it is part of § 5.2 vector search.
2. Do not apply it — return the raw top-k by similarity.

**Your choice:** Interpretation 2. No threshold, no tier reranking; results are collapsed
to one entry per judgment and returned in descending similarity order.

**Reasoning:** The README frames the endpoint as the retriever "in isolation from the
ranking logic", and the threshold sits in § 5.2's filter stage alongside the collapse and
ranking steps the README explicitly excludes. Thresholding would also corrupt the metrics
the locked harness computes: `recall@10` and MRR assume a ranked list of length `top_k`,
and silently returning three items where ten were requested would understate recall for
reasons unrelated to retrieval quality.

Collapsing to unique judgments *is* applied, because the harness scores distinct
`judgment_id`s — returning several chunks of one judgment would spend top-k slots on
duplicates and understate recall for a different artificial reason.

**Confidence:** High.

---

### [Q-006] Precision@5 is capped by the eval set, not by retrieval quality

**Spec reference:** `data/eval_set.json`; `eval/eval.py` `precision_at_k`

**Ambiguity:** Not a spec ambiguity but a reporting one, logged because the headline
number invites a wrong conclusion.

Measured against the deployed retriever, mean **Precision@5 = 0.36**, which reads as poor
in isolation. It is not: each eval query has only 1-3 relevant judgments, and
`precision_at_k` divides hits by `k`, so the maximum attainable P@5 is
`len(relevant) / 5`.

| Query | relevant | P@5 | max possible |
|---|---|---|---|
| Section 65B certificate | 3 | 0.6 | 0.60 |
| FIR conversion to murder | 2 | 0.4 | 0.40 |
| Motive demolished | 1 | 0.2 | 0.20 |
| Quashing of proceedings | 2 | 0.4 | 0.40 |
| Dowry death presumption | 1 | 0.2 | 0.20 |

**Every query scores its theoretical maximum.** Recall@10 is 1.0 and MRR is 1.0 across
all five, and inspection of the returned order shows every relevant judgment ranked above
every irrelevant one.

**Your choice:** Report 0.36 exactly as `eval.py` prints it, and state the ceiling
alongside it. No adjustment, no alternative metric, no re-tuning to inflate the number.

**Reasoning:** Fabricated or massaged evaluation numbers are an explicit disqualifier, and
the honest figure plus its context is more informative than the figure alone. The ceiling
is a property of the eval set's small relevant sets, not of the retriever.

**Confidence:** High — arithmetic, verified per query in `eval_results.json`.

---

*(Add further questions below. If you found no ambiguities, write "No unresolved ambiguities." — though we expect most candidates to find at least one.)*
