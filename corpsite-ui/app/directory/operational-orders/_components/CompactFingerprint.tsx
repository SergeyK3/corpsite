"use client";

import * as React from "react";

type Props = {
  value: string | null | undefined;
  label?: string;
};

export function fingerprintShort(value: string | null | undefined): string {
  if (!value) return "—";
  if (value.length <= 12) return value;
  return `${value.slice(0, 4)}…${value.slice(-4)}`;
}

export default function CompactFingerprint({ value, label = "fingerprint" }: Props) {
  const [expanded, setExpanded] = React.useState(false);
  const [copied, setCopied] = React.useState(false);

  if (!value) return <span className="text-zinc-400">—</span>;

  async function copyFull() {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }

  return (
    <span className="inline-flex flex-wrap items-center gap-1 text-xs text-zinc-500" data-testid="compact-fingerprint">
      <span className="text-zinc-400">{label}:</span>
      <code>{expanded ? value : fingerprintShort(value)}</code>
      <button type="button" className="rounded border px-1 py-0.5 text-[10px] hover:bg-zinc-100 dark:hover:bg-zinc-800" onClick={() => setExpanded((v) => !v)}>
        {expanded ? "Свернуть" : "Показать"}
      </button>
      <button type="button" className="rounded border px-1 py-0.5 text-[10px] hover:bg-zinc-100 dark:hover:bg-zinc-800" onClick={() => void copyFull()}>
        {copied ? "Скопировано" : "Копировать"}
      </button>
    </span>
  );
}
