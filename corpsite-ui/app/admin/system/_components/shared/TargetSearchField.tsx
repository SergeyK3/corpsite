// FILE: corpsite-ui/app/admin/system/_components/shared/TargetSearchField.tsx
"use client";

import { useEffect, useState } from "react";

import {
  searchAccessTargets,
  type AccessTargetSearchItem,
} from "../../_lib/adminSystemApi.client";

type TargetSearchFieldProps = {
  targetType: string;
  value: AccessTargetSearchItem | null;
  onChange: (item: AccessTargetSearchItem | null) => void;
  label?: string;
};

export default function TargetSearchField({
  targetType,
  value,
  onChange,
  label = "Target",
}: TargetSearchFieldProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<AccessTargetSearchItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void (async () => {
        setLoading(true);
        try {
          const res = await searchAccessTargets({
            target_type: targetType,
            q: query,
            limit: 15,
          });
          setResults(res.items);
        } catch {
          setResults([]);
        } finally {
          setLoading(false);
        }
      })();
    }, 300);
    return () => window.clearTimeout(timer);
  }, [query, targetType]);

  useEffect(() => {
    onChange(null);
    setQuery("");
    setResults([]);
  }, [targetType]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="text-sm">
      <span className="font-medium">{label}</span>
      {value ? (
        <div className="mt-1 flex items-center justify-between rounded border border-green-300 bg-green-50 px-2 py-1 dark:border-green-800 dark:bg-green-950/30">
          <span>
            #{value.target_id} — {value.label}
            {value.subtitle ? ` (${value.subtitle})` : ""}
          </span>
          <button type="button" className="text-xs underline" onClick={() => onChange(null)}>
            сменить
          </button>
        </div>
      ) : (
        <>
          <input
            type="search"
            placeholder={`Поиск ${targetType}…`}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
          />
          {loading ? <p className="mt-1 text-xs text-zinc-500">Поиск…</p> : null}
          {results.length > 0 ? (
            <ul className="mt-1 max-h-40 overflow-auto rounded border dark:border-zinc-700">
              {results.map((item) => (
                <li key={`${item.target_type}-${item.target_id}`}>
                  <button
                    type="button"
                    className="block w-full px-2 py-1 text-left text-xs hover:bg-zinc-100 dark:hover:bg-zinc-800"
                    onClick={() => {
                      onChange(item);
                      setQuery("");
                      setResults([]);
                    }}
                  >
                    <strong>#{item.target_id}</strong> {item.label}
                    {item.subtitle ? ` — ${item.subtitle}` : ""}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </>
      )}
    </div>
  );
}
