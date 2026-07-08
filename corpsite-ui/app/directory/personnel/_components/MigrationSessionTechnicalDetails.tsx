// PMF-4C / PMF-4E — session technical details (collapsed).
"use client";

import type { MigrationEntrySource } from "../_lib/personnelMigrationEntry";
import type { MigrationRun } from "../_lib/personnelMigrationApi.client";
import { migrationTechnicalRunStatus } from "../_lib/personnelMigrationLabels";

type MigrationSessionTechnicalDetailsProps = {
  domainCode: string;
  employeeId: number;
  run: MigrationRun | null;
  source: MigrationEntrySource;
  candidateId: string | null;
  lastError?: string | null;
};

export default function MigrationSessionTechnicalDetails({
  domainCode,
  employeeId,
  run,
  source,
  candidateId,
  lastError = null,
}: MigrationSessionTechnicalDetailsProps) {
  const itemCount = run?.items?.length ?? 0;
  const hasDraftItem = (run?.items ?? []).some((item) => item.item_status === "draft");

  return (
    <details className="rounded-lg border border-zinc-200 bg-zinc-50/60 dark:border-zinc-800 dark:bg-zinc-900/30">
      <summary className="cursor-pointer select-none px-3 py-2 text-xs font-medium text-zinc-600 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200">
        Техническая информация
      </summary>
      <dl className="space-y-2 border-t border-zinc-200 px-3 py-3 text-xs dark:border-zinc-800">
        <div>
          <dt className="font-medium text-zinc-500">domainCode</dt>
          <dd className="mt-0.5 font-mono text-zinc-800 dark:text-zinc-200">{domainCode}</dd>
        </div>
        <div>
          <dt className="font-medium text-zinc-500">employeeId</dt>
          <dd className="mt-0.5 font-mono text-zinc-800 dark:text-zinc-200">{employeeId}</dd>
        </div>
        <div>
          <dt className="font-medium text-zinc-500">run_id</dt>
          <dd className="mt-0.5 font-mono text-zinc-800 dark:text-zinc-200">{run?.run_id ?? "—"}</dd>
        </div>
        <div>
          <dt className="font-medium text-zinc-500">run status</dt>
          <dd className="mt-0.5 font-mono text-zinc-800 dark:text-zinc-200">
            {run ? migrationTechnicalRunStatus(run.run_status) : "—"}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-zinc-500">commit status</dt>
          <dd className="mt-0.5 font-mono text-zinc-800 dark:text-zinc-200">
            {run?.run_status === "committed"
              ? "committed"
              : run?.run_status === "draft"
                ? "pending"
                : run
                  ? migrationTechnicalRunStatus(run.run_status)
                  : "—"}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-zinc-500">item presence</dt>
          <dd className="mt-0.5 font-mono text-zinc-800 dark:text-zinc-200">
            {itemCount > 0 ? `yes (${itemCount})` : "no"}
            {hasDraftItem ? " · draft item present" : ""}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-zinc-500">source</dt>
          <dd className="mt-0.5 font-mono text-zinc-800 dark:text-zinc-200">{source}</dd>
        </div>
        <div>
          <dt className="font-medium text-zinc-500">candidate_id</dt>
          <dd className="mt-0.5 break-all font-mono text-zinc-800 dark:text-zinc-200">
            {candidateId ?? "—"}
          </dd>
        </div>
        {lastError ? (
          <div>
            <dt className="font-medium text-zinc-500">last error</dt>
            <dd className="mt-0.5 break-all font-mono text-red-700 dark:text-red-300">{lastError}</dd>
          </div>
        ) : null}
      </dl>
    </details>
  );
}
