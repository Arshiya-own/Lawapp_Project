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

### [D-001] Example — REPLACE THIS WITH YOUR ACTUAL DEVIATIONS

**Spec reference:** `01_architecture.md § 4.5 — Vector Store`

**Specified behavior:** Vertex AI Vector Search listed as preferred; ChromaDB, pgvector, FAISS all listed as acceptable.

**Your implementation:** Used ChromaDB in persistent mode on disk.

**Reason:** Faster to set up for a 3-day project; Vertex AI Vector Search requires additional GCP project configuration that would have consumed ~2 hours. ChromaDB is listed as acceptable in the spec.

**Tradeoff:** ChromaDB running on a single Cloud Run instance has no horizontal scaling. In production, swapping to Vertex would be preferred.

**Effort to bring into compliance:** Not a deviation that needs "fixing" — ChromaDB was listed as acceptable. Swap to Vertex is ~2 hours if desired.

---

*(Add further deviations below. Number them D-002, D-003, etc. If you have zero deviations, delete the example and write "No deviations from spec.")*
