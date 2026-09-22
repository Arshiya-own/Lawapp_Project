/**
 * Router + providers (02_frontend_spec.md § 3, § 4).
 *
 * Exactly three routes: /login, /, /cases/:caseId. Unauthenticated access to the two
 * protected routes redirects to /login, carrying `returnTo` so the user lands back
 * where they were after signing in (§ 4).
 */

import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { AuthProvider } from "./auth/AuthContext";
import { useAuth } from "./auth/useAuth";
import { LoginPage } from "./pages/LoginPage";
import { ResultsPage } from "./pages/ResultsPage";
import { UploadPage } from "./pages/UploadPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <span
          aria-hidden="true"
          className="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600"
        />
        <span className="sr-only">Loading</span>
      </div>
    );
  }

  if (status !== "authenticated") {
    const returnTo = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?returnTo=${encodeURIComponent(returnTo)}`} replace />;
  }

  return <>{children}</>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <UploadPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cases/:caseId"
            element={
              <ProtectedRoute>
                <ResultsPage />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </QueryClientProvider>
  );
}
