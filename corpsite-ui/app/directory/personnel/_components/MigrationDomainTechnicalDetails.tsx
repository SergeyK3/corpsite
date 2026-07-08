// PMF-4B.1 — collapsed technical details (admin/support).
"use client";

import type { MigrationDomainRow } from "../_lib/personnelMigrationApi.client";
import {
  migrationTechnicalControlListColumns,
  migrationTechnicalDescription,
  migrationTechnicalDomainCode,
  migrationTechnicalRegistryEnabled,
  migrationTechnicalTargetTables,
} from "../_lib/personnelMigrationLabels";

type MigrationDomainTechnicalDetailsProps = {
  domain: MigrationDomainRow;
};

export default function MigrationDomainTechnicalDetails({ domain }: MigrationDomainTechnicalDetailsProps) {
  const targetTables = migrationTechnicalTargetTables(domain);
  const controlColumns = migrationTechnicalControlListColumns(domain);
  const registryDescription = migrationTechnicalDescription(domain);

  return (
    <details className="mt-4 rounded-lg border border-zinc-200 bg-zinc-50/60 dark:border-zinc-800 dark:bg-zinc-900/30">
      <summary className="cursor-pointer select-none px-3 py-2 text-xs font-medium text-zinc-600 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200">
        Техническая информация
      </summary>
      <dl className="space-y-2 border-t border-zinc-200 px-3 py-3 text-xs dark:border-zinc-800">
        <div>
          <dt className="font-medium text-zinc-500">Код типа (domain)</dt>
          <dd className="mt-0.5 font-mono text-zinc-800 dark:text-zinc-200">{migrationTechnicalDomainCode(domain)}</dd>
        </div>
        <div>
          <dt className="font-medium text-zinc-500">Включён в реестре</dt>
          <dd className="mt-0.5 text-zinc-800 dark:text-zinc-200">
            {migrationTechnicalRegistryEnabled(domain) ? "да" : "нет"}
          </dd>
        </div>
        {registryDescription ? (
          <div>
            <dt className="font-medium text-zinc-500">Описание в реестре</dt>
            <dd className="mt-0.5 text-zinc-800 dark:text-zinc-200">{registryDescription}</dd>
          </div>
        ) : null}
        <div>
          <dt className="font-medium text-zinc-500">Целевые таблицы</dt>
          <dd className="mt-0.5 font-mono text-zinc-800 dark:text-zinc-200">
            {targetTables.length > 0 ? targetTables.join(", ") : "—"}
          </dd>
        </div>
        <div>
          <dt className="font-medium text-zinc-500">Колонки контрольного списка</dt>
          <dd className="mt-0.5 font-mono text-zinc-800 dark:text-zinc-200">
            {controlColumns.length > 0 ? controlColumns.join(", ") : "—"}
          </dd>
        </div>
      </dl>
    </details>
  );
}
