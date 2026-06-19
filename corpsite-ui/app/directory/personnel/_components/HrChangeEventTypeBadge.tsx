"use client";

import { hrChangeEventBadgeClass, isHrChangeEventType } from "../_lib/hrChangeEventLabels";

type Props = {
  eventType: string;
};

export default function HrChangeEventTypeBadge({ eventType }: Props) {
  const normalized = String(eventType || "").trim().toUpperCase();
  const shortLabel = normalized.replace(/_CHANGED$/, "").slice(0, 12) || "—";
  const className = isHrChangeEventType(normalized)
    ? hrChangeEventBadgeClass(normalized)
    : "border-zinc-200 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300";

  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${className}`}
      title={normalized}
    >
      {shortLabel}
    </span>
  );
}
