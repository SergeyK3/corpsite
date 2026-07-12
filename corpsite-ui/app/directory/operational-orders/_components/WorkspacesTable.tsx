"use client";

import Link from "next/link";

import type { WorkspaceSummary } from "../_lib/types";
import { formatDateTime, languageCoverageLabel } from "../_lib/mappers";
import { draftingPathLabel } from "../_lib/status";
import WorkspaceStageBadge from "./WorkspaceStageBadge";

type Props = {
  items: WorkspaceSummary[];
  loading: boolean;
  emptyMessage?: string;
};

export default function WorkspacesTable({ items, loading, emptyMessage }: Props) {
  if (loading) {
    return (
      <div className="rounded-xl border px-4 py-8 text-center text-sm text-zinc-500" data-testid="oo-workspaces-loading">
        Загрузка рабочих проектов…
      </div>
    );
  }

  if (!items.length) {
    return (
      <div
        className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-zinc-500"
        data-testid="oo-workspaces-empty"
      >
        {emptyMessage ?? "Рабочие проекты не найдены"}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800" data-testid="oo-workspaces-table">
      <table className="min-w-full text-sm">
        <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
          <tr>
            <th className="px-3 py-2">ID</th>
            <th className="px-3 py-2">Название</th>
            <th className="px-3 py-2">Подразделение</th>
            <th className="px-3 py-2">Автор</th>
            <th className="px-3 py-2">Создатель</th>
            <th className="px-3 py-2">Путь</th>
            <th className="px-3 py-2">Стадия</th>
            <th className="px-3 py-2">Языки</th>
            <th className="px-3 py-2">Уточнения</th>
            <th className="px-3 py-2">Перевод</th>
            <th className="px-3 py-2">Создан</th>
            <th className="px-3 py-2">Обновлён</th>
            <th className="px-3 py-2">Ver</th>
            <th className="px-3 py-2">Документ</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.workspace_id}
              className="border-t border-zinc-100 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900/50"
              data-testid={`oo-workspace-row-${item.workspace_id}`}
            >
              <td className="px-3 py-2">
                <Link href={`/directory/operational-orders/workspaces/${item.workspace_id}`} className="text-blue-600 hover:underline">
                  {item.workspace_id}
                </Link>
              </td>
              <td className="px-3 py-2">{item.proposed_title || "—"}</td>
              <td className="px-3 py-2">#{item.submitting_org_unit_id}</td>
              <td className="px-3 py-2 text-xs">{item.content_author_reference}</td>
              <td className="px-3 py-2">#{item.record_creator_user_id}</td>
              <td className="px-3 py-2">{draftingPathLabel(item.drafting_path)}</td>
              <td className="px-3 py-2">
                <WorkspaceStageBadge stage={item.stage} />
              </td>
              <td className="px-3 py-2">{languageCoverageLabel(item.ru_present, item.kk_present)}</td>
              <td className="px-3 py-2">{item.open_clarification_count ?? 0}</td>
              <td className="px-3 py-2">{item.has_active_translation ? "Да" : "—"}</td>
              <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(item.created_at)}</td>
              <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(item.updated_at)}</td>
              <td className="px-3 py-2">{item.version}</td>
              <td className="px-3 py-2">
                {item.document_id ? (
                  <Link href={`/directory/operational-orders/documents/${item.document_id}`} className="text-blue-600 hover:underline">
                    #{item.document_id}
                  </Link>
                ) : (
                  "—"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
