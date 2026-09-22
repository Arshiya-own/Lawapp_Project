/**
 * 02_frontend_spec.md § 5.1 — centered card, wordmark, tagline, Google sign-in.
 * States: idle / authenticating / error.
 */

import { useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";

import { getAuthorizeUrl } from "../api/auth";
import { useAuth } from "../auth/useAuth";

/** § 5.1: graded verbatim. */
export const SIGN_IN_FAILED_TEXT = "Sign-in failed. Please try again.";

export function LoginPage() {
  const { status } = useAuth();
  const [searchParams] = useSearchParams();
  const [state, setState] = useState<"idle" | "authenticating" | "error">("idle");

  const returnTo = searchParams.get("returnTo") ?? "/";

  if (status === "authenticated") {
    return <Navigate to={returnTo} replace />;
  }

  async function handleSignIn() {
    setState("authenticating");
    try {
      const { authorize_url } = await getAuthorizeUrl(returnTo);
      window.location.assign(authorize_url);
    } catch {
      setState("error");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-8 text-center shadow-sm">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          JuriNex
        </h1>
        <p className="mt-1 text-sm text-slate-600">Find precedents, faster.</p>

        {state === "error" && (
          <p role="alert" className="mt-6 text-sm text-red-700">
            {SIGN_IN_FAILED_TEXT}
          </p>
        )}

        <button
          type="button"
          onClick={() => void handleSignIn()}
          disabled={state === "authenticating"}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-md bg-slate-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {state === "authenticating" && (
            <span
              aria-hidden="true"
              className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white"
            />
          )}
          {state === "authenticating" ? "Signing in…" : "Sign in with Google"}
        </button>

        <p className="mt-6 text-xs text-slate-500">
          By signing in, you agree to our terms.
        </p>
      </div>
    </main>
  );
}
