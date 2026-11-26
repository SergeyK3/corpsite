"use client";

import * as React from "react";
import { apiFetchJson } from "@/lib/api";

type Mode = "paper" | "electronic";
type Unit = { unit_id: number; unit_name: string; mode: Mode; unfinished_count: number; retained_prior_mode_count: number };
type Audit = { audit_id: number; unit_name: string; application_id: number | null; old_mode: Mode; new_mode: Mode;
  changed_by_name: string; changed_at: string; reason: string };
const label = (mode: Mode) => mode === "electronic" ? "Электронное согласование" : "Бумажное согласование";

export default function HireApprovalRolloutTab() {
  const [items, setItems] = React.useState<Unit[]>([]);
  const [audit, setAudit] = React.useState<Audit[]>([]);
  const [reason, setReason] = React.useState("");
  const [selected, setSelected] = React.useState<number | null>(null);
  const [error, setError] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const refresh = React.useCallback(async () => {
    const data = await apiFetchJson<{items: Unit[]; audit: Audit[]}>("/admin/hire-approval-rollout");
    setItems(data.items); setAudit(data.audit);
  }, []);
  React.useEffect(() => { void refresh().catch(e => setError(String(e))); }, [refresh]);

  async function change(unit: Unit, mode: Mode) {
    if (unit.mode === mode) return;
    if (!reason.trim()) { setError("Укажите причину изменения режима."); return; }
    setBusy(true); setError("");
    try {
      await apiFetchJson(`/admin/hire-approval-rollout/${unit.unit_id}`, {
        method: "PUT", body: {mode, reason: reason.trim()},
      });
      setReason(""); setSelected(null); await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return <section className="space-y-4 text-sm">
    <h2 className="text-lg font-semibold">Внедрение электронного согласования</h2>
    <p>Настройка действует только для приёма на работу. Новые заявления сохраняют режим отделения на момент создания. Заявления без настройки используют бумажное согласование.</p>
    {error && <p role="alert" className="rounded bg-red-50 p-3 text-red-800">{error}</p>}
    <div className="overflow-x-auto"><table className="w-full border-collapse text-left">
      <thead><tr className="border-b"><th className="p-2">Отделение</th><th className="p-2">Режим приёма</th><th className="p-2">Незавершённые заявления</th><th className="p-2">С прежним порядком</th><th className="p-2">Изменение</th></tr></thead>
      <tbody>{items.map(unit => <tr key={unit.unit_id} className="border-b align-top">
        <td className="p-2">{unit.unit_name}</td><td className="p-2">{label(unit.mode)}</td>
        <td className="p-2">{unit.unfinished_count}</td><td className="p-2">{unit.retained_prior_mode_count}</td>
        <td className="p-2"><button type="button" className="underline" onClick={() => setSelected(unit.unit_id)}>Изменить</button>
          {selected === unit.unit_id && <div className="mt-2 space-y-2 rounded border p-2">
            <p>После смены режима {unit.unfinished_count} незавершённых заявлений продолжат действовать по сохранённому порядку.</p>
            <label className="block">Причина<input className="mt-1 w-full rounded border p-1" value={reason} onChange={e => setReason(e.target.value)} /></label>
            <button disabled={busy} className="rounded bg-blue-700 px-2 py-1 text-white disabled:opacity-50"
              onClick={() => void change(unit, unit.mode === "paper" ? "electronic" : "paper")}>Включить {unit.mode === "paper" ? "электронное" : "бумажное"} согласование</button>
          </div>}</td>
      </tr>)}</tbody>
    </table></div>
    <details><summary className="cursor-pointer font-medium">История изменений режима</summary>
      <ul className="mt-2 space-y-2">{audit.map(row => <li key={row.audit_id} className="border-b pb-2">
        {row.unit_name}: {label(row.old_mode)} → {label(row.new_mode)} · {row.changed_by_name} · {new Date(row.changed_at).toLocaleString("ru-RU", {timeZone: "Asia/Qyzylorda"})} · {row.reason}
        {row.application_id && ` · заявление №${row.application_id}`}
      </li>)}</ul>
    </details>
  </section>;
}
