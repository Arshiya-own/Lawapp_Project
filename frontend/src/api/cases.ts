/** Case-related API calls (02_frontend_spec.md § 3). */

import { request } from "./client";
import type {
  CaseDetail,
  CaseListResponse,
  DimensionsResponse,
  RetrievalResponse,
  UploadResponse,
} from "../types/api";

export function uploadCase(file: File): Promise<UploadResponse> {
  const body = new FormData();
  body.append("file", file);
  return request<UploadResponse>("/cases/upload", { method: "POST", body });
}

export function listCases(): Promise<CaseListResponse> {
  return request<CaseListResponse>("/cases");
}

export function getCase(caseId: string): Promise<CaseDetail> {
  return request<CaseDetail>(`/cases/${encodeURIComponent(caseId)}`);
}

export function generateDimensions(caseId: string): Promise<DimensionsResponse> {
  return request<DimensionsResponse>(
    `/cases/${encodeURIComponent(caseId)}/dimensions`,
    { method: "POST" },
  );
}

export function retrievePrecedents(caseId: string): Promise<RetrievalResponse> {
  return request<RetrievalResponse>(
    `/cases/${encodeURIComponent(caseId)}/retrieve`,
    { method: "POST" },
  );
}
