// PMF-4B — domain card on Migration Home.
"use client";

import type { MigrationDomainRow } from "../_lib/personnelMigrationApi.client";
import {
  migrationDomainDescription,
  migrationDomainEnabledLabel,
  migrationDomainReadiness,
  migrationDomainReadinessHint,
  migrationDomainReadinessLabel,
  migrationTargetTableCount,
} from "../_lib/personnelMigrationLabels";

type MigrationDomainCardProps = {
  domain: MigrationDomainRow;
  onStartMigration?: (domain: MigrationDomainRow) => void;
};

function enabledBadgeClass(isEnabled: boolean): string {
  return isEnabled
    ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200"
    : "border-zinc-200 bg-zinc-100 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400";
}

function readinessBadgeClass(readiness: ReturnType<typeof migrationDomainReadiness>): string {
  switch (readiness) {
    case "pilot_ready":
      return "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-200";
    case "active":
      return "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200";
    default:
      return "border-zinc-200 bg-zinc-100 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400";
  }
}

export default function MigrationDomainCard({ domain, onStartMigration }: MigrationDomainCardProps) {
  const readiness = migrationDomainReadiness(domain);
  const targetCount = migrationTargetTableCount(domain);
  const canStart = domain.is_enabled && readiness === "pilot_ready";

  return (
    <article className="flex h-full flex-col rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{domain.display_name}</h2>
          <p className="mt-0.5 font-mono text-xs text-zinc-500">{domain.domain_code}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span
            className={`rounded-full border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ${enabledBadgeClass(domain.is_enabled)}`}
          >
            {migrationDomainEnabledLabel(domain.is_enabled)}
          </span>
          <span
            className={`rounded-full border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ${readinessBadgeClass(readiness)}`}
          >
            {migrationDomainReadinessLabel(readiness)}
          </span>
        </div>
      </div>

      <p className="mt-3 flex-1 text-sm text-zinc-600 dark:text-zinc-400">{migrationDomainDescription(domain)}</p>

      <dl className="mt-4 grid gap-2 text-xs text-zinc-500 sm:grid-cols-2">
        <div>
          <dt className="font-medium uppercase tracking-wide">Целевые таблицы</dt>
          <dd className="mt-0.5 text-sm text-zinc-800 dark:text-zinc-200">{targetCount}</dd>
        </div>
        <div>
          <dt className="font-medium uppercase tracking-wide">Колонки КС</dt>
          <dd className="mt-0.5 text-sm text-zinc-800 dark:text-zinc-200">
            {domain.control_list_columns?.length ?? 0}
          </dd>
        </div>
      </dl>

      {domain.target_table_names.length > 0 ? (
        <p className="mt-2 font-mono text-[11px] text-zinc-500">{domain.target_table_names.join(", ")}</p>
      ) : null}

      <p className="mt-3 text-xs text-zinc-500">{migrationDomainReadinessHint(readiness)}</p>

      <div className="mt-4 border-t border-zinc-100 pt-4 dark:border-zinc-800">
        <button
          type="button"
          disabled={!canStart}
          onClick={() => onStartMigration?.(domain)}
          title={
            canStart
              ? "Выбор сотрудника и draft run — PMF-4C"
              : domain.is_enabled
                ? "Wizard для этого домена — в следующих WP"
                : "Домен отключён"
          }
          className={[
            "w-full rounded-lg px-3 py-2 text-sm font-medium transition",
            canStart
              ? "bg-blue-600 text-white hover:bg-blue-700"
              : "cursor-not-allowed bg-zinc-100 text-zinc-400 dark:bg-zinc-900 dark:text-zinc-600",
          ].join(" ")}
        >
          Начать миграцию
        </button>
        {!canStart ? (
          <p className="mt-2 text-center text-[11px] text-zinc-500">Сессия миграции — PMF-4C</p>
        ) : (
          <p className="mt-2 text-center text-[11px] text-zinc-500">Draft Run UI — PMF-4C</p>
        )}
      </div>
    </article>
  );
}
