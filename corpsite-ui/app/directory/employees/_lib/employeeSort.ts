export const EMPLOYEE_SORT_COLUMNS = ["fio", "position", "department", "rate", "status"] as const;

export type EmployeeSortColumn = (typeof EMPLOYEE_SORT_COLUMNS)[number];
export type SortOrder = "asc" | "desc";

export function isEmployeeSortColumn(value: string | null | undefined): value is EmployeeSortColumn {
  return EMPLOYEE_SORT_COLUMNS.includes(value as EmployeeSortColumn);
}

export function parseSortOrder(value: string | null | undefined): SortOrder | undefined {
  if (value === "asc" || value === "desc") return value;
  return undefined;
}

export function toggleEmployeeSort(
  current: { sort?: EmployeeSortColumn; order?: SortOrder },
  column: EmployeeSortColumn,
): { sort: EmployeeSortColumn; order: SortOrder } {
  if (current.sort === column) {
    return { sort: column, order: current.order === "asc" ? "desc" : "asc" };
  }
  return { sort: column, order: "asc" };
}

export function sortIndicator(order: SortOrder | null | undefined): string {
  return order === "desc" ? "↓" : "↑";
}
