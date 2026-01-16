export type EmployeesFilters = {
  q?: string;
  department_id?: number;
  position_id?: number;
  status?: "active" | "inactive" | "all";
  limit?: number;
  offset?: number;
};

export function normalizeFilters(input: Partial<EmployeesFilters>): EmployeesFilters {
  const status = input.status ?? "active";
  const normalizedStatus: EmployeesFilters["status"] =
    status === "active" || status === "inactive" || status === "all" ? status : "active";

  return {
    q: (input.q ?? "").trim() || undefined,
    department_id: input.department_id || undefined,
    position_id: input.position_id || undefined,
    status: normalizedStatus,
    limit: input.limit ?? 50,
    offset: input.offset ?? 0,
  };
}

export function filtersToSearchParams(filters: EmployeesFilters): URLSearchParams {
  const p = new URLSearchParams();
  if (filters.q) p.set("q", filters.q);
  if (filters.department_id) p.set("department_id", String(filters.department_id));
  if (filters.position_id) p.set("position_id", String(filters.position_id));
  if (filters.status) p.set("status", filters.status);
  if (filters.limit != null) p.set("limit", String(filters.limit));
  if (filters.offset != null) p.set("offset", String(filters.offset));
  return p;
}
