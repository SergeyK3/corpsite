// corpsite-ui/app/directory/employees/_lib/api.server.ts
import "server-only";

type Json = any;

function apiBase(): string {
  return (
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    "http://127.0.0.1:8000"
  );
}

function devUserId(): string {
  return process.env.DEV_X_USER_ID || process.env.NEXT_PUBLIC_DEV_X_USER_ID || "";
}

function buildUrl(path: string, params?: Record<string, any>): string {
  const base = apiBase().replace(/\/+$/, "");
  const url = new URL(`${base}${path.startsWith("/") ? "" : "/"}${path}`);

  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === "") continue;
      url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

async function apiGet(path: string, params?: Record<string, any>): Promise<Json> {
  const url = buildUrl(path, params);
  const uid = devUserId();

  const headers: Record<string, string> = {};
  if (uid) headers["X-User-Id"] = uid;

  const res = await fetch(url, {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Directory API GET ${path} -> ${res.status} ${res.statusText}: ${body}`);
  }

  return res.json();
}

// --------------------
// Public API used by pages / server components
// --------------------

export async function getDepartments(): Promise<Array<{ id: number; name: string }>> {
  const r = await apiGet("/directory/departments", { limit: 1000, offset: 0 });
  return Array.isArray(r?.items) ? r.items : [];
}

export async function getPositions(): Promise<Array<{ id: number; name: string }>> {
  const r = await apiGet("/directory/positions", { limit: 1000, offset: 0 });
  return Array.isArray(r?.items) ? r.items : [];
}

export type GetEmployeesArgs = {
  q?: string;
  department_id?: number;
  position_id?: number;
  status?: string; // active|inactive|all
  limit?: number;
  offset?: number;
  sort?: string;
  order?: string;
};

export async function getEmployees(args: GetEmployeesArgs) {
  return apiGet("/directory/employees", {
    q: args.q,
    department_id: args.department_id,
    position_id: args.position_id,
    status: args.status,
    limit: args.limit,
    offset: args.offset,
    sort: args.sort,
    order: args.order,
  });
}

// --------------------
// Employee card API
// --------------------

export async function getEmployeeById(employee_id: string) {
  const id = (employee_id ?? "").toString().trim();
  return apiGet(`/directory/employees/${encodeURIComponent(id)}`);
}
