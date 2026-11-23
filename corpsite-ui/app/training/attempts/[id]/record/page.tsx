"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { trainingApi } from "@/lib/trainingApi";

export default function TrainingHireRecordPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [record, setRecord] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => setRecord(await trainingApi.hireRecord(id)), [id]);
  useEffect(() => { void load().catch((cause) => setError(String(cause?.message ?? cause))); }, [load]);
  async function consent() {
    setBusy(true); setError("");
    try { setRecord(await trainingApi.hireConsent(id)); }
    catch (cause: any) { setError(String(cause?.message ?? cause)); }
    finally { setBusy(false); }
  }
  if (!record) return <main className="mx-auto max-w-4xl p-6">{error || "Загрузка учебной записи…"}</main>;
  const visa = record.visa;
  const approved = visa?.decision === "approved" && visa?.is_current;
  return <main className="mx-auto max-w-4xl space-y-5 p-4 md:p-6">
    <Link href={`/training/attempts/${id}`} className="text-sm text-blue-700 underline">← К карточке занятия</Link>
    <header className="rounded-xl border bg-white p-5 dark:bg-zinc-900">
      <p className="text-sm text-zinc-500">Индивидуальная учебная запись</p>
      <h1 className="text-2xl font-semibold">Заявление о приёме № {record.application_number}</h1>
      <p className="mt-2">{record.full_name}</p>
      <p className="text-sm text-zinc-600">{record.org_unit} · {record.position} · ставка {record.rate} · начало {record.start_date}</p>
      <p className="mt-2 text-sm">Внутренний ID черновика приказа {record.order_number} · задача № {record.task_number}</p>
    </header>
    <section className="rounded-xl border bg-white p-5 dark:bg-zinc-900">
      <h2 className="text-lg font-semibold">Резолюция с решением</h2>
      <p className="mt-1 text-sm">Заявление № {record.application_number}</p>
      <p className="mt-2 text-sm">Проверьте ФИО кандидата, отделение, должность, ставку и дату начала.</p>
      {approved ? <div className="mt-3 rounded-lg border border-green-300 bg-green-50 p-3 text-green-900">
        <strong>Согласен · положительная виза сохранена</strong>
        <p className="text-sm">Согласовал: {visa.decided_by_name} · {new Date(visa.decided_at).toLocaleString("ru-RU", { timeZone: "Asia/Qyzylorda" })}</p>
      </div> : <button type="button" onClick={() => void consent()} disabled={busy}
        className="mt-4 rounded-lg bg-blue-700 px-4 py-2 text-white disabled:opacity-50">{busy ? "Сохранение…" : "Согласен"}</button>}
      {approved && record.attempt_status === "technical_pause" && <button type="button" onClick={() => void consent()} disabled={busy}
        className="mt-3 rounded-lg border px-3 py-2 text-sm disabled:opacity-50">Повторить проверку визы</button>}
    </section>
    <section className="rounded-xl border bg-white p-5 dark:bg-zinc-900">
      <h2 className="text-lg font-semibold">Карточка с итоговым статусом</h2>
      <p className="mt-2">Заявление № {record.application_number}: {approved ? "Согласовано" : "Ожидает согласования"}</p>
      <p className="text-sm">Задача: {record.task_status === "DONE" ? "Отработано" : "В работе"}</p>
      <p className="text-sm">Виза в связанном приказе: {record.order_visa_valid ? "Согласовано" : "Ожидается"}</p>
      <p className="text-sm">Приказ: {record.order_status === "DRAFT" ? "Черновик" : record.order_status}</p>
    </section>
    {record.technical_message && <p role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-amber-900">{record.technical_message}</p>}
    {error && <p role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}
  </main>;
}
