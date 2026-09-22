/**
 * 02_frontend_spec.md § 5.3 — metadata card, Find Precedents, three dimension cards.
 *
 * "Find Precedents" chains POST /dimensions then POST /retrieve (§ 5.3). While that
 * runs, the dimension cards show `loading`; once dimensions exist they render with
 * their real query and rationale even if retrieval is still in flight, which is the
 * closest the two-call API gets to the spec's "results stream in per-dimension".
 */

import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { generateDimensions, getCase, retrievePrecedents } from "../api/cases";
import { CaseMetadataCard } from "../components/CaseMetadataCard";
import { DimensionCard } from "../components/DimensionCard";
import { Header } from "../components/Header";
import { JudgmentSnippetModal } from "../components/JudgmentSnippetModal";
import type { RankedJudgment } from "../types/api";

export function ResultsPage() {
  const { caseId = "" } = useParams();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<RankedJudgment | null>(null);

  const caseQuery = useQuery({
    queryKey: ["case", caseId],
    queryFn: () => getCase(caseId),
    enabled: Boolean(caseId),
  });

  const findPrecedents = useMutation({
    mutationFn: async () => {
      await generateDimensions(caseId);
      return retrievePrecedents(caseId);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["case", caseId] }),
  });

  if (caseQuery.isPending) {
    return (
      <Shell>
        <p className="text-sm text-slate-500">Loading case&hellip;</p>
      </Shell>
    );
  }

  if (caseQuery.isError) {
    return (
      <Shell>
        <div className="flex items-center gap-3">
          <p className="text-sm text-red-700">Couldn&rsquo;t load this case.</p>
          <button
            type="button"
            onClick={() => void caseQuery.refetch()}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Retry
          </button>
        </div>
      </Shell>
    );
  }

  const detail = caseQuery.data;
  const dimensions = detail.dimensions ?? [];
  const retrieval = detail.retrieval ?? [];
  const running = findPrecedents.isPending;

  const resultFor = (dimensionNumber: number) =>
    retrieval.find((entry) => entry.dimension_number === dimensionNumber);

  function statusFor(dimensionNumber: number) {
    if (running) return "loading" as const;
    if (findPrecedents.isError) return "error" as const;
    const result = resultFor(dimensionNumber);
    if (!result) return "loading" as const;
    return result.judgments.length === 0 ? ("empty" as const) : ("success" as const);
  }

  return (
    <Shell>
      {detail.metadata && (
        <CaseMetadataCard
          parties={detail.metadata.parties}
          court={detail.metadata.court}
          sections={detail.metadata.sections_invoked}
          synopsis={detail.metadata.synopsis}
          jurisdiction={detail.metadata.jurisdiction}
        />
      )}

      {retrieval.length === 0 && (
        <div className="mt-6">
          <button
            type="button"
            onClick={() => findPrecedents.mutate()}
            disabled={running}
            className="flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {running && (
              <span
                aria-hidden="true"
                className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white"
              />
            )}
            {running ? "Finding precedents…" : "Find Precedents"}
          </button>

          {findPrecedents.isError && (
            <p role="alert" className="mt-3 text-sm text-red-700">
              Couldn&rsquo;t find precedents for this case. Please try again.
            </p>
          )}
        </div>
      )}

      {(dimensions.length > 0 || running) && (
        <div className="mt-6 space-y-4">
          {(dimensions.length > 0
            ? dimensions
            : // § 9: never a blank screen — placeholders carry the loading state.
              [1, 2, 3].map((n) => ({
                dimension_number: n,
                query: "Identifying a legal dimension…",
                rationale: "",
              }))
          ).map((dimension) => (
            <DimensionCard
              key={dimension.dimension_number}
              dimension={dimension.dimension_number}
              query={dimension.query}
              rationale={dimension.rationale}
              judgments={resultFor(dimension.dimension_number)?.judgments ?? []}
              status={statusFor(dimension.dimension_number)}
              onRetry={() => findPrecedents.mutate()}
              onViewSnippet={setSelected}
            />
          ))}
        </div>
      )}

      {selected && (
        <JudgmentSnippetModal
          judgment={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-content px-4 py-8">{children}</main>
    </div>
  );
}
