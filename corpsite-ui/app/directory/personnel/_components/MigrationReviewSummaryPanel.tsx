// PMF-4E — review summary before commit.
"use client";

import type { EmployeeDetails } from "@/app/directory/employees/_lib/types";

import type { MigrationEntrySource } from "../_lib/personnelMigrationEntry";
import type { MigrationDomainRow } from "../_lib/personnelMigrationApi.client";
import type { NormalizedRecord } from "../_lib/importApi.client";
import { migrationCandidateSummary } from "../_lib/personnelMigrationCandidates";
import {
  MIGRATION_REVIEW_READINESS_READY,
  MIGRATION_REVIEW_SUMMARY_TITLE,
  migrationHrCommitUnavailableReason,
  migrationHrSessionEntrySourceLabel,
} from "../_lib/personnelMigrationHrLabels";

type MigrationReviewSummaryPanelProps = {
  employee: EmployeeDetails;
  domain: MigrationDomainRow;
  source: MigrationEntrySource;
  record: NormalizedRecord | null;
  isDraft: boolean;
  hasPersonLink: boolean;
};

function SummaryField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="mt-1 text-sm text-zinc-900 dark:text-zinc-100">{value || "—"}</dd>
    </div>
  );
}

export default function MigrationReviewSummaryPanel({
  employee,
  domain,
  source,
  record,
  isDraft,
  hasPersonLink,
}: MigrationReviewSummaryPanelProps) {
  const hasItem = record != null;
  const unavailableReason = migrationHrCommitUnavailableReason({
    hasItem,
    isDraft,
    hasPersonLink,
  });
  const isReady = unavailableReason == null;

  return (
    <section
      aria-label={MIGRATION_REVIEW_SUMMARY_TITLE}
      className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
      data-testid="migration-review-summary"
    >
      <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
        {MIGRATION_REVIEW_SUMMARY_TITLE}
      </h2>
      <dl className="mt-4 grid gap-4 sm:grid-cols-2">
        <SummaryField label="Сотрудник" value={employee.fio?.trim() || "—"} />
        <SummaryField label="Тип кадровых данных" value={domain.display_name} />
        <SummaryField label="Источник записи" value={migrationHrSessionEntrySourceLabel(source)} />
        <SummaryField
          label="Импортированная запись"
          value={record ? migrationCandidateSummary(record) : "—"}
        />
        <div className="sm:col-span-2">
          <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Статус готовности
          </dt>
          <dd className="mt-1">
            {isReady ? (
              <span className="inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-200">
                {MIGRATION_REVIEW_READINESS_READY}
              </span>
            ) : (
              <span className="text-sm text-amber-800 dark:text-amber-200">
                {unavailableReason}
              </span>
            )}
          </dd>
        </div>
      </dl>
    </section>
  );
}
