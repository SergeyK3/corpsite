"use client";

import * as React from "react";

import { formatPersonnelApplicationDateTime } from "../_lib/personnelApplicationLabels";
import {
  getApplicationTimeline,
  mapPersonnelApplicationsApiError,
  type TimelineEventItem,
} from "../_lib/personnelApplicationsApi.client";

type Props = {
  applicationId: number;
};

export default function PersonnelApplicationTimelineSection({ applicationId }: Props) {
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [items, setItems] = React.useState<TimelineEventItem[]>([]);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void getApplicationTimeline(applicationId)
      .then((body) => {
        if (!cancelled) setItems(body.items);
      })
      .catch((e) => {
        if (!cancelled) {
          setItems([]);
          setError(mapPersonnelApplicationsApiError(e, "Не удалось загрузить временную шкалу"));
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
      <section className="space-y-3" data-testid="personnel-application-timeline-loading">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Временная шкала</h3>
        <div className="h-16 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-900" />
      </section>
    );
  }

  return (
    <section className="space-y-3" data-testid="personnel-application-timeline">
      <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Временная шкала</h3>
      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      ) : null}
      {items.length === 0 ? (
        <p className="text-sm text-zinc-500">Событий пока нет.</p>
      ) : (
        <ol className="relative space-y-4 border-l border-zinc-200 pl-4 dark:border-zinc-700">
          {items.map((item, index) => (
            <li key={`${item.code}-${item.occurred_at}-${index}`} className="relative">
              <span className="absolute -left-[1.35rem] top-1.5 h-2.5 w-2.5 rounded-full bg-blue-600 ring-4 ring-white dark:ring-zinc-950" />
              <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{item.label}</div>
              <div className="text-xs text-zinc-500">{formatPersonnelApplicationDateTime(item.occurred_at)}</div>
              {item.detail ? <div className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{item.detail}</div> : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
