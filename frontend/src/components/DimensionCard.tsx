/**
 * 02_frontend_spec.md § 6.3.
 *
 * Handles all four states explicitly (§ 9) — no silent "nothing happens" branch. The
 * empty-state string is graded verbatim (§ 11), so it lives in one exported constant
 * rather than being retyped.
 */

import type { RankedJudgment } from "../types/api";
import { JudgmentItem } from "./JudgmentItem";

/** § 11: exact text, do not reword. */
export const EMPTY_DIMENSION_TEXT = "No precedents found for this dimension.";

export interface DimensionCardProps {
  dimension: number;
  query: string;
  rationale: string;
  judgments: RankedJudgment[];
  status: "loading" | "success" | "empty" | "error";
  onRetry?: () => void;
  onViewSnippet?: (judgment: RankedJudgment) => void;
}

export function DimensionCard({
  dimension,
  query,
  rationale,
  judgments,
  status,
  onRetry,
  onViewSnippet,
}: DimensionCardProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        Dimension {dimension}
      </p>
      <h2 className="mt-1 font-medium text-slate-900">{query}</h2>
      <p className="mt-1 text-sm text-slate-600">{rationale}</p>

      <div className="mt-4">
        <h3 className="text-sm font-semibold text-slate-700">Precedents</h3>

        {status === "loading" && (
          <p className="mt-3 flex items-center gap-2 text-sm text-slate-500">
            <span
              aria-hidden="true"
              className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600"
            />
            Searching&hellip;
          </p>
        )}

        {status === "error" && (
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <p className="text-sm text-red-700">
              Couldn&rsquo;t retrieve results for this dimension.
            </p>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Retry
              </button>
            )}
          </div>
        )}

        {status === "empty" && (
          <p className="mt-3 text-sm text-slate-500">{EMPTY_DIMENSION_TEXT}</p>
        )}

        {status === "success" && (
          <ul className="mt-2">
            {judgments.map((judgment) => (
              <JudgmentItem
                key={judgment.chunk_id}
                judgmentId={judgment.judgment_id}
                citation={judgment.citation}
                court={judgment.court}
                date={judgment.date}
                similarityScore={judgment.similarity_score}
                snippet={judgment.snippet}
                onViewSnippet={() => onViewSnippet?.(judgment)}
              />
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
