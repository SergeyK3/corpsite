"use client";

import * as React from "react";

import {
  formatPersonnelApplicationDateTime,
  personnelApplicationStatusLabel,
} from "../_lib/personnelApplicationLabels";
import {
  getLifecycleAudit,
  mapPersonnelApplicationsApiError,
  type CombinedAuditItem,
} from "../_lib/personnelApplicationsApi.client";

type Props = {
  applicationId: number;
};

function auditActionLabel(item: CombinedAuditItem): string {
  if (item.source === "resolution") {
    return `Резолюция: ${item.action}`;
  }
  return item.action;
}

export default function PersonnelApplicationLifecycleAuditSection({ applicationId }: Props) {
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [items, setItems] = React.useState<CombinedAuditItem[]>([]);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void getLifecycleAudit(applicationId)
      .then((body) => {
        if (!cancelled) setItems(body.items);
      })
      .catch((e) => {
        if (!cancelled) {
          setItems([]);
          setError(mapPersonnelApplicationsApiError(e, "Не удалось загрузить audit"));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [applicationId]);

  if (loading) {
    return (
      <section className="space-y-3" data-testid="personnel-application-lifecycle-audit-loading">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">История audit</h3>
        <div className="h-16 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-900" />
      </section>
    );
  }

  return (
    <section className="space-y-3" data-testid="personnel-application-lifecycle-audit">
      <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">История audit</h3>
      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      ) : null}
      {items.length === 0 ? (
        <p className="text-sm text-zinc-500">Записей audit пока нет.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
          <table className="min-w-full divide-y divide-zinc-200 text-sm dark:divide-zinc-800">
            <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900/60">
              <tr>
                <th className="px-3 py-2">Дата</th>
                <th className="px-3 py-2">Источник</th>
                <th className="px-3 py-2">Действие</th>
                <th className="px-3 py-2">Статус</th>
                <th className="px-3 py-2">Комментарий</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-900">
              {items.map((item) => (
                <tr key={`${item.source}-${item.audit_id}`}>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {formatPersonnelApplicationDateTime(item.created_at)}
                  </td>
                  <td className="px-3 py-2">{item.source}</td>
                  <td className="px-3 py-2">{auditActionLabel(item)}</td>
                  <td className="px-3 py-2">
                    {item.previous_status ? personnelApplicationStatusLabel(item.previous_status) : "—"}
                    {" → "}
                    {item.new_status ? personnelApplicationStatusLabel(item.new_status) : "—"}
                  </td>
                  <td className="px-3 py-2">{item.comment || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
