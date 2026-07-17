"use client";

import * as React from "react";
import Link from "next/link";

import {
  formatPersonnelApplicationDate,
  formatPersonnelApplicationDateTime,
} from "../_lib/personnelApplicationLabels";
import { buildPersonnelApplicationsJournalHref } from "../_lib/personnelApplicationsJournalNav";
import {
  getPersonApplicationsHistory,
  mapPersonnelApplicationsApiError,
  type PersonnelApplicationDetail,
} from "../_lib/personnelApplicationsApi.client";
import PersonnelApplicationStatusBadge from "./PersonnelApplicationStatusBadge";

type Props = {
  personId: number;
};

function formatIntendedPlacement(item: PersonnelApplicationDetail): string {
  const parts = [
    item.intended_org_unit_name || item.intended_org_group_name,
    item.intended_position_name,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : "—";
}

export default function PprCardApplicationsSection({ personId }: Props) {
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [items, setItems] = React.useState<PersonnelApplicationDetail[]>([]);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void getPersonApplicationsHistory(personId)
      .then((body) => {
        if (!cancelled) setItems(Array.isArray(body.items) ? body.items : []);
      })
      .catch((e) => {
        if (!cancelled) {
          setItems([]);
          setError(mapPersonnelApplicationsApiError(e, "Не удалось загрузить историю обращений"));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [personId]);

  if (loading) {
    return (
      <div className="space-y-2" data-testid="ppr-applications-section-loading">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="h-12 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-900" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200"
        data-testid="ppr-applications-section-error"
      >
        {error}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <p className="text-sm text-zinc-500" data-testid="ppr-applications-section-empty">
        Кадровых обращений по этой персоне пока нет.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto" data-testid="ppr-applications-section">
      <table className="min-w-full divide-y divide-zinc-200 text-sm dark:divide-zinc-800">
        <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900/60">
          <tr>
            <th className="px-3 py-2">Дата</th>
            <th className="px-3 py-2">Статус</th>
            <th className="px-3 py-2">Предполагаемое место работы</th>
            <th className="px-3 py-2">HR</th>
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100 dark:divide-zinc-900">
          {items.map((item) => (
            <tr key={item.application_id} data-testid={`ppr-application-row-${item.application_id}`}>
              <td className="px-3 py-2">{formatPersonnelApplicationDate(item.application_received_at)}</td>
              <td className="px-3 py-2">
                <PersonnelApplicationStatusBadge status={item.status} />
              </td>
              <td className="px-3 py-2">{formatIntendedPlacement(item)}</td>
              <td className="px-3 py-2">
                {item.registered_by_name || `#${item.registered_by_user_id}`}
                <div className="text-xs text-zinc-500">
                  {formatPersonnelApplicationDateTime(item.registered_at)}
                </div>
              </td>
              <td className="px-3 py-2 text-right">
                <Link
                  href={buildPersonnelApplicationsJournalHref({
                    q: "",
                    sort: "application_received_at_desc",
                    limit: 50,
                    offset: 0,
                    application_id: item.application_id,
                  })}
                  className="text-blue-700 hover:underline dark:text-blue-300"
                  data-testid={`ppr-application-open-${item.application_id}`}
                >
                  Открыть
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
