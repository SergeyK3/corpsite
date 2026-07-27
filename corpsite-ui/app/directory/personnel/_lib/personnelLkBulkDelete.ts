import type {
  EmployeeBulkDeleteResponse,
} from "../../employees/_lib/api.client";
import type { PersonnelLkRegistryItem } from "./personnelLkApi.client";

export function listSelectableEmployeeIds(items: PersonnelLkRegistryItem[]): number[] {
  return items
    .filter((item) => item.record_kind === "employee" && item.employee_id != null)
    .map((item) => Number(item.employee_id))
    .filter((id) => Number.isFinite(id) && id > 0);
}

export function buildEmployeeBulkDeleteConfirmMessage(names: string[]): string {
  const uniqueNames = names.map((name) => name.trim() || "сотрудника").filter(Boolean);
  const list =
    uniqueNames.length > 0
      ? uniqueNames.map((name) => `• ${name}`).join("\n")
      : "• выбранные сотрудники";
  return [
    `Удалить ${uniqueNames.length || "выбранных"} сотрудник(ов)?`,
    "",
    list,
    "",
    "Сотрудники и все связанные данные будут удалены без возможности восстановления.",
  ].join("\n");
}

export function formatEmployeeBulkDeleteSummary(result: EmployeeBulkDeleteResponse): string {
  const deletedCount = result.deleted.length;
  const failedCount = result.failed.length;
  if (failedCount === 0) {
    return deletedCount === 1
      ? "Удалён 1 сотрудник."
      : `Удалено сотрудников: ${deletedCount}.`;
  }
  if (deletedCount === 0) {
    return "Не удалось удалить выбранных сотрудников.";
  }
  return `Удалено: ${deletedCount}. Не удалено: ${failedCount}.`;
}

export function formatEmployeeBulkDeleteFailureLines(
  result: EmployeeBulkDeleteResponse,
  nameByEmployeeId: Map<number, string>,
): string[] {
  return result.failed.map((item) => {
    const name = nameByEmployeeId.get(item.employee_id) || `ID ${item.employee_id}`;
    return `${name}: ${item.message}`;
  });
}
