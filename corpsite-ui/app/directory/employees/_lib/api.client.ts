// ROUTE: (library used by /directory/employees/* and /directory/org)
// FILE: corpsite-ui/app/directory/employees/_lib/api.client.ts

import type {
  EmployeesResponse,
  EmployeeDTO,
  EmployeesQuery,
  OrgTreeResponse,
} from "./types";

function toQueryString(params: Record<string, unknown>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "";

// DEV: add X-User-Id header from NEXT_PUBLIC_DEV_X_USER_ID
const DEV_UID = process.env.NEXT_PUBLIC_DEV_X_USER_ID?.trim() || "";

async function apiGet<T>(path: string): Promise<T> {
  const url = BASE ? `${BASE}${path}` : path;

  const headers: Record<string, string> = { Accept: "application/json" };
  if (DEV_UID) headers["X-User-Id"] = DEV_UID;

  const res = await fetch(url, {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Directory API ${res.status}: ${text || res.statusText}`);
  }

  return (await res.json()) as T;
}

// ---------------------------
// Employees
// ---------------------------

export function getEmployees(query: EmployeesQuery = {}): Promise<EmployeesResponse> {
  const qs = toQueryString(query as Record<string, unknown>);
  return apiGet<EmployeesResponse>(`/directory/employees${qs}`);
}

export function getEmployee(id: string): Promise<EmployeeDTO> {
  const safe = encodeURIComponent(String(id).trim());
  return apiGet<EmployeeDTO>(`/directory/employees/${safe}`);
}

// ---------------------------
// Org tree
// ---------------------------

export function getOrgTree(): Promise<OrgTreeResponse> {
  return apiGet<OrgTreeResponse>("/directory/org-units/tree");
}
