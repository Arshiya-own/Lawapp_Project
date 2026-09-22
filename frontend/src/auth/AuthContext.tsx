/**
 * Auth state (02_frontend_spec.md § 2: React Context).
 *
 * The token is held in React state and mirrored into the api client — never in
 * `localStorage`, which § 10 forbids. The trade-off is deliberate: a refresh signs the
 * user out. That is the behaviour the spec asks for, and with a 60-minute expiry and
 * the OAuth redirect doing the work, signing back in is one click.
 *
 * The backend's callback redirects to the frontend with `?token=...` (03_backend_spec.md
 * § 5.1). We read it, then strip it from the URL so the token does not linger in the
 * address bar, history, or any link the user copies.
 */

import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { getCurrentUser, logout as logoutRequest } from "../api/auth";
import { setAuthToken, setUnauthorizedHandler } from "../api/client";
import type { User } from "../types/api";

export interface AuthState {
  user: User | null;
  token: string | null;
  status: "loading" | "authenticated" | "anonymous";
  signIn: (token: string) => Promise<void>;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthState | null>(null);

function readTokenFromUrl(): string | null {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");
  if (!token) return null;

  params.delete("token");
  const query = params.toString();
  window.history.replaceState(
    {},
    "",
    `${window.location.pathname}${query ? `?${query}` : ""}`,
  );
  return token;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>("loading");

  const signIn = useCallback(async (nextToken: string) => {
    setAuthToken(nextToken);
    setToken(nextToken);
    try {
      setUser(await getCurrentUser());
      setStatus("authenticated");
    } catch {
      setAuthToken(null);
      setToken(null);
      setUser(null);
      setStatus("anonymous");
      throw new Error("Sign-in failed. Please try again.");
    }
  }, []);

  const signOut = useCallback(async () => {
    try {
      await logoutRequest();
    } catch {
      // Sessions are stateless, so a failed call does not keep the user signed in.
    }
    setAuthToken(null);
    setToken(null);
    setUser(null);
    setStatus("anonymous");
  }, []);

  useEffect(() => {
    const fromUrl = readTokenFromUrl();
    if (!fromUrl) {
      setStatus("anonymous");
      return;
    }
    void signIn(fromUrl).catch(() => undefined);
  }, [signIn]);

  useEffect(() => {
    // Any 401 mid-session drops straight back to anonymous; ProtectedRoute then
    // redirects to /login (§ 11).
    setUnauthorizedHandler(() => {
      setAuthToken(null);
      setToken(null);
      setUser(null);
      setStatus("anonymous");
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({ user, token, status, signIn, signOut }),
    [user, token, status, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
