// FILE: corpsite-ui/app/admin/system/_components/shared/JsonViewer.tsx
"use client";

type JsonViewerProps = {
  value: unknown;
  title?: string;
  emptyMessage?: string;
  testId?: string;
};

function formatJson(value: unknown): string {
  if (value === null || value === undefined) return "null";
  if (typeof value === "string") {
    try {
      return JSON.stringify(JSON.parse(value), null, 2);
    } catch {
      return value;
    }
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export default function JsonViewer({
  value,
  title,
  emptyMessage = "Нет данных",
  testId,
}: JsonViewerProps) {
  const isEmpty =
    value === null ||
    value === undefined ||
    (typeof value === "object" && !Array.isArray(value) && Object.keys(value as object).length === 0) ||
    (Array.isArray(value) && value.length === 0);

  return (
    <div className="space-y-1" data-testid={testId}>
      {title ? <div className="text-xs font-medium text-zinc-600 dark:text-zinc-400">{title}</div> : null}
      {isEmpty ? (
        <p className="text-sm text-zinc-500">{emptyMessage}</p>
      ) : (
        <pre className="max-h-96 overflow-auto rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs leading-relaxed dark:border-zinc-700 dark:bg-zinc-900">
          {formatJson(value)}
        </pre>
      )}
    </div>
  );
}
