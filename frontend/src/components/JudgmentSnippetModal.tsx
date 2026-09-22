/**
 * 02_frontend_spec.md § 6.5 — full-screen on mobile, centered on desktop.
 * Closes on ESC, backdrop click, or the Close button (§ 11), and traps focus (§ 7).
 */

import { useEffect, useRef } from "react";

import type { RankedJudgment } from "../types/api";

export interface JudgmentSnippetModalProps {
  judgment: RankedJudgment;
  onClose: () => void;
}

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export function JudgmentSnippetModal({ judgment, onClose }: JudgmentSnippetModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeButtonRef.current?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab") return;

      // Focus trap: cycle within the dialog rather than escaping to the page behind.
      const nodes = dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (!nodes || nodes.length === 0) return;

      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-stretch justify-center bg-slate-900/50 sm:items-center sm:p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="snippet-modal-title"
        className="flex h-full w-full flex-col overflow-y-auto bg-white p-6 sm:h-auto sm:max-h-[80vh] sm:max-w-2xl sm:rounded-lg sm:shadow-xl"
      >
        <h2 id="snippet-modal-title" className="text-lg font-semibold text-slate-900">
          {judgment.citation}
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          {judgment.court} &middot; {judgment.date}
        </p>

        <span className="mt-3 w-fit rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium tabular-nums text-slate-700">
          Similarity {judgment.similarity_score.toFixed(3)}
        </span>

        {/* Rendered as a text node, never via dangerouslySetInnerHTML (§ 10). */}
        <p className="mt-4 flex-1 whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
          {judgment.snippet}
        </p>

        <div className="mt-6 flex justify-end">
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
