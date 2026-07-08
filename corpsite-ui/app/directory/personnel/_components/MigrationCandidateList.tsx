// PMF-4D — migration candidate selection list.
"use client";

import type { NormalizedRecord } from "../_lib/importApi.client";
import { NORMALIZED_RECORD_KIND_LABELS } from "../_lib/importApi.client";
import { migrationCandidateSummary } from "../_lib/personnelMigrationCandidates";

type MigrationCandidateListProps = {
  records: NormalizedRecord[];
  selectedRecordId: number | null;
  loading?: boolean;
  adding?: boolean;
  error?: string | null;
  onSelect: (record: NormalizedRecord) => void;
};

export default function MigrationCandidateList({
  records,
  selectedRecordId,
  loading = false,
  adding = false,
  error = null,
  onSelect,
}: MigrationCandidateListProps) {
  if (loading) {
    return (
      <section
        aria-label="Кандидаты для переноса"
        className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
      >
        <p className="text-sm text-zinc-600 dark:text-zinc-400">Загрузка записей…</p>
      </section>
    );
  }

  return (
    <section
      aria-label="Кандидаты для переноса"
      className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
      data-testid="migration-candidate-list"
    >
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Записи для переноса</h2>
        {adding ? (
          <span className="text-xs text-zinc-500">Добавление в сессию…</span>
        ) : null}
      </div>

      {error ? (
        <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </p>
      ) : null}

      {records.length === 0 ? (
        <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-400">
          Нет одобренных записей для этого сотрудника. Вернитесь в проверку записей.
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-zinc-200 dark:divide-zinc-800">
          {records.map((record) => {
            const isSelected = selectedRecordId === record.normalized_record_id;
            return (
              <li key={record.normalized_record_id}>
                <button
                  type="button"
                  disabled={adding}
                  onClick={() => onSelect(record)}
                  className={[
                    "flex w-full items-start justify-between gap-3 px-1 py-3 text-left transition",
                    isSelected
                      ? "rounded-lg bg-blue-50 ring-1 ring-blue-200 dark:bg-blue-950/30 dark:ring-blue-900"
                      : "hover:bg-zinc-50 dark:hover:bg-zinc-900/50",
                    adding ? "cursor-wait opacity-70" : "",
                  ].join(" ")}
                  aria-pressed={isSelected}
                >
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-zinc-900 dark:text-zinc-100">
                      {migrationCandidateSummary(record)}
                    </span>
                    <span className="mt-1 block text-xs text-zinc-500">
                      {NORMALIZED_RECORD_KIND_LABELS[record.record_kind] ?? record.record_kind}
                      {" · "}
                      Запись № {record.normalized_record_id}
                    </span>
                  </span>
                  {isSelected ? (
                    <span className="shrink-0 rounded-full bg-blue-600 px-2 py-0.5 text-xs font-medium text-white">
                      Выбрано
                    </span>
                  ) : null}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
