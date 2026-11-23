"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiAuthMe } from "@/lib/api";
import { trainingApi, trainingEvidenceUrl, type TrainingDetail } from "@/lib/trainingApi";
import { trainingLessonTitle } from "@/lib/trainingViewModel";

type ReviewRow = { attempt_id: number; full_name: string; course_title: string; lesson_title: string; lesson_number: number; attempt_number: number; lesson_code: string; course_version: number; fixture: Record<string, unknown> };
function errorText(cause: unknown) { return cause instanceof Error ? cause.message : "Не удалось выполнить действие."; }

export default function TrainingReviewPage() {
  const [gate, setGate] = useState<"loading" | "allowed" | "denied" | "error">("loading");
  const [queueState, setQueueState] = useState<"loading" | "success" | "error">("loading");
  const [rows, setRows] = useState<ReviewRow[]>([]);
  const [detail, setDetail] = useState<TrainingDetail | null>(null);
  const [images, setImages] = useState<Record<number, string>>({});
  const [valid, setValid] = useState(false);
  const [substitution, setSubstitution] = useState(false);
  const [correction, setCorrection] = useState(false);
  const [explanation, setExplanation] = useState("");
  const [message, setMessage] = useState("");
  const load = useCallback(async () => {
    setGate("loading"); setQueueState("loading");
    try {
      const me = await apiAuthMe();
      if (!me.has_sysadmin_api) { setGate("denied"); return; }
      setGate("allowed");
      const result = await trainingApi.attempts({ result: "under_review", page_size: 100 });
      setRows(result.items.filter((row) => row.lesson_code === "skill_2" && [2, 3].includes(Number(row.course_version))) as ReviewRow[]);
      setQueueState("success");
    } catch { setGate((current) => current === "allowed" ? current : "error"); setQueueState("error"); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  async function open(id: number) {
    setMessage("");
    Object.values(images).forEach((url) => URL.revokeObjectURL(url));
    try {
      const data = await trainingApi.detail(id);
      const urls: Record<number, string> = {};
      for (const item of data.evidence) urls[item.evidence_id] = await trainingEvidenceUrl(item.evidence_id);
      setDetail(data); setImages(urls);
      setValid(false); setSubstitution(false); setCorrection(false); setExplanation("");
    } catch (cause: unknown) { setMessage(errorText(cause)); }
  }
  async function submit() {
    if (!detail) return;
    try {
      const result = await trainingApi.review(detail.attempt.attempt_id, {
        evidence_valid: valid, established_substitution: substitution,
        hint_or_action_correction: correction, explanation,
      });
      setMessage(`Проверка сохранена. Оценка: ${result.score}.`);
      setDetail(null); await load();
    } catch (cause: unknown) { setMessage(errorText(cause)); }
  }
  if (gate === "loading") return <main className="mx-auto max-w-5xl p-6">Загрузка проверки работ…</main>;
  if (gate === "denied") return <main className="mx-auto max-w-5xl p-6">Нет доступа к проверке работ.</main>;
  if (gate === "error") return <main className="mx-auto max-w-5xl p-6" role="alert">Не удалось загрузить данные. <button type="button" onClick={() => void load()} className="text-blue-700 underline">Повторить</button></main>;
  return <main className="mx-auto max-w-5xl space-y-4 p-4 md:p-6">
    <Link href="/training" className="text-sm text-blue-700 underline">← Обучение</Link>
    <h1 className="text-2xl font-semibold">Проверка работ</h1>
    {message && <p role="status" className="rounded-lg border p-3">{message}</p>}
    {queueState === "error" && <p role="alert">Не удалось загрузить данные. <button type="button" onClick={() => void load()} className="text-blue-700 underline">Повторить</button></p>}
    {queueState === "loading" && <p>Загрузка работ…</p>}
    {queueState === "success" && rows.length === 0 && <p>Ожидающих проверок нет.</p>}
    {rows.map((row) => <button key={row.attempt_id} type="button" onClick={() => void open(row.attempt_id)}
      className="block w-full rounded-lg border p-3 text-left text-blue-700">{row.full_name}<br />Курс: {row.course_title}<br />{trainingLessonTitle(row.lesson_number, row.lesson_title)} · заявление № {String(row.fixture?.application_number ?? "—")} · попытка {row.attempt_number}</button>)}
    {detail && <section className="space-y-4 rounded-xl border p-5">
      <p className="text-sm">Курс: {detail.attempt.course_title}</p>
      <h2 className="font-semibold">{trainingLessonTitle(detail.attempt.lesson_number, detail.attempt.lesson_title)}</h2>
      <p className="text-sm">Попытка {detail.attempt.attempt_number} · заявление № {String(detail.attempt.fixture.application_number)}</p>
      <p className="text-sm">{detail.attempt.course_version === 3
        ? "Сверьте на одном снимке заявление, условия, согласие, согласовавшего и время, завершённую задачу, положительную визу и черновой статус приказа."
        : "Проверьте номер заявления и сохранённое согласие на первом снимке, тот же номер и итоговый статус на втором. Сравните с реквизитами попытки."}</p>
      <div className={detail.attempt.course_version === 3 ? "grid gap-4" : "grid gap-4 md:grid-cols-2"}>{detail.evidence.map((item) => <figure key={item.evidence_id} className="min-w-0 rounded-lg border p-2">
        <figcaption className="mb-2 text-sm font-medium">{item.step_key === "result" ? "Результат согласования заявления" : item.step_key === "resolution" ? "Резолюция с решением" : "Карточка с итоговым статусом"}</figcaption>
        {images[item.evidence_id] && <a href={images[item.evidence_id]} target="_blank" rel="noreferrer"><img src={images[item.evidence_id]} alt={item.step_key} className="max-h-80 w-full object-contain" /></a>}
      </figure>)}</div>
      <label className="block"><input type="checkbox" checked={valid} onChange={(event) => setValid(event.target.checked)} /> {detail.attempt.course_version === 3 ? "Снимок соответствует попытке и содержит требуемые сведения" : "Оба снимка соответствуют попытке и содержат требуемые сведения"}</label>
      <label className="block"><input type="checkbox" checked={substitution} onChange={(event) => setSubstitution(event.target.checked)} /> Установлена подмена подтверждения</label>
      <label className="block"><input type="checkbox" checked={correction} onChange={(event) => setCorrection(event.target.checked)} /> Потребовались подсказки или исправления действий</label>
      <label className="block text-sm">Пояснение<textarea value={explanation} onChange={(event) => setExplanation(event.target.value)} className="mt-1 block w-full rounded border p-2" rows={3} /></label>
      <button type="button" disabled={explanation.trim().length < 10} onClick={() => void submit()} className="rounded-lg bg-blue-700 px-4 py-2 text-white disabled:opacity-50">Сохранить оценку</button>
    </section>}
  </main>;
}
