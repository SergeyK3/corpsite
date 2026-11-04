export type HireNewEmployee = { last_name: string; first_name: string; middle_name: string };
export const blankHireNewEmployee = (): HireNewEmployee => ({ last_name: "", first_name: "", middle_name: "" });
export const hireNewEmployeeName = (value: HireNewEmployee): string =>
  [value.last_name, value.first_name, value.middle_name].map(part => part.trim().replace(/\s+/g, " ")).filter(Boolean).join(" ");
export const hireNewEmployeeError = (value: HireNewEmployee): string | null =>
  !value.last_name.trim() || !value.first_name.trim() ? "Укажите фамилию и имя нового сотрудника. Отчество необязательно." : null;
