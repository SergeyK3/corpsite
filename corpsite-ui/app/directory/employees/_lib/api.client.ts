import type {
  EmployeeDetails,
  EmployeeListResponse,
  Department,
  Position,
} from "./types";
import type { EmployeesFilters } from "./query";

type ApiError = Error & { status?: number; body?: string };

function buildQuery(filters: EmployeesFilters): string {
  const p = new URLSearchParams();
  if (filters.q) p.set("q", filters.q);
  if (filters.department_id) p.set("department_id", String(filters.department_id));
  if (filters.position_id) p.set("position_id", String(filters.position_id));
  if (filters.status) p.set("status", filters.status);
  if (filters.limit != null) p.set("limit", String(filters.limit));
  if (filters.offset != null) p.set("offset", String(filters.offset));
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    const err: ApiError = Object.assign(new Error(`HTTP ${res.status}`), {
      status: res.status,
      body: text,
    });
    throw err;
  }
  return (await res.json()) as T;
}

export async function getEmployees(filters: EmployeesFilters): Promise<EmployeeListResponse> {
  return apiFetch<EmployeeListResponse>(`/directory/employees${buildQuery(filters)}`);
}

export async function getEmployee(employee_id: string): Promise<EmployeeDetails> {
  return apiFetch<EmployeeDetails>(`/directory/employees/${encodeURIComponent(employee_id)}`);
}

export async function terminateEmployee(employee_id: string, date_to: string): Promise<{ ok: true }> {
  return apiFetch<{ ok: true }>(`/directory/employees/${encodeURIComponent(employee_id)}`, {
    method: "PATCH",
    body: JSON.stringify({ date_to }),
  });
}

export async function getDepartments(): Promise<Department[]> {
  return apiFetch<Department[]>(`/directory/departments`);
}

export async function getPositions(): Promise<Position[]> {
  return apiFetch<Position[]>(`/directory/positions`);
}

export function mapApiErrorToMessage(e: unknown): string {
  const err = e as ApiError;
  const status = err?.status;

  if (status === 409) return "Некорректные данные (конфликт/диапазон дат).";
  if (status === 403) return "Недостаточно прав для выполнения операции.";
  if (status === 404) return "Объект не найден (возможно, сотрудник удалён/перемещён).";
  if (status) return `Ошибка запроса (HTTP ${status}).`;
  return "Неизвестная ошибка.";
}
