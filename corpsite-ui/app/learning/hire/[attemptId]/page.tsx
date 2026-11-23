"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetchJson } from "@/lib/api";

type Fixture = { iin: string; full_name: string; birth_date: string; application_received_at: string; planned_start_date: string; org_unit_id: number; position_id: number; employment_rate: string };
type Application = { application_id: number; status: string; full_name: string; iin: string; org_unit_name?: string; position_name?: string; intended_employment_rate: string; planned_start_date: string };
type State = { attempt_id: string; attempt_no: number; attempt_status: string; fixture: Fixture; application: Application | null; guide_url?: string };
type PrintPreview = { ru?: string; kk?: string; preview_type?: string; application_id?: number; status?: string; full_name?: string; org_unit_name?: string; position_name?: string; employment_rate?: string; planned_start_date?: string };

export default function HireLessonForm() {
  const attemptId = String(useParams().attemptId);
  const [embedded, setEmbedded] = useState(false);
  useEffect(() => { setEmbedded(new URLSearchParams(window.location.search).get("embedded") === "1"); }, []);
  const [data, setData] = useState<State | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [preview, setPreview] = useState(false);
  const [printData, setPrintData] = useState<PrintPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    try { setData(await apiFetchJson<State>(`/learning/attempts/${attemptId}/hire-application`)); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Форма недоступна"); }
  }, [attemptId]);
  useEffect(() => { void load(); }, [load]);

  async function save() {
    if (!confirmed || !preview) return;
    setBusy(true); setMessage("");
    try {
      const state = await apiFetchJson<State>(`/learning/attempts/${attemptId}/hire-application`, { method: "POST", body: { confirmed: true } });
      setData(state); setMessage("Учебное заявление сохранено. Вернитесь к занятию и сдайте работу.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Не удалось сохранить заявление"); }
    finally { setBusy(false); }
  }
  async function openPrint() {
    try { setPrintData(await apiFetchJson<PrintPreview>(`/learning/attempts/${attemptId}/hire-application/preview`)); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Не удалось открыть подтверждение"); }
  }
  if (!data) return <main className="mx-auto max-w-3xl p-8">{message || "Открываем кадровую форму…"}</main>;
  const f = data.fixture;
  const fields = [
    ["ИИН вымышленного кандидата", f.iin], ["ФИО", f.full_name], ["Дата рождения", f.birth_date],
    ["Дата получения заявления", f.application_received_at], ["Дата начала работы", f.planned_start_date],
    ["Отделение", data.application?.org_unit_name ?? String(f.org_unit_id)],
    ["Должность", data.application?.position_name ?? String(f.position_id)], ["Ставка", f.employment_rate],
    ["Способ оформления", "Электронный"],
  ];
  return <main className="min-h-screen bg-zinc-50 px-4 py-8 text-zinc-900"><div className="mx-auto max-w-3xl space-y-5">
    <header><a href={embedded ? `/learning/hire-path?variant=single&step=1&application=${attemptId}` : "/training"} target={embedded ? "_top" : undefined} className="text-sm text-blue-700 underline">← Вернуться к занятию</a><h1 className="mt-3 text-2xl font-semibold">Электронное заявление о приёме на работу</h1><p className="text-sm text-zinc-600">Учебная попытка № {data.attempt_no} · только вымышленные данные</p></header>
    {message && <p role="status" className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm">{message}</p>}
    {data.application && <section className="rounded-xl border border-green-300 bg-green-50 p-4"><h2 className="font-semibold">Заявление № {data.application.application_id} сохранено</h2><p>Статус: {data.application.status}</p><p className="text-sm">При повторном открытии этой попытки возвращается то же заявление.</p></section>}
    <section className="rounded-xl border border-zinc-200 bg-white p-5"><h2 className="mb-4 text-lg font-semibold">Кадровая форма</h2><div className="grid gap-4 sm:grid-cols-2">{fields.map(([label, value]) => <label key={label} className="block text-sm font-medium">{label}<input readOnly value={value} className="mt-1 w-full rounded-lg border border-zinc-300 bg-zinc-50 p-2" /></label>)}</div></section>
    <section className="rounded-xl border border-zinc-200 bg-white p-5"><h2 className="font-semibold">Инструкция и подтверждение</h2>{!embedded && data.guide_url && <a href={data.guide_url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block text-sm text-blue-700 underline">Открыть инструкцию в Google Документах</a>}
      {!data.application && <><label className="mt-4 block text-sm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} /> Данные вымышленные и соответствуют учебному заданию</label><button className="mt-4 rounded-lg border border-zinc-300 px-4 py-2 text-sm" onClick={() => setPreview(true)}>Предпросмотр подтверждения</button>{preview && <div className="mt-4 rounded-lg bg-blue-50 p-4 text-sm"><p className="font-semibold">Подтверждение сохранения</p><p>Кандидат: {f.full_name}, ИИН {f.iin}. Отделение #{f.org_unit_id}, должность #{f.position_id}, ставка {f.employment_rate}, начало {f.planned_start_date}. Способ: электронный.</p></div>}<button className="mt-4 block rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50" disabled={!confirmed || !preview || busy} onClick={save}>Сохранить заявление</button></>}
      {data.application && <><button className="mt-4 rounded-lg border border-zinc-300 px-4 py-2 text-sm" onClick={openPrint}>Предпросмотр сохранённого заявления</button>{printData && <div className="mt-3 space-y-3 rounded bg-zinc-50 p-4 text-sm">{printData.ru ? <><h3 className="font-semibold">Русский</h3><p className="whitespace-pre-wrap">{printData.ru}</p>{printData.kk && <><h3 className="font-semibold">Қазақша</h3><p className="whitespace-pre-wrap">{printData.kk}</p></>}</> : <><h3 className="font-semibold">Подтверждение сохранённого заявления № {printData.application_id}</h3><p>{printData.full_name} · {printData.org_unit_name} · {printData.position_name}</p><p>Ставка {printData.employment_rate} · начало {printData.planned_start_date} · статус {printData.status} · электронный способ оформления</p></>}</div>}</>}
    </section><p className="text-sm text-zinc-600">После сохранения вернитесь в занятие, приложите два снимка и отправьте работу.</p>
  </div></main>;
}
