// corpsite-ui/app/api/directory.ts

export type Department = {
  id: number;
  name: string;
};

export type Position = {
  id: number;
  name: string;
};

export type EmployeeListItem = {
  id: string;
  full_name?: string; // backward/forward tolerant
  fio?: string;       // backend may return fio
  department?: Department | null;
  position?: Position | null;
  org_unit?: { id: number; name: string } | null;
  date_from?: string | null;
  date_to?: string | null;
  rate?: number | null;
  employment_rate?: number | null;
  is_active?: boolean;
};

export type EmployeesResponse = {
  items: EmployeeListItem[];
  total: number;
};

export type EmployeesQuery = {
  q?: string;
  department_id?: number;
  position_id?: number;
  org_unit_id?: number;
  include_children?: boolean;
  status?: "active" | "inactive" | "all";
  limit?: number;
  offset?: number;
  sort?: "full_name" | "id";
  order?: "asc" | "desc";
};

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
const DEV_X_USER_ID = process.env.NEXT_PUBLIC_DEV_X_USER_ID?.trim() || "";

// NOTE: backend expects X-User-Id; for MVP dev-mode we pass it from env if present.
function buildHeaders(extra?: Record<string, string>): HeadersInit {
  const h: Record<string, string> = {
    "Content-Type": "application/json",
    ...(extra || {}),
  };
  if (DEV_X_USER_ID) h["X-User-Id"] = DEV_X_USER_ID;
  return h;
}

async function apiGet<T>(path: string): Promise<T> {
  const url = BASE ? `${BASE}${path}` : path;

  const res = await fetch(url, {
    method: "GET",
    headers: buildHeaders(),
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Directory API ${res.status}: ${text || res.statusText}`);
  }

  return (await res.json()) as T;
}

export function getDepartments(): Promise<Department[]> {
  return apiGet<Department[]>("/directory/departments");
}

export function getPositions(): Promise<Position[]> {
  return apiGet<Position[]>("/directory/positions");
}

export function getEmployees(query: EmployeesQuery = {}): Promise<EmployeesResponse> {
  const qs = toQueryString(query as Record<string, unknown>);
  return apiGet<EmployeesResponse>(`/directory/employees${qs}`);
}

export function getEmployee(employeeId: string): Promise<EmployeeListItem> {
  return apiGet<EmployeeListItem>(`/directory/employees/${encodeURIComponent(employeeId)}`);
}

// Tree types (for /directory/departments/tree)
export type OrgTreeNode = {
  id: number;
  parent_id: number | null;
  name: string;
  code?: string | null;
  children?: OrgTreeNode[];
};

export type OrgTreeResponse = {
  items: OrgTreeNode[];
  root_id?: number | null;
};

export function getOrgTree(): Promise<OrgTreeResponse> {
  return apiGet<OrgTreeResponse>("/directory/departments/tree");
}
