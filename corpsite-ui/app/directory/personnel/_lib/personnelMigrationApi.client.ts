// PMF-4B / PMF-4C — Personnel Migration Framework API client.
import { buildHeaders } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";
import { resolveApiUrl } from "@/lib/apiBase";

export type MigrationDomainRow = {
  domain_code: string;
  display_name: string;
  description: string | null;
  is_enabled: boolean;
  target_table_names: string[];
  control_list_columns: string[];
  created_at: string | null;
  updated_at: string | null;
};

export type MigrationDomainListResponse = {
  items: MigrationDomainRow[];
};

export type MigrationRunItem = {
  item_id: number;
  run_id: number;
  domain_code: string;
  source_kind: string;
  source_record_id: string | null;
  import_batch_id: number | null;
  import_row_id: number | null;
  record_kind: string | null;
  target_table_name: string | null;
  target_record_id: number | null;
  item_status: string;
  draft_payload: Record<string, unknown>;
  source_payload: Record<string, unknown>;
  validation_errors: unknown[];
  created_at: string | null;
  committed_at: string | null;
  voided_at: string | null;
  void_reason: string | null;
};

export type MigrationRun = {
  run_id: number;
  domain_code: string;
  employee_context_id: number | null;
  person_id: number | null;
  run_status: string;
  started_at: string | null;
  committed_at: string | null;
  voided_at: string | null;
  started_by: string | null;
  committed_by: string | null;
  voided_by: string | null;
  void_reason: string | null;
  metadata: Record<string, unknown>;
  items: MigrationRunItem[];
};

export type CreateDraftRunPayload = {
  domain_code: string;
  employee_context_id: number;
  metadata?: Record<string, unknown>;
};

export type CreateDraftRunResponse = {
  run: MigrationRun;
};

export type AddMigrationDraftItemPayload = {
  source_kind: string;
  source_record_id?: string | null;
  import_batch_id?: number | null;
  import_row_id?: number | null;
  record_kind?: string | null;
  draft_payload?: Record<string, unknown>;
  source_payload?: Record<string, unknown>;
};

export type AddMigrationDraftItemResponse = {
  item: MigrationRunItem;
  run: MigrationRun;
};

export type CommittedMigrationItem = {
  item_id: number;
  target_table_name: string;
  target_record_id: number;
  event_id: number;
};

export type CommitMigrationRunResponse = {
  run: MigrationRun;
  committed_items: CommittedMigrationItem[];
  event_ids: number[];
};

function getDevUserId(): string | null {
  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
  if (appEnv === "prod" || appEnv === "production") return null;
  const v = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  return v ? v : null;
}

function authHeaders(): Record<string, string> {
  const extra: Record<string, string> = { Accept: "application/json" };
  const devUserId = getDevUserId();
  if (devUserId) extra["X-User-Id"] = devUserId;
  return buildHeaders(extra) as Record<string, string>;
}

export class PersonnelMigrationForbiddenError extends Error {
  constructor(message = "Недостаточно прав для миграции кадровых данных.") {
    super(message);
    this.name = "PersonnelMigrationForbiddenError";
  }
}

function parseErrorBody(status: number, body: string, fallback: string): Error {
  if (status === 403) {
    return new PersonnelMigrationForbiddenError();
  }
  const trimmed = body.trim();
  if (trimmed.startsWith("{")) {
    try {
      const parsed = JSON.parse(trimmed) as { detail?: unknown };
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        return new Error(parsed.detail.trim());
      }
    } catch {
      // keep raw body fallback
    }
  }
  return new Error(trimmed || fallback || `HTTP ${status}`);
}

export function mapPersonnelMigrationApiError(e: unknown, fallback = "Ошибка запроса."): string {
  if (e instanceof PersonnelMigrationForbiddenError) {
    return e.message;
  }
  return formatThrownError(e, { fallback });
}

export function isPersonnelMigrationForbiddenError(e: unknown): e is PersonnelMigrationForbiddenError {
  return e instanceof PersonnelMigrationForbiddenError;
}

/** PMF-4C — 422 when employees.person_id is missing at draft create. */
export function isMigrationPersonRequiredError(e: unknown): boolean {
  if (!(e instanceof Error)) return false;
  const msg = e.message.trim().toLowerCase();
  return msg.includes("person_id") || msg.includes("person link") || msg.includes("привязк");
}

async function apiGetJson<T>(path: string): Promise<T> {
  const url = resolveApiUrl(path);
  const res = await fetch(url, { method: "GET", headers: authHeaders(), cache: "no-store" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw parseErrorBody(res.status, body, "Не удалось загрузить данные.");
  }
  return res.json() as Promise<T>;
}

async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  const url = resolveApiUrl(path);
  const res = await fetch(url, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw parseErrorBody(res.status, text, "Не удалось выполнить запрос.");
  }
  return res.json() as Promise<T>;
}

/** PMF-3A — create draft migration run. */
export async function createDraftRun(payload: CreateDraftRunPayload): Promise<MigrationRun> {
  const response = await apiPostJson<CreateDraftRunResponse>("/personnel-migration/runs/draft", {
    domain_code: payload.domain_code,
    employee_context_id: payload.employee_context_id,
    metadata: payload.metadata ?? {},
  });
  return response.run;
}

/** PMF-3A — fetch migration run with items. */
export async function getMigrationRun(runId: number): Promise<MigrationRun> {
  return apiGetJson<MigrationRun>(`/personnel-migration/runs/${encodeURIComponent(String(runId))}`);
}

/** PMF-3B — list registered migration domain plugins. */
export async function listMigrationDomains(): Promise<MigrationDomainListResponse> {
  return apiGetJson<MigrationDomainListResponse>("/personnel-migration/domains");
}

/** PMF-3B — add draft item to an existing migration run. */
export async function addMigrationDraftItem(
  runId: number,
  payload: AddMigrationDraftItemPayload,
): Promise<AddMigrationDraftItemResponse> {
  return apiPostJson<AddMigrationDraftItemResponse>(
    `/personnel-migration/runs/${encodeURIComponent(String(runId))}/items`,
    {
      source_kind: payload.source_kind,
      source_record_id: payload.source_record_id ?? null,
      import_batch_id: payload.import_batch_id ?? null,
      import_row_id: payload.import_row_id ?? null,
      record_kind: payload.record_kind ?? null,
      draft_payload: payload.draft_payload ?? {},
      source_payload: payload.source_payload ?? {},
    },
  );
}

/** PMF-3B / PMF-4E — commit draft migration run. */
export async function commitMigrationRun(runId: number): Promise<CommitMigrationRunResponse> {
  return apiPostJson<CommitMigrationRunResponse>(
    `/personnel-migration/runs/${encodeURIComponent(String(runId))}/commit`,
    { confirm: true },
  );
}
