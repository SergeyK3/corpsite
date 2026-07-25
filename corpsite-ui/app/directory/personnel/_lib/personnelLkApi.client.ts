import { buildHeaders, readJsonSafe, toApiError } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";
import { resolveApiUrl } from "@/lib/apiBase";

export const PERSONNEL_LK_API_PATH = "/directory/personnel/lk";

export type PersonnelLkRecordKind = "employee" | "applicant";

export type PersonnelLkRegistryItem = {
  person_id: number;
  record_kind: PersonnelLkRecordKind;
  id: number | null;
  employee_id: number | null;
  active_application_id: number | null;
  fio: string | null;
  iin: string | null;
  rate: number | string | null;
  status: string;
  application_status: string | null;
};

export type PersonnelLkRegistryResponse = {
  items: PersonnelLkRegistryItem[];
  total: number;
  limit: number;
  offset: number;
};

export type ListPersonnelLkRegistryArgs = {
  q?: string;
  record_kind?: PersonnelLkRecordKind;
  status?: "active" | "inactive" | "all";
  application_status?: string;
  org_group_id?: number;
  org_unit_id?: number;
  position_id?: number;
  limit?: number;
  offset?: number;
};

function buildQuery(params: Record<string, string | number | undefined>): string {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined) return;
    const raw = String(value).trim();
    if (!raw) return;
    q.set(key, raw);
  });
  return q.toString();
}

export function mapPersonnelLkApiError(e: unknown, fallback = "Ошибка запроса."): string {
  return formatThrownError(e, { fallback });
}

export async function listPersonnelLkRegistry(
  args: ListPersonnelLkRegistryArgs,
): Promise<PersonnelLkRegistryResponse> {
  const qs = buildQuery({
    q: args.q,
    record_kind: args.record_kind,
    status: args.status,
    application_status: args.application_status,
    org_group_id: args.org_group_id,
    org_unit_id: args.org_unit_id,
    position_id: args.position_id,
    limit: args.limit,
    offset: args.offset,
  });
  const url = qs ? `${resolveApiUrl(PERSONNEL_LK_API_PATH)}?${qs}` : resolveApiUrl(PERSONNEL_LK_API_PATH);
  const res = await fetch(url, {
    method: "GET",
    headers: buildHeaders({ Accept: "application/json" }),
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await readJsonSafe(res);
    throw toApiError(res.status, body, { method: "GET", url: PERSONNEL_LK_API_PATH });
  }
  return (await res.json()) as PersonnelLkRegistryResponse;
}
