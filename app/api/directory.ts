// app/api/directory.ts

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
  full_name: string;
  department: Department;
  position: Position;
  date_from: string | null;
  date_to: string | null;
  employment_rate: number | null;
  is_active: boolean;
};

export type EmployeesResponse = {
  items: EmployeeListItem[];
  total: number;
};

export type EmployeesQuery = {
  q?: string;
  department_id?: number;
  position_id?: number;
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

const BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "";

async function apiGet<T>(path: string): Promise<T> {
  const url = BASE ? `${BASE}${path}` : path;

  const res = await fetch(url, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
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

export function getEmployees(
  query: EmployeesQuery = {}
): Promise<EmployeesResponse> {
  const qs = toQueryString(query as Record<string, unknown>);
  return apiGet<EmployeesResponse>(`/directory/employees${qs}`);
}
