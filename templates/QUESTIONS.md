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

### [Q-001] Example — REPLACE WITH YOUR ACTUAL QUESTIONS

**Spec reference:** `04_ai_ml_spec.md § 5.2 — Vector Search, step 3`

**Ambiguity:** The spec says "Apply similarity threshold: discard any chunk with similarity < 0.65." It also says "Take the top 5 judgments per dimension after ranking." It does not specify what to do when fewer than 5 judgments pass the similarity threshold.

**Interpretations considered:**
1. Return fewer than 5 results — empty slots stay empty.
2. Lower the threshold until 5 results are returned.
3. Return zero results and show the empty state.

**Your choice:** Interpretation 1 — return whatever passes the threshold, up to 5. Zero is possible.

**Reasoning:** The frontend spec (`02_frontend_spec.md` § 5.3) explicitly defines an empty state with verbatim text "No precedents found for this dimension." This empty state only makes sense if the backend can legitimately return zero results. Lowering the threshold would make the empty state dead code. Interpretation 1 is therefore most consistent with the rest of the spec.

**Confidence:** High.

---

*(Add further questions below. If you found no ambiguities, write "No unresolved ambiguities." — though we expect most candidates to find at least one.)*
