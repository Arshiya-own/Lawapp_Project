/**
 * 02_frontend_spec.md § 6.4.
 *
 * Row layout: citation + court + date on the left, a 140-character snippet preview in
 * the middle, similarity pill and "View snippet" on the right.
 */

export interface JudgmentItemProps {
  judgmentId: string;
  citation: string;
  court: string;
  date: string;
  similarityScore: number;
  snippet: string;
  onViewSnippet: () => void;
}

const PREVIEW_LENGTH = 140;

export function preview(text: string): string {
  return text.length <= PREVIEW_LENGTH
    ? text
    : `${text.slice(0, PREVIEW_LENGTH)}…`;
}

export function JudgmentItem({
  judgmentId,
  citation,
  court,
  date,
  similarityScore,
  snippet,
  onViewSnippet,
}: JudgmentItemProps) {
  return (
    <li className="flex flex-col gap-3 border-t border-slate-100 py-3 first:border-t-0 md:flex-row md:items-start md:gap-4">
      <div className="md:w-56 md:shrink-0">
        <p className="font-semibold text-slate-900">{citation}</p>
        <p className="text-xs text-slate-500">
          {court} &middot; {date}
        </p>
      </div>

      <p className="flex-1 text-sm text-slate-600">{preview(snippet)}</p>

      <div className="flex items-center gap-3 md:shrink-0">
        <span
          className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium tabular-nums text-slate-700"
          title={`Similarity score for ${judgmentId}`}
        >
          {/* § 11: similarity always displays to 3 decimal places. */}
          {similarityScore.toFixed(3)}
        </span>
        <button
          type="button"
          onClick={onViewSnippet}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          View snippet
        </button>
      </div>
    </li>
  );
}
