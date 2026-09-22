/** 02_frontend_spec.md § 6.1 — 64px, sticky top, wordmark left, user + sign out right. */

import { Link } from "react-router-dom";

import { useAuth } from "../auth/useAuth";

export function Header() {
  const { user, signOut } = useAuth();

  return (
    <header className="sticky top-0 z-20 h-header border-b border-slate-200 bg-white">
      <div className="mx-auto flex h-full max-w-content items-center justify-between px-4">
        <Link
          to="/"
          className="rounded text-lg font-semibold tracking-tight text-slate-900"
        >
          JuriNex
        </Link>

        {user && (
          <div className="flex items-center gap-3">
            {user.picture ? (
              <img
                src={user.picture}
                alt=""
                className="h-8 w-8 rounded-full border border-slate-200"
              />
            ) : (
              <span
                aria-hidden="true"
                className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-200 text-sm font-medium text-slate-600"
              >
                {user.email.charAt(0).toUpperCase()}
              </span>
            )}
            <span className="hidden text-sm text-slate-600 sm:inline">
              {user.email}
            </span>
            <button
              type="button"
              onClick={() => void signOut()}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
