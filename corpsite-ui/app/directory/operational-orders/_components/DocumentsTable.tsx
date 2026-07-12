"use client";

import Link from "next/link";

import type { DocumentSummary } from "../_lib/types";
import { formatDateTime } from "../_lib/mappers";
import DocumentStatusBadge from "./DocumentStatusBadge";

type Props = {
  items: DocumentSummary[];
  loading: boolean;
  emptyMessage?: string;
};

export default function DocumentsTable({ items, loading, emptyMessage }: Props) {
  if (loading) {
    return (
      <div className="rounded-xl border px-4 py-8 text-center text-sm text-zinc-500" data-testid="oo-documents-loading">
        Загрузка документов…
      </div>
    );
  }

  if (!items.length) {
    return (
      <div
        className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-zinc-500"
        data-testid="oo-documents-empty"
      >
        {emptyMessage ?? "Официальные документы не найдены"}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800" data-testid="oo-documents-table">
      <table className="min-w-full text-sm">
        <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
          <tr>
            <th className="px-3 py-2">ID</th>
            <th className="px-3 py-2">Workspace</th>
            <th className="px-3 py-2">Подразделение</th>
            <th className="px-3 py-2">Статус</th>
            <th className="px-3 py-2">Ver</th>
            <th className="px-3 py-2">Готов к подписи</th>
            <th className="px-3 py-2">Создан</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.document_id}
              className="border-t border-zinc-100 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900/50"
              data-testid={`oo-document-row-${item.document_id}`}
            >
              <td className="px-3 py-2">
                <Link href={`/directory/operational-orders/documents/${item.document_id}`} className="text-blue-600 hover:underline">
                  {item.document_id}
                </Link>
              </td>
              <td className="px-3 py-2">
                <Link href={`/directory/operational-orders/workspaces/${item.workspace_id}`} className="text-blue-600 hover:underline">
                  #{item.workspace_id}
                </Link>
              </td>
              <td className="px-3 py-2">#{item.submitting_org_unit_id ?? "—"}</td>
              <td className="px-3 py-2">
                <DocumentStatusBadge status={item.status} />
              </td>
              <td className="px-3 py-2">{item.version}</td>
              <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(item.ready_for_signature_at)}</td>
              <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(item.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
