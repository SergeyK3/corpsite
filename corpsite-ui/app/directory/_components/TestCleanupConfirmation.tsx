"use client";

import * as React from "react";

type PreviewState = {
  snapshot_hash: string;
  counts: Record<string, number>;
  blockers: string[];
  retained_counts?: Record<string, number>;
  file_count?: number;
};

export function useTestCleanupConfirmation(preview: PreviewState | null) {
  // Compare the complete preview, so a changed dependency resets confirmation
  // immediately during render, before the delete button can become active.
  const fingerprint = preview ? JSON.stringify(preview) : "";
  const [choice, setChoice] = React.useState({ fingerprint: "", checked: false });
  return {
    confirmed: !!preview && choice.fingerprint === fingerprint && choice.checked,
    setConfirmed: (checked: boolean) => setChoice({ fingerprint, checked }),
  };
}

export function groupedCleanupCounts(
  counts: Record<string, number> | undefined,
  labels: Record<string, string>,
  fallback: string,
): Array<[string, number]> {
  const grouped = new Map<string, number>();
  for (const [table, count] of Object.entries(counts ?? {})) {
    if (count <= 0) continue;
    const label = labels[table] ?? fallback;
    grouped.set(label, (grouped.get(label) ?? 0) + count);
  }
  return [...grouped];
}

export function TestCleanupConfirmationCheckbox({ checked, onChange }: {
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return <label className="flex items-start gap-2 text-sm">
    <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)}
      className="mt-0.5 h-4 w-4 accent-red-700" />
    <span>Подтверждаю окончательное удаление</span>
  </label>;
}
