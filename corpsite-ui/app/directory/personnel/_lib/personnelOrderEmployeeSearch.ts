import type { EmployeeDTO, EmployeesResponse } from "@/app/directory/employees/_lib/types";

export type EmployeeSearchOption = {
  employee_id: number;
  full_name: string;
};

/**
 * Map GET /directory/employees payload `{ items, total }` into dropdown options.
 * Backend items use `id` + `fio` (not `employee_id` / `full_name`).
 */
export function mapEmployeesResponseToSearchOptions(
  response: EmployeesResponse | EmployeeDTO[] | null | undefined,
): EmployeeSearchOption[] {
  const list = Array.isArray(response)
    ? response
    : Array.isArray(response?.items)
      ? response.items
      : [];

  const options: EmployeeSearchOption[] = [];
  for (const row of list) {
    const id = Number(
      (row as { id?: string | number; employee_id?: number }).id ??
        (row as { employee_id?: number }).employee_id,
    );
    if (!Number.isFinite(id) || id <= 0) continue;
    const fullName = String(
      (row as { fio?: string | null }).fio ??
        (row as { full_name?: string | null }).full_name ??
        (row as { name?: string | null }).name ??
        `#${id}`,
    ).trim();
    options.push({
      employee_id: id,
      full_name: fullName || `#${id}`,
    });
  }
  return options;
}

export function requireEmployeeIdForItemType(
  itemTypeCode: string,
  employeeId: string | number | null | undefined,
): string | null {
  const type = String(itemTypeCode || "").trim().toUpperCase();
  if (type !== "HIRE") return null;
  const numeric = Number(employeeId);
  if (Number.isFinite(numeric) && numeric > 0) return null;
  return "Для пункта «Приём» выберите сотрудника из результатов поиска.";
}
