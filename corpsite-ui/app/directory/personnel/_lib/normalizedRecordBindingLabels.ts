export type EmployeeBindingStatus = "bound" | "unbound" | "conflict";

export type EmployeeBindingMethod = "iin" | "full_name" | "row_link" | "manual";

export type EmployeeBindingInfo = {
  status: EmployeeBindingStatus;
  method?: EmployeeBindingMethod | null;
  reason?: string | null;
  employee_id?: number | null;
  directory_employee_name?: string | null;
  candidate_employee_ids?: number[];
};

export const EMPLOYEE_BINDING_STATUS_LABELS: Record<EmployeeBindingStatus, string> = {
  bound: "Привязан",
  unbound: "Не привязан",
  conflict: "Конфликт",
};

export const EMPLOYEE_BINDING_METHOD_LABELS: Record<EmployeeBindingMethod, string> = {
  iin: "По ИИН",
  full_name: "По ФИО",
  row_link: "Ссылка на строку",
  manual: "Вручную",
};

export function employeeBindingBadgeClass(status: EmployeeBindingStatus): string {
  switch (status) {
    case "bound":
      return "border-green-200 bg-green-100 text-green-900 dark:border-green-800 dark:bg-green-950/50 dark:text-green-200";
    case "conflict":
      return "border-orange-200 bg-orange-100 text-orange-900 dark:border-orange-800 dark:bg-orange-950/50 dark:text-orange-200";
    default:
      return "border-zinc-200 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300";
  }
}
