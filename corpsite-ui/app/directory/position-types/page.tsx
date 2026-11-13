"use client";

import * as React from "react";
import { apiFetchJson } from "@/lib/api";

type PositionType = { code: number; name: string };

export default function PositionTypesPage() {
  const [items, setItems] = React.useState<PositionType[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => {
    let active = true;
    apiFetchJson<{items: PositionType[]}>("/directory/position-types")
      .then(data => { if (active) setItems(data.items); })
      .catch(() => { if (active) setError("Не удалось загрузить справочник типов."); });
    return () => { active = false; };
  }, []);
  return (
    <main className="p-6 text-zinc-900 dark:text-zinc-50">
      <h1 className="mb-5 text-2xl font-semibold">Тип</h1>
      {error && <p role="alert" className="text-red-700 dark:text-red-300">{error}</p>}
      <table className="w-full max-w-xl border-collapse text-left text-sm">
        <thead><tr className="border-b border-zinc-300 dark:border-zinc-700"><th className="p-2">Код</th><th className="p-2">Название</th></tr></thead>
        <tbody>{items.map(item => <tr key={item.code} className="border-b border-zinc-200 dark:border-zinc-800"><td className="p-2">{item.code}</td><td className="p-2">{item.name}</td></tr>)}</tbody>
      </table>
    </main>
  );
}
