# 04 — AI/ML Specification

**Document:** AI/ML Pipeline Specification
**Version:** 1.0
**Audience:** Engineers implementing the retrieval and generation pipeline

---

## 1. Purpose

This document defines the AI/ML components of Mini-JuriNex: chunking, embedding, prompt templates, retrieval, and ranking. These rules are binding because retrieval quality and the automated grading script depend on them.

---

## 2. Models (Binding)

| Role | Model | Notes |
|---|---|---|
| Text embedding | `text-embedding-004` | 768 dimensions |
| Generation (metadata, dimensions) | `gemini-2.5-flash` | temperature 0.2 |

Do not swap these for other models without a `DEVIATIONS.md` entry with strong justification.

---

## 3. Chunking

### 3.1 Judgment Structure Awareness

Each judgment in `judgments_corpus.json` has the following logical sections when present:

- `headnote` — summary
- `facts` — factual background
- `issues` — legal questions framed
- `held` — holdings
- `reasoning` — ratio decidendi and discussion
- `order` — final orders

The corpus JSON provides these as separate fields. Chunk each section independently — do not merge across sections. This preserves the legal structure that matters for retrieval.

### 3.2 Chunking Rules

1. **Tokenizer:** use the `tiktoken` `cl100k_base` tokenizer for all token counts in chunking. (It is close enough to Gemini's tokenization for our purposes; precision is less important than consistency.)
2. **Target chunk size:** 400 tokens.
3. **Minimum chunk size:** 150 tokens. If a section is shorter, emit it as a single chunk regardless of size.
4. **Maximum chunk size:** 500 tokens. Never emit a chunk longer than this.
5. **Overlap:** chunks within the same section overlap by **exactly 80 tokens**. (Not 80 characters. Not 80 words. Tokens.)
6. **Sentence boundary preference:** when choosing a split point, prefer the nearest sentence boundary (period, question mark, semicolon) within ±30 tokens of the target. If none found, split at the target.
7. **Section boundary:** never overlap across section boundaries — each section's chunking is independent.

### 3.3 Chunk Metadata

Each chunk stored in the vector store must include:

```json
{
  "chunk_id": "j_0007_chunk_004",
  "judgment_id": "j_0007",
  "section": "reasoning",
  "text": "...",
  "token_count": 387,
  "embedding": [ ... 768 floats ... ],
  "metadata": {
    "citation": "(2014) 10 SCC 473",
    "case_name": "Anvar P.V. vs P.K. Basheer",
    "court": "Supreme Court of India",
    "court_tier": 1,
    "date": "2014-09-18",
    "jurisdiction": "Criminal",
    "state": null
  }
}
```

### 3.4 Chunk ID Format

`{judgment_id}_chunk_{NNN}` where `NNN` is a zero-padded 3-digit index starting at `001`, monotonically increasing per judgment.

---

## 4. Generation Prompts

### 4.1 Metadata Extraction Prompt

Given OCR text from a case file, extract structured metadata using this prompt template:

```
You are a legal assistant extracting structured metadata from an Indian court case file.

Given the following case text, extract:
- parties: the parties in the format "Petitioner vs. Respondent"
- court: the court name in which this case is filed (or being challenged from)
- jurisdiction: one of "Criminal", "Civil", "Constitutional", "Commercial", "Other"
- sections_invoked: list of statutory sections cited (e.g., "IPC 302", "CrPC 438")
- synopsis: a single sentence, maximum 200 characters, describing what this case is about

Return ONLY valid JSON matching this schema:
{{
  "parties": string,
  "court": string,
  "jurisdiction": string,
  "sections_invoked": [string],
  "synopsis": string
}}

Case text:
---
{case_text}
---
```

The `case_text` is the OCR output, truncated to the first 12,000 characters if longer.

**Response parsing:** extract the JSON object. If the model wraps it in markdown code fences, strip them.

### 4.2 Dimensional Query Generation Prompt

Given the extracted metadata, generate dimensional queries:

```
You are a senior Indian litigator identifying the distinct legal propositions and factual scenarios in a case that could yield relevant precedents.

Case metadata:
- Parties: {parties}
- Court: {court}
- Jurisdiction: {jurisdiction}
- Sections invoked: {sections_invoked}
- Synopsis: {synopsis}

Generate exactly 3 "dimensional queries" for precedent retrieval. Each dimension must target a DISTINCT legal proposition or factual matrix — not a restatement of the case facts.

Good dimension query: "Non-compliance with Section 65B certificate for electronic evidence"
Bad dimension query: "Criminal case of Rahul Kasat involving murder"

Return ONLY valid JSON:
{{
  "dimensions": [
    {{
      "dimension_number": 1,
      "query": "string, 5-15 words, targets a specific legal proposition",
      "rationale": "string, one sentence explaining why this dimension matters"
    }},
    // exactly 3 entries, dimension_number 1, 2, 3
  ]
}}
```

**Strict rule:** exactly 3 dimensions. If the model returns fewer or more, re-prompt once. If it still misbehaves, raise an error. Do not silently fall back to 2 or 4.

---

## 5. Retrieval

### 5.1 Query Embedding

Embed each dimension query using `text-embedding-004` with task type `RETRIEVAL_QUERY`.
(Chunks during indexing use task type `RETRIEVAL_DOCUMENT`.)

### 5.2 Vector Search

For each dimension query:
1. Compute cosine similarity against every indexed chunk.
2. Retrieve top 20 chunks by similarity. *(We over-retrieve before filtering and ranking.)*
3. Apply similarity threshold: discard any chunk with similarity < **0.65**.
4. Collapse chunks to judgments: if multiple chunks of the same judgment remain, keep only the highest-similarity chunk per judgment.
5. Proceed to ranking (§ 5.3).

### 5.3 Ranking

Rank the remaining judgments per dimension using this deterministic process:

**Primary key:** `court_tier` ascending (lower is better — 1 = Supreme Court is best).

Court tier assignment:
- `1` — Supreme Court of India
- `2` — High Court of the same state as the uploaded case
- `3` — Any other High Court
- `4` — District Court (**excluded entirely** — filter these out before ranking)

The "same state as the uploaded case" is determined by the case's `court` metadata. Example mappings:
- Case's court = "Bombay High Court" or "Supreme Court of India with Maharashtra origin" → state = Maharashtra → tier 2 = Bombay HC, tier 3 = all other HCs.
- If the case's state cannot be determined, treat all non-SC High Courts as tier 3.

**Tie-breaker (when `court_tier` is equal):** sort by `date` **descending** (more recent first).

**Secondary tie-breaker (same tier, same date):** sort by `similarity_score` descending.

Take the top **5** judgments per dimension after ranking.

### 5.4 Similarity Score Reporting

In the API response, report the cosine similarity rounded to 3 decimals. Example: `0.842`.

### 5.5 Snippet Selection

The `snippet` field in the response is the `text` of the retrieved chunk. If the chunk is longer than 400 characters, truncate to the first 400 characters, preferring to end at a sentence boundary if one exists within the last 50 characters; otherwise hard-truncate and append `"…"`.

---

## 6. Index Persistence

Once indexed, the vector store persists across requests. The index is rebuilt only when the corpus file changes or by admin action. Do not re-index on every request.

If using in-memory FAISS, indexing happens at container start and is acceptable for this exercise given the small corpus size.

---

## 7. Cost Awareness

Be mindful of token usage:
- Metadata extraction: one Gemini call per upload
- Dimension generation: one Gemini call per case
- Retrieval: three embedding calls per retrieval (one per dimension query)

Do not call Gemini in loops over chunks or judgments during retrieval. Vector math is local.

---

## 8. Determinism

- Embeddings are deterministic given the same input and model version.
- Generation temperature is set to 0.2 for reproducibility. Do not use 0 (too rigid) or > 0.5 (too variable).

---

## 9. Failure Handling

| Failure | Behavior |
|---|---|
| Gemini returns malformed JSON | Retry once with a stricter reminder appended. If still bad, raise `502 upstream_error`. |
| Gemini rate limit (429) | Exponential backoff: 1s, 2s, 4s. Then raise `502`. |
| Embedding call fails | Retry once. Then raise `502`. |
| Empty retrieval (no chunks pass threshold) | Return empty `judgments: []` for that dimension. Frontend shows empty state. |

---

## 10. Forbidden Techniques (For This Exercise)

- Fine-tuning any model
- Using a retriever that bypasses the vector store (e.g., reading the corpus JSON at query time and doing keyword match)
- Using the eval set content inside any prompt
- Hardcoding expected outputs
- Using the generation model to "grade" retrievals live

---

## 11. Permitted Stretch (Do Not Count Toward MVP)

If you finish MVP and have time:
- Hybrid retrieval (BM25 + dense) with Reciprocal Rank Fusion
- Per-judgment "why relevant" summaries grounded in the retrieved chunk
- Query expansion: generating 2–3 paraphrases per dimension and averaging their results

Note these in `DEVIATIONS.md` as explicit additions so we know to look for them.

---

## 12. Summary of Binding Numeric and Structural Decisions

| Item | Value |
|---|---|
| Embedding model | text-embedding-004 (768d) |
| Generation model | gemini-2.5-flash |
| Temperature | 0.2 |
| Tokenizer for chunking | tiktoken cl100k_base |
| Target chunk size | 400 tokens |
| Min chunk size | 150 tokens |
| Max chunk size | 500 tokens |
| Overlap | 80 tokens |
| Similarity threshold | 0.65 |
| Over-retrieval top-k | 20 |
| Final top-k per dimension | 5 |
| Dimensions per case | exactly 3 |
| Court tier 4 (District) | excluded |
| Ranking primary key | court_tier ascending |
| Ranking tie-breaker | date descending |
| Snippet max length | 400 chars |
| Similarity display precision | 3 decimals |
