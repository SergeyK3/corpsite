// FILE: corpsite-ui/app/admin/sync/_lib/syncApi.client.ts
import { buildHeaders, readJsonSafe, toApiError } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";
import { resolveApiUrl } from "@/lib/apiBase";

function getDevUserId(): string | null {
  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
  if (appEnv === "prod" || appEnv === "production") return null;
  const v = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  return v ? v : null;
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json", ...(extra ?? {}) };
  const devUserId = getDevUserId();
  if (devUserId) headers["X-User-Id"] = devUserId;
  return buildHeaders(headers) as Record<string, string>;
}

export type SyncMeta = {
  schema_version: string;
  package_version: string;
};

export type SyncExportRequest = {
  source_instance_id: string;
  source_organization_id: string;
  source_organization_name: string;
  environment: "server" | "local" | "staging";
  notes?: string;
};

export type SyncExportResponse = {
  package_name: string;
  employee_count: number;
  override_count: number;
  skipped_override_count: number;
  warnings: string[];
  validation_ok: boolean;
  package_base64: string;
};

export type SyncPreviewItem = {
  employee_key: string;
  employee_name?: string | null;
  target_employee_id?: number | null;
  status: string;
  action: string;
  reason?: string | null;
  incoming_updated_at?: string | null;
  target_updated_at?: string | null;
  changed_sections: string[];
  incoming_sections: string[];
  target_sections: string[];
  conflict_type?: string | null;
  conflict_sections: string[];
  apply_allowed: boolean;
};

export type SyncPreviewResponse = {
  package_name?: string;
  package_path: string;
  validation_ok: boolean;
  total_records: number;
  new_count: number;
  update_count: number;
  merge_count: number;
  identical_count: number;
  orphan_count: number;
  ambiguous_count: number;
  conflict_count: number;
  skipped_count: number;
  apply_allowed_count: number;
  items: SyncPreviewItem[];
  warnings: string[];
  errors: string[];
};

export function mapSyncApiError(err: unknown, fallback: string): string {
  return formatThrownError(err, { fallback });
}

export async function fetchSyncMeta(): Promise<SyncMeta> {
  const url = resolveApiUrl("/directory/personnel/sync/meta");
  const res = await fetch(url, { method: "GET", headers: authHeaders(), cache: "no-store" });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body);
  return body as SyncMeta;
}

export async function exportSyncPackage(payload: SyncExportRequest): Promise<SyncExportResponse> {
  const url = resolveApiUrl("/directory/personnel/sync/export");
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body);
  return body as SyncExportResponse;
}

export async function previewSyncPackage(file: File): Promise<SyncPreviewResponse> {
  const url = resolveApiUrl("/directory/personnel/sync/preview");
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(),
    body: form,
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body);
  return body as SyncPreviewResponse;
}

export function downloadBase64Zip(packageBase64: string, packageName: string): void {
  const binary = atob(packageBase64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  const blob = new Blob([bytes], { type: "application/zip" });
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = packageName || "corpsite_sync.zip";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export function formatSyncTimestamp(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("ru-RU");
}

/** Approximate decoded zip size in KB from base64 payload. */
export function zipSizeKbFromBase64(packageBase64: string): number {
  const trimmed = packageBase64.trim();
  if (!trimmed) return 0;
  const padding = trimmed.endsWith("==") ? 2 : trimmed.endsWith("=") ? 1 : 0;
  const bytes = Math.floor((trimmed.length * 3) / 4) - padding;
  return Math.max(1, Math.round(bytes / 1024));
}
