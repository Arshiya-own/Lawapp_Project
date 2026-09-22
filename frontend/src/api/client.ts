/**
 * fetch wrapper with auth header (02_frontend_spec.md § 3).
 *
 * The bearer token lives in a module-level variable, not `localStorage` — § 10 forbids
 * persisting it, so a page reload deliberately ends the session and the user signs in
 * again. `AuthContext` owns the value; this module only holds the copy that outgoing
 * requests read.
 */

import type { ApiErrorBody } from "../types/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

let authToken: string | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
}

export function getAuthToken(): string | null {
  return authToken;
}

/** Thrown for any non-2xx response, carrying the § 4 envelope's code. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string,
              details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/** Set by AuthContext so a 401 anywhere can drop the session and bounce to /login. */
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

async function toApiError(response: Response): Promise<ApiError> {
  let code = "internal_error";
  let message = "Something went wrong on our side. Please try again.";
  let details: Record<string, unknown> = {};

  try {
    const body = (await response.json()) as ApiErrorBody;
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
      details = body.error.details ?? {};
    }
  } catch {
    // Non-JSON error body (a proxy timeout, say) — the defaults above stand.
  }
  return new ApiError(response.status, code, message, details);
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (authToken) headers.set("Authorization", `Bearer ${authToken}`);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });

  if (response.status === 401) {
    onUnauthorized?.();
    throw await toApiError(response);
  }
  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;

  return (await response.json()) as T;
}

export const apiBaseUrl = BASE_URL;
