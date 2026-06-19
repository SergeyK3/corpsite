"use client";

import type { ImportBatchReviewVisibility } from "../_lib/importApi.client";

type Props = {
  visibility: ImportBatchReviewVisibility | null | undefined;
};

export default function ImportReviewByExceptionBanner({ visibility }: Props) {
  if (!visibility?.no_changes_detected) {
    return null;
  }

  return (
    <div className="mb-4 rounded-xl border border-green-200 bg-green-50 px-4 py-4 dark:border-green-900/50 dark:bg-green-950/30">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-green-900 dark:text-green-100">
            Review complete — изменений не обнаружено
          </h2>
          <p className="mt-1 text-sm text-green-800 dark:text-green-200">
            Импорт полностью совпадает с каноническим кадровым реестром.
            {visibility.hidden_unchanged > 0
              ? ` Скрыто неизменённых записей: ${visibility.hidden_unchanged.toLocaleString("ru-RU")}.`
              : null}
          </p>
          <p className="mt-1 text-xs text-green-700 dark:text-green-300">
            Действия пользователя не требуются.
          </p>
        </div>
        <span className="rounded-full border border-green-300 bg-white px-3 py-1 text-xs font-medium text-green-900 dark:border-green-800 dark:bg-green-950 dark:text-green-100">
          No changes detected
        </span>
      </div>
    </div>
  );
}
