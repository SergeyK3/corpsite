import { apiFetchJson } from "@/lib/api";

export type TestPersonnelReasonCode =
  | "LEGACY_SYNTHETIC_TEST_DATA"
  | "PROVENANCE_TEST_RUN_CLEANUP"
  | "DUPLICATE_SYNTHETIC_FIXTURE"
  | "OTHER_APPROVED_TEST_DATA";

export type TestPersonnelStageAdmissibility = {
  create: boolean;
  submit: boolean;
  approve: boolean;
  future_execution: boolean;
};

export type TestPersonnelTarget = {
  target_type: "APPLICANT";
  person_id: number;
  application_id: number;
  subject: string;
  masked_iin: string | null;
  eligibility_status: string;
  stage_admissibility?: TestPersonnelStageAdmissibility;
  blocking_codes: string[];
  tombstone_required_codes: string[];
  hr_attestation_codes: string[];
  informational_codes: string[];
  relationship_summary?: Record<string, RelationshipSummary>;
  relationship_fingerprint?: string;
  manifest_order?: number;
  requires_hr_synthetic_confirmation?: boolean;
  has_test_provenance?: boolean;
};

export type RelationshipSummary = {
  category: string;
  count: number;
  state_digest: string;
  create_allowed: boolean;
  submit_allowed: boolean;
  approval_allowed: boolean;
  future_execution_allowed: boolean;
  required_hr_decision?: string | null;
};

export type TestPersonnelDecision = {
  decision_id: number;
  decision: "APPROVE" | "REJECT";
  actor_user_id: number;
  actor_display_name?: string;
  comment?: string | null;
  submitted_synthetic_confirmed: boolean;
  decided_at: string;
};

export type TestPersonnelRequest = {
  request_id: string;
  request_number: string;
  status: string;
  stored_status?: string;
  version: number;
  reason_code: TestPersonnelReasonCode;
  basis: string;
  initiated_by_user_id: number;
  initiated_by_display_name?: string;
  target_set_hash: string;
  relationship_fingerprint: string;
  created_at: string;
  submitted_at?: string | null;
  expires_at?: string | null;
  approved_at?: string | null;
  approval_expires_at?: string | null;
  approval_valid?: boolean;
  targets?: TestPersonnelTarget[];
  decisions?: TestPersonnelDecision[];
  result_code?: string;
};

export type TestPersonnelApiError = Error & {
  status?: number;
  code?: string;
  details?: unknown;
};

export const REASON_OPTIONS: ReadonlyArray<{ value: TestPersonnelReasonCode; label: string }> = [
  { value: "LEGACY_SYNTHETIC_TEST_DATA", label: "Устаревшие синтетические тестовые данные" },
  { value: "PROVENANCE_TEST_RUN_CLEANUP", label: "Очистка результатов тестового прогона" },
  { value: "DUPLICATE_SYNTHETIC_FIXTURE", label: "Дубликат синтетической фикстуры" },
  { value: "OTHER_APPROVED_TEST_DATA", label: "Иные подтверждённые тестовые данные" },
];

export function newIdempotencyKey(action: string): string {
  const random = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `wp-td-003-${action}-${random}`;
}

export function stableIdempotencyKey(
  registry: Map<string, string>,
  action: string,
  commandSignature: string,
): string {
  const registryKey = `${action}:${commandSignature}`;
  const existing = registry.get(registryKey);
  if (existing) return existing;
  const created = newIdempotencyKey(action);
  registry.set(registryKey, created);
  return created;
}

export function forgetIdempotencyKey(
  registry: Map<string, string>,
  action: string,
  commandSignature: string,
): void {
  registry.delete(`${action}:${commandSignature}`);
}

export function testPersonnelErrorStatus(error: unknown): number {
  return Number((error as TestPersonnelApiError | null)?.status ?? 0);
}

export function previewTestPersonnel(mask: string): Promise<{ items: TestPersonnelTarget[]; count: number }> {
  return apiFetchJson("/directory/test-personnel-deletion/preview", {
    method: "POST",
    body: { field: "full_name", mask },
  });
}

export function createTestPersonnelDeletionRequest(input: {
  reason_code: TestPersonnelReasonCode;
  original_mask: string;
  targets: Array<{ person_id: number; application_id: number }>;
  idempotency_key: string;
}): Promise<TestPersonnelRequest> {
  return apiFetchJson("/directory/test-personnel-deletion/requests", {
    method: "POST",
    body: {
      basis: "LEGACY_MANIFEST",
      reason_code: input.reason_code,
      search_field: "full_name",
      original_mask: input.original_mask,
      targets: input.targets,
      idempotency_key: input.idempotency_key,
    },
  });
}

export async function listTestPersonnelDeletionRequests(): Promise<TestPersonnelRequest[]> {
  const response = await apiFetchJson<{ items: TestPersonnelRequest[] }>(
    "/directory/test-personnel-deletion/requests",
  );
  return response.items ?? [];
}

export function getTestPersonnelDeletionRequest(requestId: string): Promise<TestPersonnelRequest> {
  return apiFetchJson(`/directory/test-personnel-deletion/requests/${encodeURIComponent(requestId)}`);
}

export function submitTestPersonnelDeletionRequest(
  requestId: string,
  version: number,
  idempotencyKey: string,
): Promise<TestPersonnelRequest> {
  return apiFetchJson(`/directory/test-personnel-deletion/requests/${encodeURIComponent(requestId)}/submit`, {
    method: "POST",
    body: { expected_version: version, idempotency_key: idempotencyKey },
  });
}

export function cancelTestPersonnelDeletionRequest(
  requestId: string,
  version: number,
  idempotencyKey: string,
): Promise<TestPersonnelRequest> {
  return apiFetchJson(`/directory/test-personnel-deletion/requests/${encodeURIComponent(requestId)}/cancel`, {
    method: "POST",
    body: { expected_version: version, idempotency_key: idempotencyKey },
  });
}

export async function listTestPersonnelDeletionApprovals(): Promise<TestPersonnelRequest[]> {
  const response = await apiFetchJson<{ items: TestPersonnelRequest[] }>(
    "/directory/test-personnel-deletion/approvals",
  );
  return response.items ?? [];
}

export function getTestPersonnelDeletionApproval(requestId: string): Promise<TestPersonnelRequest> {
  return apiFetchJson(`/directory/test-personnel-deletion/approvals/${encodeURIComponent(requestId)}`);
}

function decideTestPersonnelDeletionRequest(
  requestId: string,
  action: "approve" | "reject",
  input: {
    version: number;
    idempotencyKey: string;
    comment?: string;
    submittedSyntheticConfirmed: boolean;
  },
): Promise<TestPersonnelRequest> {
  return apiFetchJson(
    `/directory/test-personnel-deletion/approvals/${encodeURIComponent(requestId)}/${action}`,
    {
      method: "POST",
      body: {
        expected_version: input.version,
        idempotency_key: input.idempotencyKey,
        comment: input.comment?.trim() || undefined,
        submitted_synthetic_confirmed: input.submittedSyntheticConfirmed,
      },
    },
  );
}

export function approveTestPersonnelDeletionRequest(
  requestId: string,
  input: Parameters<typeof decideTestPersonnelDeletionRequest>[2],
): Promise<TestPersonnelRequest> {
  return decideTestPersonnelDeletionRequest(requestId, "approve", input);
}

export function rejectTestPersonnelDeletionRequest(
  requestId: string,
  input: Parameters<typeof decideTestPersonnelDeletionRequest>[2],
): Promise<TestPersonnelRequest> {
  return decideTestPersonnelDeletionRequest(requestId, "reject", input);
}

export function testPersonnelErrorMessage(error: unknown): string {
  const apiError = error as TestPersonnelApiError;
  const status = testPersonnelErrorStatus(error);
  const details = apiError?.details as { detail?: { code?: string } } | undefined;
  const code = String(apiError?.code ?? details?.detail?.code ?? "");
  if (status === 403) return "Недостаточно прав для выполнения операции.";
  if (status === 409) {
    if (code.includes("ATTESTATION")) return "Подтвердите синтетический характер отправленных анкет.";
    return "Данные запроса изменились. Обновите сведения и повторите действие.";
  }
  if (status === 410) return "Операция отключена политикой безопасного удаления.";
  if (status === 422) return "Проверьте заполнение полей и выбранные записи.";
  if (status === 0) return "Не удалось связаться с сервером. Проверьте доступность сервиса и повторите попытку.";
  return "Не удалось выполнить операцию. Повторите попытку или обратитесь к администратору.";
}
