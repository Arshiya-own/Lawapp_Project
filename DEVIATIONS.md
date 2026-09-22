# DEVIATIONS

Every deviation from the provided specifications must be documented here. Silent deviations are a disqualifier. Honest, well-reasoned deviations are scored on the rubric under "Deviation quality" (10 pts).

## Format

Copy this block for each deviation:

```
### [D-NNN] Short title

**Spec reference:** e.g. `04_ai_ml_spec.md § 3.2 — Chunking Rules`

**Specified behavior:** [quote or paraphrase what the spec says]

**Your implementation:** [what you actually did]

**Reason:** [why you deviated]

**Tradeoff:** [what this costs — performance, correctness, cost, complexity]

**Effort to bring into compliance:** [rough estimate — 1 hour? 1 day?]
```

---

## Deviations

### [D-008] Generation model: `gemini-3.6-flash` instead of `gemini-2.5-flash`

**Spec reference:** `01_architecture.md` § 4.6 and `04_ai_ml_spec.md` § 2 — both bind
`gemini-2.5-flash` as the generation model.

**Specified behavior:** All generation calls (metadata extraction § 4.1, dimensional query
generation § 4.2) use `gemini-2.5-flash` at temperature 0.2.

**Your implementation:** `gemini-3.6-flash` at temperature 0.2. Pinned as a constant in
`backend/config.py`.

**Reason:** The model is no longer callable. A `generateContent` request returns:

    404 NOT_FOUND — "This model models/gemini-2.5-flash is no longer available to new
    users. Please update your code to use models/gemini-3.6-flash for the latest
    features and improvements."

Note that `models.list()` still *reports* `gemini-2.5-flash` for this key; only an actual
call reveals the restriction, so this is not detectable from the model listing alone.
`gemini-3.6-flash` is the replacement Google's own error message names.

`gemini-flash-latest` also works and was rejected deliberately: it is a floating alias, and
§ 8 requires reproducibility, which a model that can change under the alias would undermine.

**Tradeoff:** Generated metadata and dimensional queries come from a newer model than the
spec assumed, so exact wording will differ from the sample fixtures. This is already the
expected situation — `samples/` are illustrative fixtures and sample matching is structural
(see QUESTIONS.md). **Temperature 0.2 was verified to still be accepted on 3.x**, so the
binding determinism setting is preserved and no second deviation is needed.

**Effort to bring into compliance:** Not possible from a new API key. An account with prior
`gemini-2.5-flash` access could revert by changing one constant.

---

### [D-007] Gemini SDK: `google-genai` instead of `google-generativeai`

**Spec reference:** `01_architecture.md` § 4.6, `04_ai_ml_spec.md` § 2 — the specs name models
(`gemini-2.5-flash`, `text-embedding-004`) but never name a Python SDK.

**Specified behavior:** No SDK is specified. The provided `starter_repo/backend/requirements.txt`
lists `google-generativeai`.

**Your implementation:** `google-genai` (the current unified SDK), pinned at 2.24.0.
`google-generativeai` and its transitive `google-ai-generativelanguage` were uninstalled.

**Reason:** `google-generativeai` is the legacy SDK and is no longer the supported path.
The substitution in D-003 depends on passing `output_dimensionality=768` together with a
`task_type` of `RETRIEVAL_QUERY` / `RETRIEVAL_DOCUMENT` to `gemini-embedding-001`; that
surface is the one carried forward in `google-genai`. Building the retrieval layer on a
deprecated client would be a needless second source of risk.

**Tradeoff:** None functionally — the models called are unchanged, so no API-contract or
retrieval behaviour differs. The cost is that the starter's requirements file is no longer
used verbatim, which is a visible divergence from the provided scaffold.

**Effort to bring into compliance:** ~1 hour to port the client calls back, but it would
reintroduce a deprecated dependency; not recommended.

---

### [D-001] Example — REPLACE THIS WITH YOUR ACTUAL DEVIATIONS

**Spec reference:** `01_architecture.md § 4.5 — Vector Store`

**Specified behavior:** Vertex AI Vector Search listed as preferred; ChromaDB, pgvector, FAISS all listed as acceptable.

**Your implementation:** Used ChromaDB in persistent mode on disk.

**Reason:** Faster to set up for a 3-day project; Vertex AI Vector Search requires additional GCP project configuration that would have consumed ~2 hours. ChromaDB is listed as acceptable in the spec.

**Tradeoff:** ChromaDB running on a single Cloud Run instance has no horizontal scaling. In production, swapping to Vertex would be preferred.

**Effort to bring into compliance:** Not a deviation that needs "fixing" — ChromaDB was listed as acceptable. Swap to Vertex is ~2 hours if desired.

---

*(Add further deviations below. Number them D-002, D-003, etc. If you have zero deviations, delete the example and write "No deviations from spec.")*
