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

Eight deviations. Six (D-001 to D-006) follow from a single constraint: the engagement
required a free stack, while the specs assume a billing-enabled GCP project. Two were
discovered by running the code — D-007 and D-008 — and are model/SDK substitutions forced
by upstream changes since the specs were written.

None of them touch the API contract, the chunking rules, or the ranking logic.

| ID | Area | Forced by |
|---|---|---|
| D-001 | PDF storage: local disk, not GCS | free tier |
| D-002 | Hosting: Render + Vercel, not Cloud Run | free tier |
| D-003 | Embedding model: `gemini-embedding-001` | upstream shutdown |
| D-004 | PDF access: authed streaming, not signed URLs | follows D-001 |
| D-005 | Indexing: offline, vectors committed | free-tier quota |
| D-006 | OCR: text layer first, pytesseract fallback | free tier + 512 MB |
| D-007 | Gemini SDK: `google-genai` | starter used legacy SDK |
| D-008 | Generation model: `gemini-3.6-flash` | upstream restriction |

---

### [D-001] Case PDF storage: local disk instead of Google Cloud Storage

**Spec reference:** `01_architecture.md` § 4.4 — Storage

**Specified behavior:** Raw PDFs stored in a private GCS bucket `jurinex-{env}-cases/`,
object key `users/{user_id}/cases/{case_id}/original.pdf`, accessed via 15-minute signed
URLs.

**Your implementation:** Written to local disk under `UPLOAD_DIR`, preserving the same key
layout — `users/{user_id}/cases/{case_id}/original.pdf` (`services/storage.py`).

**Reason:** The engagement requires a free stack; GCS requires a billing-enabled GCP
project. Keeping the object-key layout identical confines the substitution to the storage
backend rather than letting it leak into the path scheme, so migrating later is a change
to one module.

**Tradeoff:** Significant, and it compounds with D-002. Render's free tier has an
**ephemeral filesystem** and cannot mount a persistent disk, so uploaded PDFs do not
survive a redeploy, a restart, or the 15-minute idle spin-down. Persistence is
per-instance-lifetime. For a demo this is acceptable — a reviewer uploads, views results
and is done within one session — but it is not production behaviour. The corpus index is
unaffected: it ships inside the image (D-005), so retrieval works on a cold start even
when previously uploaded cases have gone.

**Effort to bring into compliance:** ~2 hours with a billing-enabled GCP project:
`google-cloud-storage` in place of `Path.write_bytes`, plus signed-URL generation. The key
layout needs no change.

---

### [D-002] Hosting: Render (Docker) + Vercel instead of Cloud Run

**Spec reference:** `01_architecture.md` § 9.1, § 9.2 — Deployment

**Specified behavior:** Backend and frontend both deployed to Cloud Run.

**Your implementation:** Backend as a Docker web service on Render's free tier; frontend
static build on Vercel.

**Reason:** Cloud Run requires a billing-enabled GCP project. Render offers a genuinely
free Docker runtime with no card, which is the constraint the engagement set.

Docker specifically, not Render's native Python runtime: `pytesseract` shells out to the
`tesseract` binary and `pdf2image` to poppler's `pdftoppm`, and native environments block
`apt-get` and OS-level installs, so the OCR fallback could not exist there at all.

**Tradeoff:** The free-tier limits are real and worth stating plainly — 512 MB RAM,
0.1 CPU, spin-down after 15 minutes idle with roughly a minute to wake. The first request
after idle is slow, which matters when running `eval.py` against the deployed URL: warm
the service first or the first query pays the cold start. The 512 MB ceiling also informed
D-006, since rasterising four pages at 200 DPI is the memory-hungry path.

**Effort to bring into compliance:** ~1 hour. The Dockerfile is portable; Cloud Run needs
the same image plus `gcloud run deploy`.

---

### [D-003] Embedding model: `gemini-embedding-001` instead of `text-embedding-004`

**Spec reference:** `04_ai_ml_spec.md` § 2, § 5.1, § 12

**Specified behavior:** Embed with `text-embedding-004` at 768 dimensions, task types
`RETRIEVAL_QUERY` for queries and `RETRIEVAL_DOCUMENT` for chunks.

**Your implementation:** `gemini-embedding-001` with `output_dimensionality=768` and the
same two task types.

**Reason:** `text-embedding-004` was shut down on 2026-01-14 and returns 404. It cannot be
implemented at all. `gemini-embedding-001` is the replacement that preserves **both**
properties the spec's design depends on: 768 dimensions (§ 2) and parameter-based task
types (§ 5.1). `gemini-embedding-2` also produces 768 dimensions but drops the `task_type`
parameter — instructions move into the prompt — which would have been a second, larger
deviation touching the retrieval design rather than just the model name.

**Tradeoff:** One that is easy to miss and would have been silent.
`gemini-embedding-001` pre-normalizes only its default 3072-dimension output; at 768 it
returns raw vectors, measured norm ≈0.568. Since cosine similarity is implemented as a
FAISS inner-product index, and inner product equals cosine **only** on unit vectors, every
vector is explicitly L2-normalized (`services/embeddings.py`), on both the document and
query side.

Measured on the real index, skipping that step drops the top score from 0.817 to 0.577 and
leaves **zero** chunks above the binding 0.65 threshold — the app would render
"No precedents found for this dimension." everywhere while appearing to work.

**Effort to bring into compliance:** Not possible; the specified model no longer exists.

---

### [D-004] PDF access: authenticated streaming instead of signed URLs

**Spec reference:** `01_architecture.md` § 4.4 — "private bucket, signed URLs only
(15-minute expiry)"

**Specified behavior:** Clients fetch the original PDF via a time-limited GCS signed URL.

**Your implementation:** Files are served through the authenticated API rather than by
handing out a pre-signed URL. Ownership is enforced by the same rule as every other case
route: `db.get_case()` takes `user_id` as part of the lookup, so another user's case is a
404 rather than a 403 (§ 11).

**Reason:** Signed URLs are a GCS feature. With local-disk storage (D-001) there is no
equivalent primitive, and inventing a bespoke signed-token scheme would add security
surface the spec never asked for.

**Tradeoff:** Bytes flow through the application instead of object storage, which would
matter at scale and does not here. The access-control property the spec cares about — only
the owner can read a case's PDF — is preserved, and arguably strengthened: no URL stays
valid for 15 minutes after being shared.

**Effort to bring into compliance:** Folded into D-001; signed URLs come with the GCS
migration.

---

### [D-005] Indexing: offline script with committed vectors, not at container start

**Spec reference:** `04_ai_ml_spec.md` § 4.5, § 6; `01_architecture.md` § 8

**Specified behavior:** § 4.5 permits in-memory FAISS "only if indexing happens at
container start".

**Your implementation:** `scripts/index_corpus.py` is run once offline; the resulting
`data/corpus_index.json` (72 chunks, 768 dimensions, 660 KB) is committed and copied into
the image. Startup loads it; nothing is embedded at boot.

**Reason:** Embedding 72 chunks at every container start would spend free-tier quota on
each spin-up — and the free tier spins down every 15 idle minutes, so that is frequent. It
also makes cold starts slower and, worse, dependent on the Gemini API being reachable at
boot: a transient outage would mean a container that starts but cannot retrieve.

This arguably satisfies § 6's actual requirement — "the index is rebuilt only when the
corpus file changes or by admin action" — more faithfully than re-embedding at boot does.

**Tradeoff:** The index must be regenerated and committed whenever the corpus or the
embedding model changes. `index_corpus.py` guards the failure mode that matters by
refusing to write the file unless every vector is unit length, so a normalization
regression fails at build time rather than degrading retrieval silently in production.

**Effort to bring into compliance:** ~15 minutes — call the same `build_index()` from the
lifespan handler. Not recommended, for the reasons above.

---

### [D-006] OCR: pypdf text layer first, pytesseract as fallback

**Spec reference:** `01_architecture.md` § 4.7; `03_backend_spec.md` § 7

**Specified behavior:** OCR via Document AI or pytesseract.

**Your implementation:** `pypdf` extracts the embedded text layer first; only if that
yields under 200 characters does the pipeline rasterise via pdf2image and run pytesseract.
Both binaries are installed in the image, so the fallback is live in production.

**Reason:** Document AI requires billing. Between the two remaining options, running
pytesseract unconditionally would be strictly worse: both sample PDFs are ReportLab
documents with a real text layer (~6.5K characters over 4 pages), so rasterising them at
200 DPI would spend seconds and a large amount of memory reproducing text already present
— on a 512 MB instance (D-002) that is a genuine OOM risk.

**Tradeoff:** Two code paths instead of one, and the fallback is the path least exercised
by the provided samples — precisely the one that could rot unnoticed. A corrupted PDF is
handled by the same route: `pypdf` parse failures are caught and degrade to "no text",
which produces the 422 `ocr_failed` that § 4 requires for a corrupted file, rather than
escaping as a 500.

**Effort to bring into compliance:** ~1 hour to swap in Document AI with billing enabled.

---

### [D-007] Gemini SDK: `google-genai` instead of `google-generativeai`

**Spec reference:** `01_architecture.md` § 4.6, `04_ai_ml_spec.md` § 2 — the specs name
models (`gemini-2.5-flash`, `text-embedding-004`) but never name a Python SDK.

**Specified behavior:** No SDK is specified. The provided
`starter_repo/backend/requirements.txt` lists `google-generativeai`.

**Your implementation:** `google-genai` (the current unified SDK), pinned at 2.24.0.
`google-generativeai` and its transitive `google-ai-generativelanguage` were uninstalled.

**Reason:** `google-generativeai` is the legacy SDK and is no longer the supported path.
D-003 depends on passing `output_dimensionality=768` together with a `task_type` of
`RETRIEVAL_QUERY` / `RETRIEVAL_DOCUMENT` to `gemini-embedding-001`; that surface is the one
carried forward in `google-genai`. Building the retrieval layer on a deprecated client
would be a needless second source of risk.

**Tradeoff:** None functionally — the models called are unchanged, so no API-contract or
retrieval behaviour differs. The cost is that the starter's requirements file is no longer
used verbatim, which is a visible divergence from the provided scaffold.

**Effort to bring into compliance:** ~1 hour to port the client calls back, but it would
reintroduce a deprecated dependency; not recommended.

---

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
§ 8 requires reproducibility, which a model that can change under the alias would
undermine.

**Tradeoff:** Generated metadata and dimensional queries come from a newer model than the
spec assumed, so exact wording differs from the sample fixtures. That is already the
expected situation — `samples/` are illustrative fixtures and sample matching is structural
(see QUESTIONS.md). **Temperature 0.2 was verified to still be accepted on 3.x**, so the
binding determinism setting is preserved and no second deviation is needed.

**Effort to bring into compliance:** Not possible from a new API key. An account with prior
`gemini-2.5-flash` access could revert by changing one constant.

---
