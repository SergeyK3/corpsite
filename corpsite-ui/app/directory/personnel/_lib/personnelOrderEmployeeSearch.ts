import type { EmployeeDTO, EmployeesResponse } from "@/app/directory/employees/_lib/types";

import { requiresEmployeeForFormType } from "./personnelOrderItemFormRegistry";

export type EmployeeSearchOption = {
  employee_id: number;
  full_name: string;
  org_unit_id: number | null;
  org_unit_name: string | null;
  position_id: number | null;
  position_name: string | null;
  rate: string | null;
  status: string;
};

function formatRate(value: string | number | null | undefined): string | null {
  if (value == null || value === "") return null;
  const text = String(value).trim();
  return text || null;
}

/**
 * Map GET /directory/employees payload `{ items, total }` into dropdown options.
 * Backend items use `id` + `fio` (not `employee_id` / `full_name`).
 */
export function mapEmployeesResponseToSearchOptions(
  response: EmployeesResponse | EmployeeDTO[] | null | undefined,
  options?: { activeOnly?: boolean },
): EmployeeSearchOption[] {
  const list = Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

  const activeOnly = options?.activeOnly === true;
  const mapped: EmployeeSearchOption[] = [];
  for (const row of list) {
    const dto = row as EmployeeDTO;
    const id = Number(dto.id ?? (row as { employee_id?: number }).employee_id);
    if (!Number.isFinite(id) || id <= 0) continue;

    const status = String(dto.status || "").trim().toLowerCase();
    // API already filters status=active; keep rows with missing/unknown status labels.
    if (activeOnly && status && status !== "active" && status !== "unknown") continue;

    const fullName = String(
      dto.fio ??
        (row as { full_name?: string | null }).full_name ??
        (row as { name?: string | null }).name ??
        `#${id}`,
    ).trim();

    mapped.push({
      employee_id: id,
      full_name: fullName || `#${id}`,
      org_unit_id: dto.org_unit?.unit_id ?? null,
      org_unit_name: dto.org_unit?.name ?? null,
      position_id: dto.position?.id ?? null,
      position_name: dto.position?.name ?? null,
      rate: formatRate(dto.rate),
      status,
    });
  }
  return mapped;
}

export function requireEmployeeIdForItemType(
  itemTypeCode: string,
  employeeId: string | number | null | undefined,
): string | null {
  if (!requiresEmployeeForFormType(itemTypeCode)) return null;
  const numeric = Number(employeeId);
  if (Number.isFinite(numeric) && numeric > 0) return null;
  return "Выберите действующего сотрудника из результатов поиска.";
}
