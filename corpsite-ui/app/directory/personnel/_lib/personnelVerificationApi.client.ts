/** Personnel employment verification API client (WP-VER-005A/B). */

import { buildHeaders, readJsonSafe, toApiError } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";
import { formatThrownError } from "@/lib/i18n";

export const EMPLOYMENT_VERIFICATION_BASE_PATH =
  "/directory/personnel/employment-verification";

export type VerificationTaskResponse = {
  task_id: number;
  person_id: number;
  control_point: string;
  object_type: string;
  object_id: number;
  object_version_id: number;
  policy_id: number;
  policy_version: number;
  status: string;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
  prior_updated_at: string | null;
};

export type EmploymentPendingTaskListResponse = {
  items: VerificationTaskResponse[];
  count: number;
};

export type EmploymentRecordSnapshot = {
  employment_id: number;
  record_kind: string;
  employer_name: string | null;
  department_name: string | null;
  position_title: string | null;
  employment_type: string | null;
  started_at: string | null;
  ended_at: string | null;
  termination_reason: string | null;
  document_reference: string | null;
  notes: string | null;
  lifecycle_status: string;
  updated_at: string | null;
};

export type EmploymentTaskReviewResponse = {
  task: VerificationTaskResponse;
  person_id: number;
  person_full_name: string;
  prior: EmploymentRecordSnapshot;
  revision: EmploymentRecordSnapshot;
  verification_state: string;
};

export type EmploymentRevisionDecisionResponse = {
  task: VerificationTaskResponse;
  attestation: {
    attestation_id: number;
    decision: string;
    decided_at: string;
    comment: string | null;
  };
  prior_employment_id: number;
  revision_employment_id: number;
  prior_lifecycle_status: string;
  revision_lifecycle_status: string;
};

export type VerificationApiErrorKind = "forbidden" | "not_found" | "conflict" | "other";

export class VerificationApiError extends Error {
  readonly kind: VerificationApiErrorKind;
  readonly status: number;

  constructor(kind: VerificationApiErrorKind, status: number, message: string) {
    super(message);
    this.name = "VerificationApiError";
    this.kind = kind;
    this.status = status;
  }
}

function getDevUserId(): string | null {
  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
  if (appEnv === "prod" || appEnv === "production") return null;
  const v = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  return v ? v : null;
}

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const devUserId = getDevUserId();
  if (devUserId) headers["X-User-Id"] = devUserId;
  return buildHeaders(headers) as Record<string, string>;
}

function isRawBackendConflictDetail(detail: string | null): boolean {
  if (!detail) return false;
  // Hide technical service messages from HR UI (e.g. "Task 1 is not pending...").
  return /task\s+\d+\s+is\s+not\s+pending/i.test(detail) || /\bstatus\s*=\s*'/i.test(detail);
}

function messageForStatus(status: number, detail: string | null): string {
  if (status === 403) {
    return "Недостаточно прав для проверки трудовой биографии.";
  }
  if (status === 404) {
    return detail?.trim() || "Задание или запись не найдены.";
  }
  if (status === 409) {
    if (detail?.trim() && !isRawBackendConflictDetail(detail)) {
      return detail.trim();
    }
    return "Конфликт данных: задание уже обработано или запись изменилась. Обновите очередь.";
  }
  return detail?.trim() || `Ошибка запроса (HTTP ${status}).`;
}

function extractDetail(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  return null;
}

function kindForStatus(status: number): VerificationApiErrorKind {
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  return "other";
}

async function verificationFetchJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const method = (init?.method || "GET").toUpperCase();
  const res = await fetch(resolveApiUrl(path), {
    ...init,
    method,
    headers: {
      ...authHeaders(),
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) {
    const detail = extractDetail(body);
    const message = messageForStatus(res.status, detail);
    if (res.status === 403 || res.status === 404 || res.status === 409) {
      throw new VerificationApiError(kindForStatus(res.status), res.status, message);
    }
    throw toApiError(res.status, body, { method, url: path });
  }
  return body as T;
}

export function mapPersonnelVerificationApiError(
  e: unknown,
  fallback = "Не удалось выполнить запрос.",
): string {
  if (e instanceof VerificationApiError) return e.message;
  return formatThrownError(e, { fallback });
}

export function verificationErrorKind(e: unknown): VerificationApiErrorKind {
  if (e instanceof VerificationApiError) return e.kind;
  return "other";
}

export async function listPendingEmploymentTasks(opts?: {
  personId?: number;
  limit?: number;
  signal?: AbortSignal;
}): Promise<EmploymentPendingTaskListResponse> {
  const params = new URLSearchParams();
  if (opts?.personId != null) params.set("person_id", String(opts.personId));
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  const qs = params.toString();
  const path = qs
    ? `/api/personnel-verification/employment/pending-tasks?${qs}`
    : "/api/personnel-verification/employment/pending-tasks";
  return verificationFetchJson<EmploymentPendingTaskListResponse>(path, {
    method: "GET",
    signal: opts?.signal,
  });
}

export async function getEmploymentTaskReview(
  taskId: number,
  opts?: { signal?: AbortSignal },
): Promise<EmploymentTaskReviewResponse> {
  return verificationFetchJson<EmploymentTaskReviewResponse>(
    `/api/personnel-verification/employment/tasks/${encodeURIComponent(String(taskId))}/review`,
    { method: "GET", signal: opts?.signal },
  );
}

export async function confirmEmploymentTask(
  taskId: number,
  body: { expected_prior_updated_at: string; comment?: string | null },
): Promise<EmploymentRevisionDecisionResponse> {
  return verificationFetchJson<EmploymentRevisionDecisionResponse>(
    `/api/personnel-verification/employment/tasks/${encodeURIComponent(String(taskId))}/confirm`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

export async function rejectEmploymentTask(
  taskId: number,
  body: { expected_prior_updated_at: string; comment?: string | null },
): Promise<EmploymentRevisionDecisionResponse> {
  return verificationFetchJson<EmploymentRevisionDecisionResponse>(
    `/api/personnel-verification/employment/tasks/${encodeURIComponent(String(taskId))}/reject`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}
