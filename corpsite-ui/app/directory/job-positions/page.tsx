"use client";

import * as React from "react";
import Link from "next/link";
import { apiFetchJson } from "@/lib/api";

type Job = { job_code: string; job_nameru: string; job_namekk: string; job_namekk_doc: string; legacy_position_ids: number[] };

export default function JobPositionsPage() {
  const [items, setItems] = React.useState<Job[]>([]);
  const [canEdit, setCanEdit] = React.useState(false);
  const [selected, setSelected] = React.useState<Job | null>(null);
  const [error, setError] = React.useState("");
  const [notice, setNotice] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const load = React.useCallback(async () => {
    const data = await apiFetchJson<{ items: Job[]; can_edit: boolean }>("/directory/job-positions");
    setItems(data.items); setCanEdit(data.can_edit);
  }, []);
  React.useEffect(() => { void load().catch(() => setError("Не удалось загрузить справочник. Проверьте применение локальной миграции.")); }, [load]);
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!selected || busy) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const { job_code, job_nameru, job_namekk, job_namekk_doc } = selected;
      await apiFetchJson(`/directory/job-positions/${encodeURIComponent(job_code)}`, {
        method: "PUT", body: { job_nameru, job_namekk, job_namekk_doc },
      });
      await load(); setSelected(null); setNotice("Сохранено. Новые значения доступны для автозаполнения приказов.");
    } catch { setError("Не удалось сохранить изменения."); }
    finally { setBusy(false); }
  }
  return <main className="mx-auto max-w-6xl space-y-5 p-6">
    <Link href="/directory/positions" className="text-blue-600">Должности и назначения</Link>
    <h1 className="text-2xl font-semibold">Справочник должностей RU / KK</h1>
    <p>Названия и документные формы для кадровых приказов. Код должности постоянный. Изменения справочника не переписывают сохранённые приказы.</p>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {selected && <form onSubmit={save} className="space-y-3 rounded border p-4">
      <p>Код: <strong>{selected.job_code}</strong></p>
      {([['job_nameru', 'Название RU'], ['job_namekk', 'Название KK'], ['job_namekk_doc', 'Должность в тексте приказа KK']] as const).map(([key, label]) =>
        <label key={key} className="block">{label}<input required maxLength={500} value={selected[key]} onChange={e => setSelected({ ...selected, [key]: e.target.value })} className="block w-full rounded border bg-transparent p-2" /></label>)}
      <button disabled={busy} className="rounded bg-blue-600 px-4 py-2 text-white">Сохранить</button>{" "}
      <button type="button" disabled={busy} onClick={() => setSelected(null)}>Отмена</button>
    </form>}
    <div className="overflow-auto"><table className="w-full text-left text-sm"><thead><tr>{["Код", "Название RU", "Название KK", "Форма KK для приказа", "Прежние ID", ""].map((label, i) => <th className="p-2" key={i}>{label}</th>)}</tr></thead>
      <tbody>{items.map(job => <tr key={job.job_code} className="border-t"><td className="p-2">{job.job_code}</td><td className="p-2">{job.job_nameru}</td><td className="p-2">{job.job_namekk}</td><td className="p-2">{job.job_namekk_doc}</td><td className="p-2">{job.legacy_position_ids.join(", ")}</td><td>{canEdit && <button onClick={() => { setSelected({ ...job }); setNotice(""); }}>Редактировать</button>}</td></tr>)}</tbody>
    </table></div>
  </main>;
}
