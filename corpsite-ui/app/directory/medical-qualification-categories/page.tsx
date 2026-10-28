"use client";

import * as React from "react";
import ExportExcelButton from "@/components/ExportExcelButton";
import { apiFetchJson } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";
import type { ExcelTable } from "@/lib/tableExport";

type Category = { qualification_category_id: number; code: number; name: string; name_kk: string };
type List = { items: Category[]; total: number };
const API = "/directory/medical-qualification-categories";
const headers = ["ID", "Код", "На русском языке", "Қазақша атауы"];

export default function MedicalQualificationCategoriesPage() {
  const [search, setSearch] = React.useState("");
  const [data, setData] = React.useState<List>({ items: [], total: 0 });
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    let live = true;
    setLoading(true);
    setError("");
    apiFetchJson<List>(API, { query: { q: search || undefined } })
      .then(result => { if (live) setData(result); })
      .catch(exc => { if (live) { setError(formatThrownError(exc)); setData({ items: [], total: 0 }); } })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [search]);

  async function loadExcel(): Promise<ExcelTable> {
    const result = await apiFetchJson<List>(API, { query: { q: search || undefined } });
    return { headers, rows: result.items.map(row => [row.qualification_category_id, row.code, row.name, row.name_kk]) };
  }

  return <div className="space-y-4 p-4 text-zinc-900 dark:text-zinc-50">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-2xl font-semibold">Категории квалификации медработников</h1>
      <ExportExcelButton load={loadExcel} filename="Категории_квалификации_медработников.xlsx" disabled={loading || !!error} />
    </div>
    <div className="flex flex-wrap gap-3">
      <label className="flex flex-col gap-1 text-sm">Поиск по RU / KK
        <input className="rounded-lg border border-zinc-200 bg-transparent px-3 py-2 dark:border-zinc-700" value={search} placeholder="Русское или казахское название" onChange={event => setSearch(event.target.value)} />
      </label>
    </div>
    <p className="text-sm text-zinc-600 dark:text-zinc-400">Фиксированный справочник: 4 категории.</p>
    {error && <p role="alert">{error}</p>}
    <p role="status">{loading ? "Загрузка…" : error ? "Не удалось загрузить справочник." : `Всего: ${data.total}`}</p>
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
      <table className="w-full text-left text-sm">
        <thead className="bg-zinc-100 dark:bg-zinc-900"><tr>{headers.map(header => <th key={header} scope="col" className="px-3 py-2">{header}</th>)}</tr></thead>
        <tbody>{!loading && data.items.map(row => <tr key={row.qualification_category_id} className="border-t border-zinc-200 dark:border-zinc-700">
          {[row.qualification_category_id, row.code, row.name, row.name_kk].map((value, index) => <td key={index} className="px-3 py-2">{value}</td>)}
        </tr>)}</tbody>
      </table>
      {!loading && !data.items.length && !error && <p className="p-3">Категории не найдены.</p>}
    </div>
  </div>;
}
