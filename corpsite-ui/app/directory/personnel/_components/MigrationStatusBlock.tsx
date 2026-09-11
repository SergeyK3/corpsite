"use client";
import type { MigrationCell } from "../_lib/migrationStatusApi.client";

export default function MigrationStatusBlock({ cell }: { cell?: MigrationCell }) {
  if (!cell) return null;
  return <div className="mb-3 rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700" data-testid="ppr-migration-status-block">
    <div><strong>Состояние миграции: {cell.status_label}</strong></div>
    <div>{cell.reason_label}</div><div className="text-xs text-zinc-500">Рассчитано: {new Date(cell.calculated_at).toLocaleString("ru-RU")}</div>
  </div>;
}
