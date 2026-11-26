"use client";

import * as React from "react";
import { apiFetchJson } from "@/lib/api";

type Historical = {application_id: number; personnel_order_id: number;
  source_title: string; intended_org_unit_id: number; order_status: string};

export default function HistoricalUnresolvedPage() {
  const [items, setItems] = React.useState<Historical[]>([]);
  const [error, setError] = React.useState("");
  React.useEffect(() => { void apiFetchJson<{items: Historical[]}>("/directory/electronic-hire/position-requests/historical-unresolved")
    .then(result => setItems(result.items)).catch(e => setError(String(e))); }, []);
  return <main className="mx-auto max-w-5xl space-y-4 bg-white p-6 text-zinc-900"><a href="/directory/personnel/position-reconciliation" className="underline">← Очередь уточнений</a><h1 className="text-2xl font-semibold">Исторические документы с несопоставленной должностью</h1><p className="text-sm text-zinc-600">Отчёт только для просмотра. Подписанные и зарегистрированные документы автоматически не меняются.</p>{error && <p role="alert" className="text-red-700">{error}</p>}<table className="w-full border-collapse text-left text-sm"><thead><tr><th className="border p-2">Заявление</th><th className="border p-2">Приказ</th><th className="border p-2">Исходное название</th><th className="border p-2">Отделение</th><th className="border p-2">Статус</th></tr></thead><tbody>{items.map(row => <tr key={row.application_id}><td className="border p-2">№{row.application_id}</td><td className="border p-2"><a className="underline" href={`/directory/personnel/orders?order_id=${row.personnel_order_id}`}>№{row.personnel_order_id}</a></td><td className="border p-2">{row.source_title}</td><td className="border p-2">№{row.intended_org_unit_id}</td><td className="border p-2">{row.order_status}</td></tr>)}</tbody></table>{items.length === 0 && !error && <p>Таких документов нет.</p>}</main>;
}
