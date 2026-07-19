import type { MonthlyDiffRemoval } from "./importApi.client";

/** Кадровое решение по записи, отсутствующей в новом файле. */
export type RemovedEntryDecisionKind = "restore" | "confirm_removal";

export const REMOVED_ENTRY_RESTORE_LABEL = "Восстановить запись";
export const REMOVED_ENTRY_CONFIRM_REMOVAL_LABEL = "Подтвердить удаление";

export const REMOVED_ENTRY_DECISION_FOUNDATION_NOTE =
  "Сохранение решений по отсутствующим в файле записям будет доступно после подключения команд на сервере. " +
  "До этого кнопки показывают смысл действия и не меняют эталон.";

export function isRemovedEntryRoster(recordKind: string | null | undefined): boolean {
  return String(recordKind ?? "").trim().toLowerCase() === "roster";
}

/** Рекомендуемый шаг для кадровика — без привязки к API. */
export function getRemovedEntryRecommendedStep(recordKind: string | null | undefined): string {
  if (isRemovedEntryRoster(recordKind)) {
    return (
      "Сотрудник есть в эталоне, но отсутствует в Excel. " +
      "Выберите: восстановить запись в эталоне или подтвердить удаление из состава."
    );
  }
  return (
    "Запись есть в эталоне, но отсутствует в новом файле. " +
    "Выберите: восстановить запись или подтвердить её удаление."
  );
}

export function getRemovedEntryDecisionDialogTitle(kind: RemovedEntryDecisionKind): string {
  return kind === "restore" ? REMOVED_ENTRY_RESTORE_LABEL : REMOVED_ENTRY_CONFIRM_REMOVAL_LABEL;
}

export function getRemovedEntryDecisionDialogBody(
  item: Pick<MonthlyDiffRemoval, "record_kind">,
  kind: RemovedEntryDecisionKind,
): string {
  const roster = isRemovedEntryRoster(item.record_kind);

  if (kind === "restore") {
    if (roster) {
      return (
        "Сотрудник останется в формируемом эталоне с данными из текущего канонического снимка, " +
        "как если бы он присутствовал в файле. После сохранения решения строка исчезнет из списка нерешённых проблем."
      );
    }
    return (
      "Запись останется в формируемом эталоне с данными из текущего канонического снимка. " +
      "После сохранения решения строка исчезнет из списка нерешённых проблем."
    );
  }

  if (roster) {
    return (
      "Подтверждаете, что сотрудник действительно выбыл из состава и не должен войти в новый эталон по этому импорту. " +
      "После сохранения решения строка исчезнет из списка нерешённых проблем."
    );
  }
  return (
    "Подтверждаете, что запись действительно удалена и не должна войти в новый эталон по этому импорту. " +
    "После сохранения решения строка исчезнет из списка нерешённых проблем."
  );
}

export function removedEntryDecisionTestId(
  item: Pick<MonthlyDiffRemoval, "match_key" | "canonical_entry_id">,
  kind: RemovedEntryDecisionKind,
): string {
  return `removed-entry-${kind}-${item.canonical_entry_id}-${item.match_key}`;
}
