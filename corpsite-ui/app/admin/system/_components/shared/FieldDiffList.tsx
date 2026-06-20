// FILE: corpsite-ui/app/admin/system/_components/shared/FieldDiffList.tsx
"use client";

import { formatFieldValue } from "../../_lib/adminSystemLabels";

type DiffEntry = {
  employee?: unknown;
  assignment?: unknown;
  from?: unknown;
  to?: unknown;
};

type FieldDiffListProps = {
  diff?: Record<string, DiffEntry> | null;
  changedFields?: Record<string, { from?: unknown; to?: unknown }> | null;
  emptyLabel?: string;
};

export default function FieldDiffList({
  diff,
  changedFields,
  emptyLabel = "—",
}: FieldDiffListProps) {
  const entries = changedFields
    ? Object.entries(changedFields).map(([field, v]) => ({
        field,
        from: v.from,
        to: v.to,
      }))
    : Object.entries(diff ?? {}).map(([field, v]) => ({
        field,
        from: v.employee ?? v.from,
        to: v.assignment ?? v.to,
      }));

  if (!entries.length) {
    return <span className="text-zinc-500">{emptyLabel}</span>;
  }

  return (
    <ul className="space-y-1 text-xs">
      {entries.map(({ field, from, to }) => (
        <li key={field}>
          <span className="font-medium">{field}</span>:{" "}
          <span className="text-zinc-500">{formatFieldValue(from)}</span>
          <span className="mx-1">→</span>
          <span>{formatFieldValue(to)}</span>
        </li>
      ))}
    </ul>
  );
}
