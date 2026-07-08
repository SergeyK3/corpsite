// PMF-4B.1 — HR data-type card on Migration Home.
"use client";

import type { MigrationDomainRow } from "../_lib/personnelMigrationApi.client";
import {
  migrationHrDomainStatus,
  migrationHrDomainStatusBadgeClass,
  migrationHrDomainStatusHint,
  migrationHrDomainStatusLabel,
  migrationHrTransferItems,
} from "../_lib/personnelMigrationHrLabels";
import MigrationDomainTechnicalDetails from "./MigrationDomainTechnicalDetails";

type MigrationDomainCardProps = {
  domain: MigrationDomainRow;
};

export default function MigrationDomainCard({ domain }: MigrationDomainCardProps) {
  const status = migrationHrDomainStatus(domain);
  const transferItems = migrationHrTransferItems(domain);
  const canSelectEmployee = status === "available";

  return (
    <article className="flex h-full flex-col rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{domain.display_name}</h2>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${migrationHrDomainStatusBadgeClass(status)}`}
        >
          {migrationHrDomainStatusLabel(status)}
        </span>
      </div>

      <div className="mt-4">
        <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">Что переносится</h3>
        <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-zinc-700 dark:text-zinc-300">
          {transferItems.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>

      <p className="mt-4 text-sm text-zinc-600 dark:text-zinc-400">{migrationHrDomainStatusHint(status)}</p>

      <MigrationDomainTechnicalDetails domain={domain} />

      <div className="mt-auto border-t border-zinc-100 pt-4 dark:border-zinc-800">
        <button
          type="button"
          disabled={!canSelectEmployee}
          title={
            canSelectEmployee
              ? "Выбор сотрудника будет доступен на следующем этапе"
              : "Раздел ожидает включения администратором"
          }
          className={[
            "w-full rounded-lg px-3 py-2 text-sm font-medium transition",
            canSelectEmployee
              ? "cursor-not-allowed bg-zinc-100 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400"
              : "cursor-not-allowed bg-zinc-100 text-zinc-400 dark:bg-zinc-900 dark:text-zinc-600",
          ].join(" ")}
        >
          {canSelectEmployee ? "Выбрать сотрудника" : "Начать перенос"}
        </button>
        <p className="mt-2 text-center text-[11px] text-zinc-500">
          {canSelectEmployee
            ? "Будет доступно на следующем этапе"
            : status === "awaiting_enablement"
              ? "Ожидает включения администратором"
              : "Скоро"}
        </p>
      </div>
    </article>
  );
}
