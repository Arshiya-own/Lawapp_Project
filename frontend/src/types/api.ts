/**
 * Types mirroring the backend contract (03_backend_spec.md § 6).
 *
 * Field names are snake_case here deliberately: they are the wire format, and
 * renaming them on the way in would make it harder to check the client against the
 * spec. Component props use camelCase, and the mapping happens at that boundary.
 */

export type Jurisdiction =
  | "Criminal"
  | "Civil"
  | "Constitutional"
  | "Commercial"
  | "Other";

export type CaseStatus = "processing" | "processed";

export interface Metadata {
  parties: string;
  court: string;
  jurisdiction: Jurisdiction;
  sections_invoked: string[];
  synopsis: string;
}

export interface Dimension {
  dimension_number: number;
  query: string;
  rationale: string;
}

export interface RankedJudgment {
  judgment_id: string;
  citation: string;
  case_name: string;
  court: string;
  /** 1 = Supreme Court, 2 = same-state HC, 3 = other HC. */
  court_tier: number;
  /** ISO date, YYYY-MM-DD. */
  date: string;
  chunk_id: string;
  snippet: string;
  /** Already rounded to 3 decimals by the backend (§ 5.4). */
  similarity_score: number;
}

export interface DimensionResult {
  dimension_number: number;
  query: string;
  judgments: RankedJudgment[];
}

export interface User {
  user_id: string;
  email: string;
  name: string;
  picture: string;
  created_at: string;
}

export interface UploadResponse {
  case_id: string;
  status: CaseStatus;
  uploaded_at: string;
}

export interface CaseDetail {
  case_id: string;
  user_id: string;
  status: CaseStatus;
  metadata: Metadata | null;
  dimensions: Dimension[] | null;
  retrieval: DimensionResult[] | null;
  uploaded_at: string;
  processed_at: string | null;
}

export interface CaseListItem {
  case_id: string;
  parties: string;
  uploaded_at: string;
}

export interface CaseListResponse {
  cases: CaseListItem[];
}

export interface DimensionsResponse {
  case_id: string;
  dimensions: Dimension[];
  generated_at: string;
}

export interface RetrievalResponse {
  case_id: string;
  results: DimensionResult[];
  retrieved_at: string;
}

export interface AuthorizeResponse {
  authorize_url: string;
}

/** Every backend error uses this envelope (03_backend_spec.md § 4). */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}
