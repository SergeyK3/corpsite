// PMF-4E — post-commit success state.
"use client";

import Link from "next/link";

import type { EmployeeDetails } from "@/app/directory/employees/_lib/types";

import type { MigrationDomainRow } from "../_lib/personnelMigrationApi.client";
import type { NormalizedRecord } from "../_lib/importApi.client";
import { migrationCandidateSummary } from "../_lib/personnelMigrationCandidates";
import {
  MIGRATION_COMMIT_SUCCESS_MESSAGE,
  MIGRATION_COMMIT_SUCCESS_TITLE,
} from "../_lib/personnelMigrationHrLabels";

type MigrationCommitSuccessPanelProps = {
  employee: EmployeeDetails;
  employeeId: number;
  domain: MigrationDomainRow;
  record: NormalizedRecord | null;
};

function SuccessField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="mt-1 text-sm text-zinc-900 dark:text-zinc-100">{value || "—"}</dd>
    </div>
  );
}

export default function MigrationCommitSuccessPanel({
  employee,
  employeeId,
  domain,
  record,
}: MigrationCommitSuccessPanelProps) {
  return (
    <section
      aria-label={MIGRATION_COMMIT_SUCCESS_TITLE}
      className="rounded-xl border border-emerald-200 bg-emerald-50/80 p-4 dark:border-emerald-900 dark:bg-emerald-950/30"
      data-testid="migration-commit-success"
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-sm font-bold text-white"
        >
          ✓
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold text-emerald-900 dark:text-emerald-100">
            {MIGRATION_COMMIT_SUCCESS_TITLE}
          </h2>
          <p className="mt-2 text-sm text-emerald-800 dark:text-emerald-200">
            {MIGRATION_COMMIT_SUCCESS_MESSAGE}
          </p>
        </div>
      </div>

      <dl className="mt-4 grid gap-4 border-t border-emerald-200/80 pt-4 sm:grid-cols-2 dark:border-emerald-900/60">
        <SuccessField label="Сотрудник" value={employee.fio?.trim() || "—"} />
        <SuccessField label="Тип кадровых данных" value={domain.display_name} />
        <SuccessField
          label="Перенесённая запись"
          value={record ? migrationCandidateSummary(record) : "—"}
        />
        <SuccessField label="Статус" value="Перенесено" />
      </dl>

      <div className="mt-4 flex flex-wrap gap-3">
        <Link
          href={`/directory/staff?employeeId=${employeeId}`}
          className="inline-flex rounded-lg bg-emerald-700 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-800"
        >
          Открыть личную карточку
        </Link>
        <Link
          href="/directory/personnel/import/review"
          className="inline-flex rounded-lg border border-emerald-300 bg-white px-3 py-2 text-sm font-medium text-emerald-900 hover:bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-100 dark:hover:bg-emerald-900"
        >
          ← Проверка записей
        </Link>
      </div>
    </section>
  );
}
