import { buildHeaders, readJsonSafe, toApiError } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";
import { resolveApiUrl } from "@/lib/apiBase";

export const EMPLOYEE_ONBOARDING_BASE_PATH = "/directory/employee-onboarding";

export type OnboardingChecklistAttachment = {
  attachment_id: number;
  item_id: number;
  file_url: string;
  file_comment: string | null;
  created_by: number;
  created_at: string;
};

export type OnboardingChecklistItem = {
  item_id: number;
  onboarding_id: number;
  item_code: string | null;
  title: string;
  sort_order: number;
  is_custom: boolean;
  status: "pending" | "completed" | "skipped";
  completed_at: string | null;
  completed_by_user_id: number | null;
  comment: string | null;
  due_date: string | null;
  assignee_kind: "hr" | "mentor" | "employee" | null;
  assignee_user_id: number | null;
  assignee_employee_id: number | null;
  priority: "low" | "normal" | "high" | "urgent";
  is_overdue: boolean;
  attachments: OnboardingChecklistAttachment[];
};

export type EmployeeOnboardingDetail = {
  onboarding_id: number;
  employee_id: number;
  application_id: number | null;
  status: string;
  started_at: string;
  planned_end_at: string | null;
  completed_at: string | null;
  responsible_hr_id: number;
  mentor_employee_id: number | null;
  notes: string | null;
  progress_percent: number;
  is_read_only: boolean;
  overdue_count: number;
  checklist_items: OnboardingChecklistItem[];
};

export type OnboardingTaskListItem = {
  item_id: number;
  onboarding_id: number;
  title: string;
  status: string;
  due_date: string | null;
  priority: string;
  assignee_kind: string | null;
  assignee_user_id: number | null;
  assignee_employee_id: number | null;
  assignee_name: string | null;
  employee_id: number;
  employee_full_name: string | null;
  org_unit_name: string | null;
  onboarding_status: string;
  is_overdue: boolean;
};

export type OnboardingTaskListResponse = {
  items: OnboardingTaskListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type OnboardingDashboard = {
  active_programs_count: number;
  overdue_tasks_count: number;
  due_soon_tasks_count: number;
  completion_percent: number;
  overdue_tasks: OnboardingTaskListItem[];
  due_soon_tasks: OnboardingTaskListItem[];
};

export type OnboardingTaskAuditEntry = {
  audit_id: number;
  item_id: number;
  onboarding_id: number;
  action: string;
  actor_user_id: number | null;
  actor_name: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

export type BulkOperationResult = {
  processed: number;
  succeeded: number;
  failed: number;
  items: Array<Record<string, unknown>>;
  errors: Array<{ item_id?: number; error?: string }>;
};

export type EmployeeOnboardingListItem = {
  onboarding_id: number;
  employee_id: number;
  application_id: number | null;
  status: string;
  started_at: string;
  planned_end_at: string | null;
  completed_at: string | null;
  responsible_hr_id: number;
  mentor_employee_id: number | null;
  progress_percent: number;
  employee_full_name: string | null;
  org_unit_name: string | null;
  responsible_hr_name: string | null;
  is_read_only: boolean;
};

export type EmployeeOnboardingListResponse = {
  items: EmployeeOnboardingListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type EmployeeOnboardingListFilters = {
  q?: string;
  status?: string;
  org_unit_id?: number;
  responsible_hr_id?: number;
  sort?: string;
  limit?: number;
  offset?: number;
};

export type OnboardingTaskListFilters = {
  q?: string;
  status?: string;
  org_unit_id?: number;
  assignee_user_id?: number;
  due_before?: string;
  due_after?: string;
  overdue_only?: boolean;
  limit?: number;
  offset?: number;
};

function authHeaders(json = false): Record<string, string> {
  const extra: Record<string, string> = { Accept: "application/json" };
  if (json) extra["Content-Type"] = "application/json";
  const devUserId = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  if (devUserId && (process.env.NEXT_PUBLIC_APP_ENV || "dev") !== "production") {
    extra["X-User-Id"] = devUserId;
  }
  return buildHeaders(extra) as Record<string, string>;
}

function buildQuery(filters: Record<string, string | number | boolean | undefined | null>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value == null || value === "") continue;
    params.set(key, String(value));
  }
  return params.toString();
}

export function mapEmployeeOnboardingApiError(error: unknown, fallback: string): string {
  return formatThrownError(error, fallback);
}

async function requestJson<T>(method: string, path: string, payload?: Record<string, unknown>): Promise<T> {
  const res = await fetch(resolveApiUrl(path), {
    method,
    headers: authHeaders(payload != null),
    body: payload != null ? JSON.stringify(payload) : undefined,
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method, url: path });
  return body as T;
}

export async function listEmployeeOnboardings(
  filters: EmployeeOnboardingListFilters = {},
): Promise<EmployeeOnboardingListResponse> {
  const qs = buildQuery({
    q: filters.q,
    status: filters.status,
    org_unit_id: filters.org_unit_id,
    responsible_hr_id: filters.responsible_hr_id,
    sort: filters.sort ?? "started_at_desc",
    limit: filters.limit ?? 50,
    offset: filters.offset ?? 0,
  });
  const path = qs ? `${EMPLOYEE_ONBOARDING_BASE_PATH}?${qs}` : EMPLOYEE_ONBOARDING_BASE_PATH;
  return requestJson("GET", path);
}

export async function listOnboardingTasks(
  filters: OnboardingTaskListFilters = {},
): Promise<OnboardingTaskListResponse> {
  const qs = buildQuery({
    q: filters.q,
    status: filters.status,
    org_unit_id: filters.org_unit_id,
    assignee_user_id: filters.assignee_user_id,
    due_before: filters.due_before,
    due_after: filters.due_after,
    overdue_only: filters.overdue_only,
    limit: filters.limit ?? 50,
    offset: filters.offset ?? 0,
  });
  const path = qs
    ? `${EMPLOYEE_ONBOARDING_BASE_PATH}/tasks?${qs}`
    : `${EMPLOYEE_ONBOARDING_BASE_PATH}/tasks`;
  return requestJson("GET", path);
}

export async function getOnboardingDashboard(): Promise<OnboardingDashboard> {
  return requestJson("GET", `${EMPLOYEE_ONBOARDING_BASE_PATH}/dashboard`);
}

export async function getEmployeeOnboardingByEmployeeId(
  employeeId: number,
): Promise<EmployeeOnboardingDetail> {
  return requestJson("GET", `${EMPLOYEE_ONBOARDING_BASE_PATH}/by-employee/${employeeId}`);
}

export async function getOnboardingTaskAudit(
  onboardingId: number,
  itemId: number,
): Promise<{ items: OnboardingTaskAuditEntry[] }> {
  return requestJson(
    "GET",
    `${EMPLOYEE_ONBOARDING_BASE_PATH}/${onboardingId}/checklist/${itemId}/audit`,
  );
}

async function postOnboardingAction(path: string, payload: Record<string, unknown> = {}) {
  return requestJson<EmployeeOnboardingDetail>("POST", path, payload);
}

export function completeOnboardingChecklistItem(
  onboardingId: number,
  itemId: number,
  comment?: string,
) {
  return postOnboardingAction(
    `${EMPLOYEE_ONBOARDING_BASE_PATH}/${onboardingId}/checklist/${itemId}/complete`,
    { comment: comment ?? null },
  );
}

export function skipOnboardingChecklistItem(onboardingId: number, itemId: number, comment?: string) {
  return postOnboardingAction(
    `${EMPLOYEE_ONBOARDING_BASE_PATH}/${onboardingId}/checklist/${itemId}/skip`,
    { comment: comment ?? null },
  );
}

export function updateOnboardingChecklistTask(
  onboardingId: number,
  itemId: number,
  payload: Partial<{
    due_date: string | null;
    assignee_kind: string | null;
    assignee_user_id: number | null;
    assignee_employee_id: number | null;
    priority: string | null;
    comment: string | null;
  }>,
) {
  return requestJson<EmployeeOnboardingDetail>(
    "PATCH",
    `${EMPLOYEE_ONBOARDING_BASE_PATH}/${onboardingId}/checklist/${itemId}`,
    payload,
  );
}

export function addOnboardingChecklistAttachment(
  onboardingId: number,
  itemId: number,
  fileUrl: string,
  fileComment?: string,
) {
  return postOnboardingAction(
    `${EMPLOYEE_ONBOARDING_BASE_PATH}/${onboardingId}/checklist/${itemId}/attachments`,
    { file_url: fileUrl, file_comment: fileComment ?? null },
  );
}

export function bulkAssignOnboardingTasks(payload: {
  item_ids: number[];
  assignee_kind: string;
  assignee_user_id?: number | null;
  assignee_employee_id?: number | null;
}) {
  return requestJson<BulkOperationResult>(
    "POST",
    `${EMPLOYEE_ONBOARDING_BASE_PATH}/tasks/bulk/assign`,
    payload,
  );
}

export function bulkUpdateOnboardingDueDates(payload: {
  item_ids: number[];
  due_date: string | null;
}) {
  return requestJson<BulkOperationResult>(
    "POST",
    `${EMPLOYEE_ONBOARDING_BASE_PATH}/tasks/bulk/due-date`,
    payload,
  );
}

export function bulkCompleteOnboardingTasks(payload: {
  item_ids: number[];
  comment?: string | null;
}) {
  return requestJson<BulkOperationResult>(
    "POST",
    `${EMPLOYEE_ONBOARDING_BASE_PATH}/tasks/bulk/complete`,
    payload,
  );
}

export function addCustomOnboardingChecklistItem(onboardingId: number, title: string) {
  return postOnboardingAction(`${EMPLOYEE_ONBOARDING_BASE_PATH}/${onboardingId}/checklist/custom`, {
    title,
  });
}

export function completeEmployeeOnboarding(onboardingId: number, notes?: string) {
  return postOnboardingAction(`${EMPLOYEE_ONBOARDING_BASE_PATH}/${onboardingId}/complete`, {
    notes: notes ?? null,
  });
}

export function cancelEmployeeOnboarding(onboardingId: number, reason: string) {
  return postOnboardingAction(`${EMPLOYEE_ONBOARDING_BASE_PATH}/${onboardingId}/cancel`, { reason });
}

export const ONBOARDING_STATUS_LABELS: Record<string, string> = {
  planned: "Запланирована",
  active: "В процессе",
  completed: "Завершена",
  cancelled: "Отменена",
};

export const ONBOARDING_CHECKLIST_STATUS_LABELS: Record<string, string> = {
  pending: "Ожидает",
  completed: "Выполнено",
  skipped: "Пропущено",
};

export const ONBOARDING_PRIORITY_LABELS: Record<string, string> = {
  low: "Низкий",
  normal: "Обычный",
  high: "Высокий",
  urgent: "Срочный",
};

export const ONBOARDING_ASSIGNEE_LABELS: Record<string, string> = {
  hr: "HR",
  mentor: "Наставник",
  employee: "Сотрудник",
};

export const ONBOARDING_TASK_AUDIT_LABELS: Record<string, string> = {
  created: "Создана",
  updated: "Обновлена",
  assignee_changed: "Изменён ответственный",
  due_date_changed: "Изменён срок",
  priority_changed: "Изменён приоритет",
  comment_changed: "Изменён комментарий",
  attachment_added: "Добавлено вложение",
  completed: "Выполнена",
  skipped: "Пропущена",
};

export function onboardingStatusLabel(status: string | null | undefined): string {
  const key = String(status || "").trim();
  return ONBOARDING_STATUS_LABELS[key] || key || "—";
}

export function onboardingChecklistStatusLabel(status: string | null | undefined): string {
  const key = String(status || "").trim();
  return ONBOARDING_CHECKLIST_STATUS_LABELS[key] || key || "—";
}

export function onboardingPriorityLabel(priority: string | null | undefined): string {
  const key = String(priority || "").trim();
  return ONBOARDING_PRIORITY_LABELS[key] || key || "—";
}

export function onboardingAssigneeLabel(kind: string | null | undefined): string {
  const key = String(kind || "").trim();
  return ONBOARDING_ASSIGNEE_LABELS[key] || key || "—";
}

export function onboardingTaskAuditLabel(action: string | null | undefined): string {
  const key = String(action || "").trim();
  return ONBOARDING_TASK_AUDIT_LABELS[key] || key || "—";
}

export function formatDueDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("ru-RU");
}
