/** PPR Command API client — employment biography mutations (WP-PR-016). */

import { buildHeaders, readJsonSafe, toApiError } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";

function getDevUserId(): string | null {
  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
  if (appEnv === "prod" || appEnv === "production") return null;
  const v = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  return v ? v : null;
}

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  const devUserId = getDevUserId();
  if (devUserId) headers["X-User-Id"] = devUserId;
  return buildHeaders(headers) as Record<string, string>;
}

export type PprExternalEmploymentRecordWrite = {
  record_kind: string;
  employee_context_id?: number | null;
  employer_name?: string | null;
  department_name?: string | null;
  position_title?: string | null;
  employment_type?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  termination_reason?: string | null;
  document_reference?: string | null;
  source_system?: string | null;
  source_id?: string | null;
  provenance?: Record<string, unknown> | null;
  notes?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type PprExternalEmploymentCreateBody = {
  command_id: string;
  correlation_id?: string | null;
  record: PprExternalEmploymentRecordWrite;
};

export type PprExternalEmploymentVoidBody = {
  command_id: string;
  correlation_id?: string | null;
  reason: string;
  expected_updated_at: string;
};

export type PprExternalEmploymentSupersedeBody = {
  command_id: string;
  correlation_id?: string | null;
  expected_updated_at: string;
  replacement: PprExternalEmploymentRecordWrite;
};

export type PprCommandMutationResponse = {
  command_id: string;
  command_type: string;
  status: string;
  resolved_person_id: number;
  section_code: string;
  section_record_id: number | null;
  section_mutation_kind: string | null;
  event_ids: number[];
  envelope_version: number | null;
  correlation_id: string | null;
};

async function pprPostJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const payload = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, payload, { method: "POST", url: path });
  }
  return payload as T;
}

export function newPprCommandId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `cmd-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function createExternalEmploymentByPerson(
  personId: string | number,
  body: PprExternalEmploymentCreateBody,
): Promise<PprCommandMutationResponse> {
  return pprPostJson<PprCommandMutationResponse>(
    `/api/ppr/persons/${encodeURIComponent(String(personId))}/employment-biography/records`,
    body,
  );
}

export async function createExternalEmploymentByEmployee(
  employeeId: string | number,
  body: PprExternalEmploymentCreateBody,
): Promise<PprCommandMutationResponse> {
  return pprPostJson<PprCommandMutationResponse>(
    `/api/ppr/employees/${encodeURIComponent(String(employeeId))}/employment-biography/records`,
    body,
  );
}

export async function voidExternalEmploymentByPerson(
  personId: string | number,
  recordId: string | number,
  body: PprExternalEmploymentVoidBody,
): Promise<PprCommandMutationResponse> {
  return pprPostJson<PprCommandMutationResponse>(
    `/api/ppr/persons/${encodeURIComponent(String(personId))}/employment-biography/records/${encodeURIComponent(String(recordId))}/void`,
    body,
  );
}

export async function voidExternalEmploymentByEmployee(
  employeeId: string | number,
  recordId: string | number,
  body: PprExternalEmploymentVoidBody,
): Promise<PprCommandMutationResponse> {
  return pprPostJson<PprCommandMutationResponse>(
    `/api/ppr/employees/${encodeURIComponent(String(employeeId))}/employment-biography/records/${encodeURIComponent(String(recordId))}/void`,
    body,
  );
}

export async function supersedeExternalEmploymentByPerson(
  personId: string | number,
  recordId: string | number,
  body: PprExternalEmploymentSupersedeBody,
): Promise<PprCommandMutationResponse> {
  return pprPostJson<PprCommandMutationResponse>(
    `/api/ppr/persons/${encodeURIComponent(String(personId))}/employment-biography/records/${encodeURIComponent(String(recordId))}/supersede`,
    body,
  );
}

export async function supersedeExternalEmploymentByEmployee(
  employeeId: string | number,
  recordId: string | number,
  body: PprExternalEmploymentSupersedeBody,
): Promise<PprCommandMutationResponse> {
  return pprPostJson<PprCommandMutationResponse>(
    `/api/ppr/employees/${encodeURIComponent(String(employeeId))}/employment-biography/records/${encodeURIComponent(String(recordId))}/supersede`,
    body,
  );
}

export type PprEmploymentBiographyRoute =
  | { kind: "person"; id: number }
  | { kind: "employee"; id: string };

export async function createExternalEmployment(
  route: PprEmploymentBiographyRoute,
  body: PprExternalEmploymentCreateBody,
): Promise<PprCommandMutationResponse> {
  return route.kind === "person"
    ? createExternalEmploymentByPerson(route.id, body)
    : createExternalEmploymentByEmployee(route.id, body);
}

export async function voidExternalEmployment(
  route: PprEmploymentBiographyRoute,
  recordId: number,
  body: PprExternalEmploymentVoidBody,
): Promise<PprCommandMutationResponse> {
  return route.kind === "person"
    ? voidExternalEmploymentByPerson(route.id, recordId, body)
    : voidExternalEmploymentByEmployee(route.id, recordId, body);
}

export async function supersedeExternalEmployment(
  route: PprEmploymentBiographyRoute,
  recordId: number,
  body: PprExternalEmploymentSupersedeBody,
): Promise<PprCommandMutationResponse> {
  return route.kind === "person"
    ? supersedeExternalEmploymentByPerson(route.id, recordId, body)
    : supersedeExternalEmploymentByEmployee(route.id, recordId, body);
}

export type PprMilitaryServiceRecordWrite = {
  record_kind: string;
  employee_context_id?: number | null;
  obligation_status?: string | null;
  registration_category?: string | null;
  military_rank?: string | null;
  military_specialty_code?: string | null;
  personnel_composition?: string | null;
  fitness_category?: string | null;
  registration_status?: string | null;
  commissariat_name?: string | null;
  registered_at?: string | null;
  deregistered_at?: string | null;
  military_id_book_series?: string | null;
  military_id_book_number?: string | null;
  registration_certificate_series?: string | null;
  registration_certificate_number?: string | null;
  notes?: string | null;
  source_type?: string | null;
  provenance?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
};

export type PprMilitaryServiceCreateBody = {
  command_id: string;
  correlation_id?: string | null;
  record: PprMilitaryServiceRecordWrite;
};

export type PprMilitaryServiceVoidBody = {
  command_id: string;
  correlation_id?: string | null;
  reason: string;
  expected_updated_at: string;
};

export type PprMilitaryServiceSupersedeBody = {
  command_id: string;
  correlation_id?: string | null;
  expected_updated_at: string;
  replacement: PprMilitaryServiceRecordWrite;
};

export type PprMilitaryServiceRoute =
  | { kind: "person"; id: number }
  | { kind: "employee"; id: string };

export async function createMilitaryServiceByPerson(
  personId: string | number,
  body: PprMilitaryServiceCreateBody,
): Promise<PprCommandMutationResponse> {
  return pprPostJson<PprCommandMutationResponse>(
    `/api/ppr/persons/${encodeURIComponent(String(personId))}/military-service/records`,
    body,
  );
}

export async function createMilitaryServiceByEmployee(
  employeeId: string | number,
  body: PprMilitaryServiceCreateBody,
): Promise<PprCommandMutationResponse> {
  return pprPostJson<PprCommandMutationResponse>(
    `/api/ppr/employees/${encodeURIComponent(String(employeeId))}/military-service/records`,
    body,
  );
}

export async function voidMilitaryServiceByPerson(
  personId: string | number,
  recordId: string | number,
  body: PprMilitaryServiceVoidBody,
): Promise<PprCommandMutationResponse> {
  return pprPostJson<PprCommandMutationResponse>(
    `/api/ppr/persons/${encodeURIComponent(String(personId))}/military-service/records/${encodeURIComponent(String(recordId))}/void`,
    body,
  );
}

export async function voidMilitaryServiceByEmployee(
  employeeId: string | number,
  recordId: string | number,
  body: PprMilitaryServiceVoidBody,
): Promise<PprCommandMutationResponse> {
  return pprPostJson<PprCommandMutationResponse>(
    `/api/ppr/employees/${encodeURIComponent(String(employeeId))}/military-service/records/${encodeURIComponent(String(recordId))}/void`,
    body,
  );
}

export async function supersedeMilitaryServiceByPerson(
  personId: string | number,
  recordId: string | number,
  body: PprMilitaryServiceSupersedeBody,
): Promise<PprCommandMutationResponse> {
  return pprPostJson<PprCommandMutationResponse>(
    `/api/ppr/persons/${encodeURIComponent(String(personId))}/military-service/records/${encodeURIComponent(String(recordId))}/supersede`,
    body,
  );
}

export async function supersedeMilitaryServiceByEmployee(
  employeeId: string | number,
  recordId: string | number,
  body: PprMilitaryServiceSupersedeBody,
): Promise<PprCommandMutationResponse> {
  return pprPostJson<PprCommandMutationResponse>(
    `/api/ppr/employees/${encodeURIComponent(String(employeeId))}/military-service/records/${encodeURIComponent(String(recordId))}/supersede`,
    body,
  );
}

export async function createMilitaryService(
  route: PprMilitaryServiceRoute,
  body: PprMilitaryServiceCreateBody,
): Promise<PprCommandMutationResponse> {
  return route.kind === "person"
    ? createMilitaryServiceByPerson(route.id, body)
    : createMilitaryServiceByEmployee(route.id, body);
}

export async function voidMilitaryService(
  route: PprMilitaryServiceRoute,
  recordId: number,
  body: PprMilitaryServiceVoidBody,
): Promise<PprCommandMutationResponse> {
  return route.kind === "person"
    ? voidMilitaryServiceByPerson(route.id, recordId, body)
    : voidMilitaryServiceByEmployee(route.id, recordId, body);
}

export async function supersedeMilitaryService(
  route: PprMilitaryServiceRoute,
  recordId: number,
  body: PprMilitaryServiceSupersedeBody,
): Promise<PprCommandMutationResponse> {
  return route.kind === "person"
    ? supersedeMilitaryServiceByPerson(route.id, recordId, body)
    : supersedeMilitaryServiceByEmployee(route.id, recordId, body);
}
