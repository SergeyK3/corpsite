"use client";

import type { PprEventSummaryResponse } from "../_lib/pprQueryTypes";
import { formatPprDateTime, pprEventTypeLabel } from "../_lib/pprCardPresentation";

type Props = {
  events: PprEventSummaryResponse | null;
};

export default function PprCardEventHistorySection({ events }: Props) {
  if (!events || events.recent.length === 0) {
    return <p className="text-sm text-zinc-500">События изменений пока отсутствуют.</p>;
  }

  return (
    <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
      {events.recent.map((event) => (
        <li key={event.event_id} className="py-3 text-sm">
          <div className="font-medium text-zinc-900 dark:text-zinc-50">
            {pprEventTypeLabel(event.event_type)}
          </div>
          <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
            {formatPprDateTime(event.occurred_at)}
            {event.section_code ? ` · ${event.section_code}` : ""}
          </div>
        </li>
      ))}
    </ul>
  );
}
