"use client";

import {
  MONTHLY_DIFF_STATUS_LABELS,
  isMonthlyDiffStatus,
  monthlyDiffStatusBadgeClass,
  type MonthlyDiffStatus,
} from "../_lib/monthlyDiffLabels";

type Props = {
  status: string | null | undefined;
  compact?: boolean;
};

export default function ImportDiffStatusBadge({ status, compact = false }: Props) {
  if (!status || !isMonthlyDiffStatus(status)) {
    return <span className="text-xs text-zinc-400">—</span>;
  }

  const diffStatus = status as MonthlyDiffStatus;
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 font-medium ${compact ? "text-[10px]" : "text-xs"} ${monthlyDiffStatusBadgeClass(diffStatus)}`}
      title={MONTHLY_DIFF_STATUS_LABELS[diffStatus]}
    >
      {MONTHLY_DIFF_STATUS_LABELS[diffStatus]}
    </span>
  );
}
