"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetchJson } from "@/lib/api";

type Exercise = {
  attempt_id: string;
  application_ref: string;
  candidate_name: string;
  position_title: string;
  employment_fraction: string;
  start_date: string;
  status: "awaiting_consent" | "approved";
  approved_at: string | null;
  attempt_status: string;
};

export default function ApprovalExercisePage() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    apiFetchJson<Exercise>(`/learning/exercises/${attemptId}`).then(setExercise)
      .catch((error) => setMessage(error instanceof Error ? error.message : "Не удалось открыть учебное заявление"));
  }, [attemptId]);
  async function consent() {
    if (!exercise) return;
    setBusy(true); setMessage("");
    try {
      const updated = await apiFetchJson<Exercise>(`/learning/exercises/${exercise.attempt_id}/consent`, { method: "POST" });
      setExercise(updated);
      setMessage(`Согласие по заявлению ${updated.application_ref} сохранено.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Не удалось сохранить согласие"); }
    finally { setBusy(false); }
  }
  return <main className="min-h-screen bg-white px-4 py-8 text-zinc-900 sm:px-6"><div className="mx-auto max-w-4xl space-y-6">
    <div><p className="text-sm font-medium text-blue-700">Учебная среда Corpsite</p><h1 className="mt-1 text-3xl font-semibold">Заявление {exercise?.application_ref ?? "…"}</h1><p className="mt-2 text-sm text-zinc-600">Данные вымышлены. Запись создана только для этого занятия и этой попытки.</p></div>
    {message && <p role="status" className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm">{message}</p>}
    {exercise && <>
      <section className="rounded-xl border border-zinc-200 p-5"><h2 className="text-xl font-semibold">Условия заявления</h2><dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2"><div><dt className="text-zinc-500">Номер</dt><dd className="font-medium">{exercise.application_ref}</dd></div><div><dt className="text-zinc-500">Кандидат</dt><dd className="font-medium">{exercise.candidate_name}</dd></div><div><dt className="text-zinc-500">Должность</dt><dd className="font-medium">{exercise.position_title}</dd></div><div><dt className="text-zinc-500">Ставка</dt><dd className="font-medium">{exercise.employment_fraction}</dd></div><div><dt className="text-zinc-500">Дата начала работы</dt><dd className="font-medium">{exercise.start_date}</dd></div></dl></section>
      <section id="resolution-evidence" className="rounded-xl border border-zinc-200 p-5"><h2 className="text-xl font-semibold">Резолюция с решением</h2><p className="mt-3 text-sm">Заявление {exercise.application_ref} · {exercise.candidate_name}</p><p className="mt-2 text-sm">Решение: <strong>{exercise.status === "approved" ? "Согласен" : "Не принято"}</strong></p>{exercise.status === "approved" ? <p className="mt-2 text-sm text-green-800">Согласие сохранено{exercise.approved_at ? ` · ${new Date(exercise.approved_at).toLocaleString("ru-RU")}` : ""}</p> : <button className="mt-4 rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50" disabled={busy || exercise.attempt_status !== "draft"} onClick={consent}>Согласен</button>}</section>
      <section id="status-evidence" className="rounded-xl border border-zinc-200 p-5"><h2 className="text-xl font-semibold">Карточка с итоговым статусом</h2><p className="mt-3 text-sm">Заявление {exercise.application_ref} · {exercise.candidate_name}</p><p className="mt-2 text-sm">Итоговый статус: <strong>{exercise.status === "approved" ? "Согласовано" : "Ожидает согласования"}</strong></p><p className="mt-2 text-sm text-zinc-600">Должность: {exercise.position_title} · ставка {exercise.employment_fraction} · начало {exercise.start_date}</p></section>
      <p className="text-sm text-zinc-600">Сделайте снимок резолюции и снимок карточки со статусом. Затем вернитесь к вкладке занятия и отправьте оба файла на проверку.</p>
    </>}
  </div></main>;
}
