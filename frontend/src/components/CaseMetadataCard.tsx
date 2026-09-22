/** 02_frontend_spec.md § 6.2. Synopsis truncates to 3 lines with a "Show more" expander. */

import { useState } from "react";

export interface CaseMetadataCardProps {
  parties: string;
  court: string;
  sections: string[];
  synopsis: string;
  jurisdiction: string;
}

export function CaseMetadataCard({
  parties,
  court,
  sections,
  synopsis,
  jurisdiction,
}: CaseMetadataCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h1 className="text-xl font-semibold text-slate-900">{parties}</h1>

      <dl className="mt-4 space-y-2 text-sm">
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 font-medium text-slate-500">Court:</dt>
          <dd className="text-slate-800">{court}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 font-medium text-slate-500">Sections:</dt>
          <dd className="text-slate-800">{sections.join(", ")}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 font-medium text-slate-500">Jurisdiction:</dt>
          <dd className="text-slate-800">{jurisdiction}</dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 font-medium text-slate-500">Synopsis:</dt>
          <dd className="text-slate-800">
            <p className={expanded ? undefined : "line-clamp-3"}>{synopsis}</p>
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className="mt-1 rounded text-sm font-medium text-slate-600 underline hover:text-slate-900"
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          </dd>
        </div>
      </dl>
    </section>
  );
}
