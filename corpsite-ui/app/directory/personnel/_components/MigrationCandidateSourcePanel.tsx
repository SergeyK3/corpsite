// PMF-4D — candidate source context panel.
"use client";

import type { MigrationEntrySource } from "../_lib/personnelMigrationEntry";
import type { NormalizedRecord } from "../_lib/importApi.client";
import { NORMALIZED_RECORD_KIND_LABELS } from "../_lib/importApi.client";
import { migrationCandidateSummary } from "../_lib/personnelMigrationCandidates";
import { migrationHrSessionEntrySourceLabel } from "../_lib/personnelMigrationHrLabels";

type MigrationCandidateSourcePanelProps = {
  candidateId: string | null;
  source: MigrationEntrySource;
  record: NormalizedRecord | null;
};

function ContextField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="mt-1 text-sm text-zinc-900 dark:text-zinc-100">{value || "—"}</dd>
    </div>
  );
}

export default function MigrationCandidateSourcePanel({
  candidateId,
  source,
  record,
}: MigrationCandidateSourcePanelProps) {
  return (
    <section
      aria-label="Источник данных"
      className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
      data-testid="migration-candidate-source"
    >
      <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Источник данных</h2>
      <dl className="mt-4 grid gap-4 sm:grid-cols-2">
        <ContextField label="Ключ записи" value={candidateId ?? "—"} />
        <ContextField label="Источник" value={migrationHrSessionEntrySourceLabel(source)} />
        {record ? (
          <>
            <ContextField
              label="Тип записи"
              value={NORMALIZED_RECORD_KIND_LABELS[record.record_kind] ?? record.record_kind}
            />
            <ContextField label="Кратко" value={migrationCandidateSummary(record)} />
          </>
        ) : candidateId ? (
          <div className="sm:col-span-2">
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Запись будет показана после загрузки списка кандидатов.
            </p>
          </div>
        ) : (
          <div className="sm:col-span-2">
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Выберите запись из списка ниже, чтобы начать сопоставление.
            </p>
          </div>
        )}
      </dl>
    </section>
  );
}
