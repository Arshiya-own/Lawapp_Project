"""
eval.py — Mini-JuriNex Evaluation Harness (LOCKED — DO NOT MODIFY)

Runs the eval set against a candidate's deployed system and computes:
- Precision@5
- Recall@10
- Mean Reciprocal Rank (MRR)

Usage:
    python eval.py \\
        --api-base-url https://your-backend.run.app/api/v1 \\
        --auth-token <bearer-token> \\
        --eval-set ../data/eval_set.json \\
        --output ../eval_results.json

The script:
1. Reads each eval query from eval_set.json
2. Calls the candidate's retrieval endpoint directly with the query
3. Collects returned judgment_ids across all dimensions
4. Compares against ground-truth relevant_judgment_ids
5. Writes metrics to the output file

NOTE: this eval bypasses the case-upload flow. It calls a dedicated eval-mode
endpoint that accepts a direct query and returns ranked judgments.

Candidates must expose this endpoint:
    POST /api/v1/eval/retrieve
    Body: { "query": "<query-string>", "top_k": 10 }
    Response: { "judgments": [ { "judgment_id": "j_...", "similarity_score": 0.XXX, "court_tier": N, "date": "YYYY-MM-DD" } ] }

This endpoint returns a flat top-k list across the whole corpus — no dimension
generation, no court-tier reranking. It is the raw retriever.

DO NOT MODIFY THIS FILE. We run it as-is against your deployment.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import httpx


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Precision@k: fraction of top-k results that are relevant."""
    if k == 0:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for r in top_k if r in relevant)
    return hits / k


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Recall@k: fraction of relevant items retrieved in top-k."""
    if not relevant:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for r in top_k if r in relevant)
    return hits / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    """Reciprocal rank of the first relevant result. 0 if none found."""
    for idx, r in enumerate(retrieved, start=1):
        if r in relevant:
            return 1.0 / idx
    return 0.0


def run_eval(
    api_base_url: str,
    auth_token: str,
    eval_set_path: Path,
    output_path: Path,
) -> None:
    with eval_set_path.open() as f:
        eval_data = json.load(f)

    queries = eval_data["queries"]
    per_query_results: list[dict[str, Any]] = []
    all_p5, all_r10, all_rr = [], [], []

    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    timeout = httpx.Timeout(30.0)

    with httpx.Client(timeout=timeout, headers=headers) as client:
        for q in queries:
            query_text = q["query"]
            relevant = set(q["relevant_judgment_ids"])

            url = f"{api_base_url.rstrip('/')}/eval/retrieve"
            body = {"query": query_text, "top_k": 10}

            try:
                resp = client.post(url, json=body)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                print(f"[ERROR] eval_id={q['eval_id']}: {exc}", file=sys.stderr)
                per_query_results.append(
                    {
                        "eval_id": q["eval_id"],
                        "query": query_text,
                        "error": str(exc),
                        "precision_at_5": 0.0,
                        "recall_at_10": 0.0,
                        "reciprocal_rank": 0.0,
                    }
                )
                all_p5.append(0.0)
                all_r10.append(0.0)
                all_rr.append(0.0)
                continue

            retrieved_ids = [j["judgment_id"] for j in data.get("judgments", [])]

            p5 = precision_at_k(retrieved_ids, relevant, 5)
            r10 = recall_at_k(retrieved_ids, relevant, 10)
            rr = reciprocal_rank(retrieved_ids, relevant)

            all_p5.append(p5)
            all_r10.append(r10)
            all_rr.append(rr)

            per_query_results.append(
                {
                    "eval_id": q["eval_id"],
                    "query": query_text,
                    "relevant_judgment_ids": list(relevant),
                    "retrieved_judgment_ids": retrieved_ids,
                    "precision_at_5": round(p5, 4),
                    "recall_at_10": round(r10, 4),
                    "reciprocal_rank": round(rr, 4),
                }
            )

    n = len(queries) if queries else 1
    summary = {
        "num_queries": len(queries),
        "mean_precision_at_5": round(sum(all_p5) / n, 4),
        "mean_recall_at_10": round(sum(all_r10) / n, 4),
        "mean_reciprocal_rank": round(sum(all_rr) / n, 4),
    }

    output = {
        "api_base_url": api_base_url,
        "eval_set_version": eval_data.get("eval_set_version", "unknown"),
        "summary": summary,
        "per_query": per_query_results,
    }

    with output_path.open("w") as f:
        json.dump(output, f, indent=2)

    print("\n=== Eval Summary ===")
    print(f"Queries:              {summary['num_queries']}")
    print(f"Mean Precision@5:     {summary['mean_precision_at_5']}")
    print(f"Mean Recall@10:       {summary['mean_recall_at_10']}")
    print(f"Mean Reciprocal Rank: {summary['mean_reciprocal_rank']}")
    print(f"\nDetails written to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mini-JuriNex eval harness")
    parser.add_argument("--api-base-url", required=True, help="e.g. https://your-backend.run.app/api/v1")
    parser.add_argument("--auth-token", default="", help="Optional bearer token for auth")
    parser.add_argument("--eval-set", type=Path, required=True, help="Path to eval_set.json")
    parser.add_argument("--output", type=Path, required=True, help="Path to write eval_results.json")
    args = parser.parse_args()

    run_eval(
        api_base_url=args.api_base_url,
        auth_token=args.auth_token,
        eval_set_path=args.eval_set,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
