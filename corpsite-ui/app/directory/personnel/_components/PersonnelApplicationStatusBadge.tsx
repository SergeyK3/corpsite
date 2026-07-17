"use client";

import {
  directorResolutionLabel,
  personnelApplicationStatusBadgeClass,
  personnelApplicationStatusLabel,
} from "../_lib/personnelApplicationLabels";

type Props = {
  status: string;
  className?: string;
};

export default function PersonnelApplicationStatusBadge({ status, className = "" }: Props) {
  return (
    <span
      className={[
        "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium",
        personnelApplicationStatusBadgeClass(status),
        className,
      ].join(" ")}
    >
      {personnelApplicationStatusLabel(status)}
    </span>
  );
}

export function DirectorResolutionBadge({ status }: { status: string | null | undefined }) {
  const label = directorResolutionLabel(status);
  if (!status) {
    return (
      <span className="inline-flex rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400">
        —
      </span>
    );
  }
  const tone =
    status === "approved"
      ? "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200"
      : status === "rejected"
        ? "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200"
        : status === "revision_requested"
          ? "bg-orange-100 text-orange-900 dark:bg-orange-950 dark:text-orange-200"
          : "bg-zinc-100 text-zinc-700 dark:bg-zinc-900 dark:text-zinc-300";
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${tone}`}>{label}</span>
  );
}
