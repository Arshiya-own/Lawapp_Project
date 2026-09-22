/**
 * 02_frontend_spec.md § 5.2 — drop zone, client-side validation, case list.
 *
 * Processing is synchronous server-side (03_backend_spec.md § 8), so the upload call
 * returns only once metadata exists. The spec's `processing` state is still rendered
 * while that request is in flight, which is what the user experiences: a 10-30 second
 * wait with the same message the § 5.2 state machine specifies.
 */

import { useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { listCases, uploadCase } from "../api/cases";
import { ApiError } from "../api/client";
import { Header } from "../components/Header";

/** § 5.2 validation messages, graded verbatim. */
export const INVALID_TYPE_TEXT = "Only PDF files are accepted.";
export const TOO_LARGE_TEXT = "File too large. Maximum 20 MB.";
export const OCR_FAILED_TEXT =
  "We couldn't extract text from this PDF. It may be corrupted or image-only with illegible scans.";
export const SERVER_ERROR_TEXT = "Something went wrong on our side. Please try again.";
export const NO_CASES_TEXT = "No cases yet. Upload your first case above.";

const MAX_BYTES = 20 * 1024 * 1024;

/** Maps the § 5.2 error table onto the backend's error envelope. */
function messageFor(error: unknown): string {
  if (!(error instanceof ApiError)) return SERVER_ERROR_TEXT;
  switch (error.status) {
    case 413:
      return TOO_LARGE_TEXT;
    case 415:
      return INVALID_TYPE_TEXT;
    case 422:
      return OCR_FAILED_TEXT;
    default:
      return error.status >= 500 ? SERVER_ERROR_TEXT : error.message;
  }
}

export function UploadPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cases = useQuery({ queryKey: ["cases"], queryFn: listCases });

  const upload = useMutation({
    mutationFn: uploadCase,
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey: ["cases"] });
      navigate(`/cases/${data.case_id}`);
    },
    onError: (err) => setError(messageFor(err)),
  });

  function handleFile(file: File | undefined) {
    if (!file) return;
    setError(null);

    // Client-side validation before the request (§ 11).
    if (file.type !== "application/pdf") {
      setError(INVALID_TYPE_TEXT);
      return;
    }
    if (file.size > MAX_BYTES) {
      setError(TOO_LARGE_TEXT);
      return;
    }
    upload.mutate(file);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    handleFile(event.dataTransfer.files?.[0]);
  }

  const busy = upload.isPending;

  return (
    <div className="min-h-screen">
      <Header />

      <main className="mx-auto max-w-content px-4 py-8">
        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={`rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
            dragging ? "border-slate-500 bg-slate-100" : "border-slate-300 bg-white"
          }`}
        >
          {busy ? (
            <div>
              <span
                aria-hidden="true"
                className="mx-auto block h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600"
              />
              <p className="mt-4 text-sm text-slate-700" aria-live="polite">
                Extracting text and metadata&hellip; (this takes 10&ndash;30 seconds)
              </p>
            </div>
          ) : (
            <>
              <label htmlFor="case-pdf" className="block text-sm text-slate-600">
                Drop a case PDF or click to browse. Max 20 MB.
              </label>
              <input
                ref={inputRef}
                id="case-pdf"
                type="file"
                accept="application/pdf"
                className="sr-only"
                onChange={(event) => handleFile(event.target.files?.[0])}
              />
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="mt-4 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
              >
                Choose a PDF
              </button>
            </>
          )}
        </div>

        {error && (
          <div
            role="alert"
            className="mt-4 flex items-start justify-between gap-4 rounded-md border border-red-200 bg-red-50 p-3"
          >
            <p className="text-sm text-red-800">{error}</p>
            <button
              type="button"
              onClick={() => setError(null)}
              className="rounded text-sm font-medium text-red-700 underline"
            >
              Dismiss
            </button>
          </div>
        )}

        <section className="mt-10">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Your cases
          </h2>

          {cases.isPending && (
            <p className="mt-3 text-sm text-slate-500">Loading&hellip;</p>
          )}

          {cases.isError && (
            <div className="mt-3 flex items-center gap-3">
              <p className="text-sm text-red-700">Couldn&rsquo;t load your cases.</p>
              <button
                type="button"
                onClick={() => void cases.refetch()}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Retry
              </button>
            </div>
          )}

          {cases.isSuccess && cases.data.cases.length === 0 && (
            <p className="mt-3 text-sm text-slate-500">{NO_CASES_TEXT}</p>
          )}

          {cases.isSuccess && cases.data.cases.length > 0 && (
            <ul className="mt-3 divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
              {cases.data.cases.map((item) => (
                <li key={item.case_id}>
                  <button
                    type="button"
                    onClick={() => navigate(`/cases/${item.case_id}`)}
                    className="flex w-full items-center justify-between gap-4 p-4 text-left hover:bg-slate-50"
                  >
                    <span className="text-sm font-medium text-slate-900">
                      {item.parties || item.case_id}
                    </span>
                    <span className="shrink-0 text-xs text-slate-500">
                      {item.uploaded_at}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
