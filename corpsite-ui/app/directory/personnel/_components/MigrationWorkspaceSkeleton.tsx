"use client";

import type { ReactNode } from "react";

import type { NormalizedRecord } from "../_lib/importApi.client";
import { migrationCandidateSummary } from "../_lib/personnelMigrationCandidates";
import type { MigrationRunItem } from "../_lib/personnelMigrationApi.client";

type MigrationWorkspaceSkeletonProps = {
  record: NormalizedRecord | null;
  item: MigrationRunItem | null;
};

function Panel({
  title,
  children,
  testId,
}: {
  title: string;
  children: ReactNode;
  testId: string;
}) {
  return (
    <section
      aria-label={title}
      data-testid={testId}
      className="flex min-h-[220px] flex-col rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
    >
      <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{title}</h3>
      <div className="mt-3 flex-1 text-sm text-zinc-600 dark:text-zinc-400">{children}</div>
    </section>
  );
}

export default function MigrationWorkspaceSkeleton({
  record,
  item,
}: MigrationWorkspaceSkeletonProps) {
  return (
    <div className="space-y-4" data-testid="migration-workspace-skeleton">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.75fr)_minmax(0,1fr)]">
        <Panel title="Imported Record" testId="migration-panel-imported">
          {record ? (
            <div className="space-y-2">
              <p className="font-medium text-zinc-800 dark:text-zinc-200">
                {migrationCandidateSummary(record)}
              </p>
              <p className="text-xs text-zinc-500">
                normalized_record_id: {record.normalized_record_id}
              </p>
              <p className="rounded-lg border border-dashed border-zinc-300 px-3 py-4 text-center text-xs dark:border-zinc-700">
                Полный просмотр импортированной записи — PMF-4E
              </p>
            </div>
          ) : (
            <p className="rounded-lg border border-dashed border-zinc-300 px-3 py-6 text-center text-xs dark:border-zinc-700">
              Импортированная запись появится после выбора кандидата.
            </p>
          )}
        </Panel>

        <Panel title="Mapping Status" testId="migration-panel-status">
          {item ? (
            <div className="space-y-2">
              <p>
                Черновик добавлен в сессию переноса (item #{item.item_id}).
              </p>
              <p className="text-xs text-zinc-500">Статус: {item.item_status}</p>
              <p className="rounded-lg border border-dashed border-zinc-300 px-3 py-4 text-center text-xs dark:border-zinc-700">
                Сопоставление полей и валидация — PMF-4E
              </p>
            </div>
          ) : (
            <p className="rounded-lg border border-dashed border-zinc-300 px-3 py-6 text-center text-xs dark:border-zinc-700">
              Статус сопоставления появится после добавления записи.
            </p>
          )}
        </Panel>

        <Panel title="Personnel Card" testId="migration-panel-personnel">
          <p className="rounded-lg border border-dashed border-zinc-300 px-3 py-6 text-center text-xs dark:border-zinc-700">
            Целевые поля кадровой карточки — PMF-4E
          </p>
        </Panel>
      </div>
    </div>
  );
}
