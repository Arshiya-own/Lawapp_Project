/** Auth-related API calls (02_frontend_spec.md § 3). */

import { request } from "./client";
import type { AuthorizeResponse, User } from "../types/api";

export function getAuthorizeUrl(returnTo: string): Promise<AuthorizeResponse> {
  return request<AuthorizeResponse>(
    `/auth/google/authorize?return_to=${encodeURIComponent(returnTo)}`,
  );
}

export function getCurrentUser(): Promise<User> {
  return request<User>("/auth/me");
}

export function logout(): Promise<unknown> {
  return request("/auth/logout", { method: "POST" });
}
