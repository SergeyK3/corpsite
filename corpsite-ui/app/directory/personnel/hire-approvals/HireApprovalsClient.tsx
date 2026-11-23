"use client";

import * as React from "react";
import { listHireApprovals, recordHireVisa, type HireApprovalItem } from "../_lib/electronicHireApi.client";

export default function HireApprovalsClient() {
  const [items, setItems] = React.useState<HireApprovalItem[]>([]);
  const [notes, setNotes] = React.useState<Record<number, string>>({});
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState<number | null>(null);
  const load = React.useCallback(async () => {
    try { const result = await listHireApprovals(); setItems(result.items); setError(""); }
    catch (e) { setError(e instanceof Error ? e.message : "Не удалось загрузить заявления."); }
  }, []);
  React.useEffect(() => { void load(); }, [load]);

  async function decide(id: number, decision: "approved" | "rejected") {
    setBusy(id); setError("");
    try { await recordHireVisa(id, decision, notes[id]); await load(); }
    catch (e) { setError(e instanceof Error ? e.message : "Не удалось сохранить визу."); }
    finally { setBusy(null); }
  }

  return <main className="mx-auto max-w-5xl space-y-5 p-6 text-zinc-900">
    <h1 className="text-2xl font-semibold">Согласование заявлений о приёме</h1>
    <p className="text-sm text-zinc-600">Показаны заявления только вашего отделения. Решение сохраняет условия приёма и время визы.</p>
    {error && <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    {items.length === 0 && <p className="rounded border p-4 text-sm">Заявлений на согласование нет.</p>}
    {items.map(item => <section key={item.application_id} className="space-y-3 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2"><h2 className="font-semibold">Заявление №{item.application_id} · {item.full_name}</h2><span className="text-sm text-zinc-600">{item.current_visa?.is_current ? item.current_visa.decision === "approved" ? "Согласовано" : "Отказ" : "Ожидает решения"}</span></div>
      <p className="text-sm">{item.position} · {item.org_unit} · {item.employment_rate} ставки · с {item.planned_start_date}</p>
      <label className="block text-sm">Пояснение при отказе<textarea className="mt-1 w-full rounded border border-zinc-300 p-2" value={notes[item.application_id] || ""} onChange={e => setNotes({...notes, [item.application_id]: e.target.value})} /></label>
      <div className="flex gap-2"><button disabled={busy === item.application_id} onClick={() => void decide(item.application_id, "approved")} className="rounded bg-emerald-700 px-3 py-2 text-sm text-white disabled:opacity-50">Согласен</button><button disabled={busy === item.application_id || !notes[item.application_id]?.trim()} onClick={() => void decide(item.application_id, "rejected")} className="rounded border border-red-300 px-3 py-2 text-sm text-red-700 disabled:opacity-50">Не согласен</button></div>
    </section>)}
  </main>;
}
