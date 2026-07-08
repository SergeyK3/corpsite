// PMF-4B — Personnel Migration Framework API client (read-only shell).
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

async function apiGetJson<T>(path: string): Promise<T> {
  const url = resolveApiUrl(path);
  const res = await fetch(url, { method: "GET", headers: authHeaders(), cache: "no-store" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw parseErrorBody(res.status, body, "Не удалось загрузить данные.");
  }
  return res.json() as Promise<T>;
}

/** PMF-3B — list registered migration domain plugins. */
export async function listMigrationDomains(): Promise<MigrationDomainListResponse> {
  return apiGetJson<MigrationDomainListResponse>("/personnel-migration/domains");
}
