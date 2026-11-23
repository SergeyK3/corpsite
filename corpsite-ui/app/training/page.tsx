"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { trainingApi, type TrainingAssignment } from "@/lib/trainingApi";
import { apiFetchJson } from "@/lib/api";
import { useCurrentUser } from "@/lib/currentUser";
import { trainingAction, trainingDate, trainingLessonTitle, trainingStatus } from "@/lib/trainingViewModel";
import TrainingNavigation from "./_components/TrainingNavigation";

function errorText(cause: unknown) { return cause instanceof Error ? cause.message : "Не удалось выполнить действие."; }

export default function TrainingPage() {
  const router = useRouter();
  const me = useCurrentUser();
  const [hireRoute, setHireRoute] = useState<{ passed: number; total: number } | null>(null);
  const [items, setItems] = useState<TrainingAssignment[]>([]);
  const [loadState, setLoadState] = useState<"loading" | "success" | "error">("loading");
  const [busy, setBusy] = useState<number | null>(null);
  const [notice, setNotice] = useState("");
  const [previews, setPreviews] = useState<Record<number, Awaited<ReturnType<typeof trainingApi.preview>>>>({});
  const loadAssignments = useCallback(async () => {
    setLoadState("loading");
    try { const data = await trainingApi.assignments(); setItems(data.items); setLoadState("success"); }
    catch { setLoadState("error"); }
  }, []);
  useEffect(() => { void loadAssignments(); }, [loadAssignments]);
  useEffect(() => {
    if (me?.role_code !== "LEARN_HR") { setHireRoute(null); return; }
    let active = true;
    void apiFetchJson<{ lessons: Record<string, { status: string }> }>("/learning/my-courses")
      .then(data => {
        const codes = ["lesson_5b2e5028ea63", "hire_path_02_personal_card", "hire_path_03_order_draft", "hire_path_04_sign_register", "hire_path_05_notify_ack"];
        if (active && codes.every(code => data.lessons[code])) setHireRoute({ passed: codes.filter(code => data.lessons[code].status === "passed").length, total: codes.length });
      }).catch(() => { if (active) setHireRoute(null); });
    return () => { active = false; };
  }, [me?.role_code]);
  async function preview(id: number) {
    setBusy(id); setNotice("");
    try { const data = await trainingApi.preview(id); setPreviews((old) => ({ ...old, [id]: data })); }
    catch (cause) { setNotice(errorText(cause)); } finally { setBusy(null); }
  }
  async function start(id: number) {
    setBusy(id); setNotice("");
    try { const attempt = await trainingApi.start(id, crypto.randomUUID()); router.push(`/training/attempts/${attempt.attempt_id}`); }
    catch (cause) { setNotice(errorText(cause)); } finally { setBusy(null); }
  }
  return <main className="mx-auto max-w-5xl space-y-5 p-4 md:p-6">
    <TrainingNavigation active="lessons" />
    <header><h1 className="text-2xl font-semibold">Мои занятия</h1><p className="text-sm text-zinc-500">Назначенные занятия и текущий результат</p></header>
    {notice && <p role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-red-800">{notice}</p>}
    {loadState === "error" && <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-red-800">Не удалось загрузить данные. <button type="button" onClick={() => void loadAssignments()} className="font-medium underline">Повторить</button></div>}
    {loadState === "loading" && items.length === 0 && <p>Загрузка занятий…</p>}
    {loadState === "success" && items.length === 0 && <p>Назначенных занятий пока нет.</p>}
    {hireRoute && <article className="rounded-xl border border-blue-200 bg-blue-50 p-5 shadow-sm dark:border-blue-900 dark:bg-blue-950">
      <p className="text-sm font-medium text-blue-800 dark:text-blue-200">Один маршрут · пять этапов</p>
      <h2 className="mt-1 text-xl font-semibold">Приём нового сотрудника на работу</h2>
      <p className="mt-2 text-sm">Пять этапов на одной странице. Используются те же заявления, попытки и оценки: зачтено {hireRoute.passed} из {hireRoute.total}.</p>
      <div className="mt-4 flex flex-wrap gap-3"><Link href="/learning/hire-path?variant=single&step=1" className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white">Открыть маршрут</Link>
</div>
    </article>}
    <div className="grid gap-4 md:grid-cols-2">{items.map((item) => {
      const id = item.assignment_id;
      const data = previews[id];
      const hasAttempt = item.latest_attempt_id != null;
      return <article id={`assignment-${id}`} key={id} className="min-w-0 scroll-mt-4 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <p className="text-sm text-zinc-500">Курс: {item.course_title}</p>
        <h2 className="mt-1 text-lg font-semibold">{trainingLessonTitle(item.lesson_number, item.title)}</h2>
        <p className="mt-1 text-xs text-zinc-500">{item.duration_minutes} минут · версия материала {item.course_version}</p>
        <div className="mt-4 rounded-lg bg-zinc-50 p-3 text-sm dark:bg-zinc-800">
          <strong>{trainingStatus(item.latest_status, item.latest_outcome)}</strong>
          <span className="ml-2">Оценка: {item.latest_score ?? "—"} · Проверено: {item.latest_status === "completed" ? trainingDate(item.latest_checked_at) : "—"}</span>
          {hasAttempt && <p className="mt-1 text-zinc-600 dark:text-zinc-300">Попытка {item.latest_attempt_number}{item.latest_application_number ? ` · заявление №${item.latest_application_number}` : ""}</p>}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {hasAttempt ? <Link href={`/training/attempts/${item.latest_attempt_id}`} className="rounded-lg bg-blue-700 px-3 py-2 text-sm text-white">{trainingAction(item.latest_status)}</Link>
            : <button type="button" disabled={busy === id} onClick={() => void preview(id)} className="rounded-lg bg-blue-700 px-3 py-2 text-sm text-white disabled:opacity-50">Подготовить и начать</button>}
          {hasAttempt && item.latest_status === "completed" && <button type="button" disabled={busy === id} onClick={() => void preview(id)} className="rounded-lg border px-3 py-2 text-sm text-blue-700 disabled:opacity-50">Пересдать</button>}
        </div>
        {data && <div className="mt-3 rounded-lg border p-3 text-sm">
          {data.ready ? <><p>Исходные данные проверены. {String(data.fixture?.full_name ?? "")}</p><button type="button" disabled={busy === id} onClick={() => void start(id)} className="mt-2 rounded-lg bg-blue-700 px-3 py-2 text-white disabled:opacity-50">Начать новую попытку</button></>
            : <p>Подготовка пока недоступна: {data.reason ?? "Проверьте исходные данные."}</p>}
        </div>}
      </article>;
    })}</div>
  </main>;
}
