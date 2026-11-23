"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { trainingApi, type TrainingNotice, type TrainingSummary, type TrainingSummaryAttempt, type TrainingSummaryItem } from "@/lib/trainingApi";
import { groupTrainingResults, trainingDate, trainingLessonTitle, trainingStatus } from "@/lib/trainingViewModel";
import TrainingNavigation from "../_components/TrainingNavigation";
import TrainingReviewReceipt from "../_components/TrainingReviewReceipt";

function AttemptLine({ attempt }: { attempt: TrainingSummaryAttempt }) {
  return <li className="break-words">Попытка {attempt.attempt_number}{attempt.application_number ? ` · заявление №${attempt.application_number}` : ""}
    {" · "}{trainingStatus(attempt.status, attempt.outcome)} · оценка {attempt.score ?? "—"} ·{" "}
    <Link href={`/training/attempts/${attempt.attempt_id}`} className="text-blue-700 underline">Посмотреть результат</Link>
  </li>;
}

export default function TrainingResultsPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<TrainingSummary | null>(null);
  const [loadState, setLoadState] = useState<"loading" | "success" | "error">("loading");
  const [error, setError] = useState("");
  const [notices, setNotices] = useState<TrainingNotice[]>([]);
  const [noticesError, setNoticesError] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);
  const [previews, setPreviews] = useState<Record<number, Awaited<ReturnType<typeof trainingApi.preview>>>>({});
  const loadSummary = useCallback(async () => {
    setLoadState("loading"); setError("");
    try { setSummary(await trainingApi.mySummary()); setLoadState("success"); }
    catch { setLoadState("error"); }
  }, []);
  const loadNotices = useCallback(async () => {
    setNoticesError(false);
    try { setNotices((await trainingApi.myNotifications()).items); }
    catch { setNoticesError(true); }
  }, []);
  useEffect(() => { void loadSummary(); void loadNotices(); }, [loadSummary, loadNotices]);
  async function preview(id: number) {
    setBusy(id); setError("");
    try { const data = await trainingApi.preview(id); setPreviews((old) => ({ ...old, [id]: data })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); } finally { setBusy(null); }
  }
  async function start(id: number) {
    setBusy(id); setError("");
    try { const result = await trainingApi.start(id, crypto.randomUUID()); router.push(`/training/attempts/${result.attempt_id}`); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); } finally { setBusy(null); }
  }
  function currentCard(item: TrainingSummaryItem, history: TrainingSummaryItem[]) {
    const latest = item.attempts[0];
    const previous = item.attempts.slice(1);
    const data = previews[item.assignment_id];
    return <section key={`${item.course_code}:${item.lesson_code}`} className="min-w-0 rounded-xl border bg-white p-5 dark:bg-zinc-900">
      <p className="text-sm text-zinc-500">Курс: {item.course_title}</p>
      <h2 className="mt-1 text-lg font-semibold">{trainingLessonTitle(item.lesson_number, item.lesson_title)}</h2>
      <p className="text-xs text-zinc-500">Актуальная версия материала {item.course_version}</p>
      <div className="mt-3 rounded-lg bg-zinc-50 p-3 text-sm dark:bg-zinc-800">
        <strong>{trainingStatus(latest?.status, latest?.outcome)}</strong>
        <span className="ml-2">Оценка: {latest?.score ?? "—"} · Проверено: {latest?.status === "completed" ? trainingDate(latest.last_checked_at) : "—"}</span>
        {latest && <p className="mt-1">Попытка {latest.attempt_number}{latest.application_number ? ` · заявление №${latest.application_number}` : ""}</p>}
      </div>
      {latest?.status === "under_review" ? <p className="mt-3 text-sm">Результат отправлен эксперту по внутреннему обучению. Оценка появится после проверки.</p>
        : latest?.status === "completed" && latest.score != null && item.lesson_code === "skill_2"
          ? <div className="mt-3"><TrainingReviewReceipt title="Результат проверки" data={{
              courseTitle: item.course_title, lessonNumber: item.lesson_number, lessonTitle: item.lesson_title,
              attemptNumber: latest.attempt_number, applicationNumber: latest.application_number,
              score: latest.score, reviewedAt: latest.reviewed_at ?? latest.last_checked_at ?? "",
              reviewerName: latest.reviewer_name, explanation: latest.explanation ?? "Пояснение не указано",
            }} /></div>
          : latest?.explanation && <p className="mt-3 text-sm">Пояснение эксперта: {latest.explanation}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {latest && <Link href={`/training/attempts/${latest.attempt_id}`} className="rounded-lg bg-blue-700 px-3 py-2 text-sm text-white">Посмотреть результат</Link>}
        {latest?.status !== "under_review" && <button type="button" disabled={busy === item.assignment_id} onClick={() => void preview(item.assignment_id)}
          className="rounded-lg border px-3 py-2 text-sm text-blue-700 disabled:opacity-50">{latest ? "Пересдать" : "Подготовить и начать"}</button>}
      </div>
      {data && <div className="mt-3 rounded-lg border p-3 text-sm">{data.ready
        ? <><p>Исходные данные проверены.</p><button type="button" disabled={busy === item.assignment_id} onClick={() => void start(item.assignment_id)}
          className="mt-2 rounded-lg bg-blue-700 px-3 py-2 text-white disabled:opacity-50">Начать новую попытку</button></>
        : <p>Подготовка пока недоступна: {data.reason ?? "Проверьте исходные данные."}</p>}</div>}
      {(previous.length > 0 || history.some((old) => old.attempts.length > 0)) && <details className="mt-4 border-t pt-3 text-sm">
        <summary className="cursor-pointer font-medium text-blue-700">История</summary>
        {previous.length > 0 && <><p className="mt-3 font-medium">Версия {item.course_version}</p><ul className="mt-1 space-y-2"><>{previous.map((attempt) => <AttemptLine key={attempt.attempt_id} attempt={attempt} />)}</></ul></>}
        {history.map((old) => <div key={old.assignment_id} className="mt-3"><p className="font-medium">Версия {old.course_version} · {old.course_title} · {old.lesson_title}</p>
          <ul className="mt-1 space-y-2">{old.attempts.map((attempt) => <AttemptLine key={attempt.attempt_id} attempt={attempt} />)}</ul></div>)}
      </details>}
    </section>;
  }
  return <main className="mx-auto max-w-5xl space-y-5 p-4 md:p-6">
    <TrainingNavigation active="results" />
    <header><h1 className="text-2xl font-semibold">Мои результаты</h1><p className="text-sm text-zinc-500">{summary?.full_name ?? ""}</p></header>
    {error && <p role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-red-800">{error}</p>}
    {loadState === "error" && <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-red-800">Не удалось загрузить данные. <button type="button" onClick={() => void loadSummary()} className="font-medium underline">Повторить</button></div>}
    {loadState === "loading" && !summary && <p>Загрузка результатов…</p>}
    {loadState === "success" && summary?.items.length === 0 && <p>Результатов пока нет.</p>}
    {summary && <div className="space-y-4">{groupTrainingResults(summary.items).map(({ current, history }) => currentCard(current, history))}</div>}
    {notices.length > 0 && <section className="space-y-3"><h2 className="text-xl font-semibold">Извещения о проверке</h2>
      {notices.map((notice) => <TrainingReviewReceipt key={notice.notification_id} title="Работа проверена" data={{
        courseTitle: notice.course_title, lessonNumber: notice.lesson_number, lessonTitle: notice.lesson_title,
        attemptNumber: notice.attempt_number, applicationNumber: notice.application_number,
        score: notice.score, reviewedAt: notice.reviewed_at, reviewerName: notice.reviewer_name,
        explanation: notice.explanation, attemptId: notice.attempt_id,
      }} />)}
    </section>}
    {noticesError && <p role="alert" className="text-sm">Не удалось загрузить извещения. <button type="button" onClick={() => void loadNotices()} className="text-blue-700 underline">Повторить</button></p>}
  </main>;
}
