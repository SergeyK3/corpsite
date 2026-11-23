"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import { apiFetchJson, buildHeaders, buildUrl, readJsonSafe, toApiError } from "@/lib/api";
import { CatalogPanel, HIRE_ROUTE_LESSON_CODES, MyCoursesPanel, SummaryPanel, statusLabel } from "./LearningPanels";
import type { Catalog, Lesson, Progress, Summary } from "./LearningPanels";
import TrainingNavigation from "../training/_components/TrainingNavigation";

type Review = { id: string; participant_id: number; lesson_code: string; attempt_no: number; pre_score: number | null };
type Assignment = { application_ref: string; work_url: string | null; message: string | null };
type ApprovalExercise = { attempt_id: string; attempt_status: string; application_ref: string };
type ExistingShot = { id: string; src: string };
type HireState = { attempt_id: string; attempt_no: number; application: { application_id: number; status: string } | null };
type Tab = "catalog" | "courses" | "reviews" | "summary";
type Source = "catalog" | "courses";

const panel = "rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm";
const primary = "rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50";
const secondary = "rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-50";
const actionLabels: Record<string, string> = { opened: "Открытие заявления", approved: "Одобрение", rejected: "Возражение", visa_viewed: "Просмотр истории виз" };

function Instruction({ lesson }: { lesson: Lesson }) {
  return <div className="space-y-4">
    <div className="grid gap-3 text-sm sm:grid-cols-3"><p><span className="text-zinc-500">Функция</span><br />{lesson.function}</p><p><span className="text-zinc-500">Навык</span><br />{lesson.skill}</p><p><span className="text-zinc-500">Занятие</span><br />№ {lesson.number} в навыке · {lesson.minutes} минут</p></div>
    <div><h3 className="font-semibold">Инструкция</h3><p className="mt-1 text-sm leading-6">{lesson.instruction}</p></div>
    <div><h3 className="font-semibold">Какие снимки нужны</h3><ol className="mt-1 list-decimal space-y-1 pl-5 text-sm leading-6">{lesson.screenshots.map((item) => <li key={item}>{item}</li>)}</ol></div>
  </div>;
}

function Criteria({ lesson }: { lesson: Lesson }) {
  return <details className="rounded-lg border border-zinc-200 p-3"><summary className="cursor-pointer font-medium">Как оценивается</summary><ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6">{lesson.criteria.map((item) => <li key={item}>{item}</li>)}</ul><p className="mt-2 rounded-lg bg-blue-50 p-3 text-sm">Зачёт: от 3 из 5 баллов и выполнен обязательный критерий «{lesson.required}».</p></details>;
}

export default function LearningPage() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [selectedCourseCode, setSelectedCourseCode] = useState("all");
  const [tab, setTab] = useState<Tab>("summary");
  const [selected, setSelected] = useState<{ lesson: Lesson; source: Source } | null>(null);
  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [hireState, setHireState] = useState<HireState | null>(null);
  const [resumeAttemptId, setResumeAttemptId] = useState<string | null>(null);
  const [retaking, setRetaking] = useState(false);
  const [retryRecordId, setRetryRecordId] = useState<string | null>(null);
  const [detail, setDetail] = useState("");
  const [files, setFiles] = useState<Array<File | null>>([]);
  const [previews, setPreviews] = useState<Array<string | null>>([]);
  const [uploaded, setUploaded] = useState<Array<ExistingShot | null>>([]);
  const [viewerId, setViewerId] = useState<number | null>(null);
  const [viewerName, setViewerName] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [scores, setScores] = useState<Record<string, number>>({});
  const [required, setRequired] = useState<Record<string, boolean>>({});
  const [criteriaMarks, setCriteriaMarks] = useState<Record<string, boolean[]>>({});
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [evidence, setEvidence] = useState<Record<string, { ref: string; action: string; images: string[] }>>({});

  const refresh = useCallback(async () => {
    const [cat, mine, personal] = await Promise.all([apiFetchJson<Catalog>("/learning/catalog"), apiFetchJson<Progress>("/learning/my-courses"), apiFetchJson<Summary>("/learning/summary", { query: { course_code: selectedCourseCode } })]);
    setCatalog(cat); setProgress(mine); setSummary(personal);
    try { const me = await apiFetchJson<{ user_id: number; full_name?: string }>("/auth/me"); setViewerId(me.user_id); setViewerName(me.full_name?.trim() || "Обучаемый"); } catch { setViewerId(null); setViewerName(""); }
    try { setReviews((await apiFetchJson<{ items: Review[] }>("/learning/reviews")).items); } catch { setReviews([]); }
  }, [selectedCourseCode]);
  useEffect(() => { refresh().catch((e) => setMessage(e.message || "Не удалось открыть обучение")); }, [refresh]);
  useEffect(() => {
    const urls = files.map((file) => file ? URL.createObjectURL(file) : null);
    setPreviews(urls);
    return () => urls.forEach((url) => { if (url) URL.revokeObjectURL(url); });
  }, [files]);
  const currentStatus = selected ? progress?.lessons[selected.lesson.code]?.status : undefined;
  const cannotSubmit = currentStatus === "manual_review" || (currentStatus === "passed" && !retaking);
  const isHireLesson = (lesson: Lesson) => lesson.title === "Создать электронное заявление о приёме на работу" && lesson.target_role === "Кадровик";
  const refreshHireState = useCallback(async () => {
    if (!resumeAttemptId || !selected || !isHireLesson(selected.lesson)) return;
    try { setHireState(await apiFetchJson<HireState>(`/learning/attempts/${resumeAttemptId}/hire-application`)); }
    catch { /* The form may not yet be saved. */ }
  }, [resumeAttemptId, selected]);
  useEffect(() => {
    const onFocus = () => { void refreshHireState(); };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [refreshHireState]);
  async function openLesson(lesson: Lesson, source: Source, retake = false) {
    if (HIRE_ROUTE_LESSON_CODES.includes(lesson.code)) {
      window.location.assign(`/learning/hire-path?variant=single&step=${lesson.route_step || 1}`);
      return;
    }
    setSelected({ lesson, source }); setFiles([]); setUploaded([]); setAssignment(null); setHireState(null); setResumeAttemptId(null); setRetryRecordId(null); setRetaking(retake); setMessage("");
    if (source === "catalog") return;
    if (lesson.route_step && lesson.route_step >= 2 && lesson.route_step <= 5) {
      window.location.assign(`/learning/hire-path?step=${lesson.route_step}`);
      return;
    }
    try {
      if (isHireLesson(lesson)) {
        const next = await apiFetchJson<{ id: string; attempt_no: number }>(`/learning/lessons/${lesson.code}/hire-attempts`, { method: "POST" });
        setResumeAttemptId(next.id);
        setAssignment({ application_ref: `Попытка № ${next.attempt_no}`, work_url: `/learning/hire/${next.id}`, message: null });
        setHireState(await apiFetchJson<HireState>(`/learning/attempts/${next.id}/hire-application`));
        const previous = await apiFetchJson<{ screenshots: Array<{ id: string }> }>(`/learning/attempts/${next.id}`);
        const shots = await Promise.all(previous.screenshots.map(async (shot, index) => {
          const response = await fetch(buildUrl(`/learning/screenshots/${shot.id}`), { headers: buildHeaders() });
          if (!response.ok) return null;
          const blob = await response.blob();
          return { id: shot.id, src: URL.createObjectURL(blob), file: new File([blob], `Снимок ${index + 1}.png`, { type: blob.type }) };
        }));
        setUploaded(shots); setFiles(shots.map((shot) => shot?.file ?? null));
        await refresh();
        return;
      }
      if (lesson.code === "resolution_2") {
        const exercise = await apiFetchJson<ApprovalExercise>("/learning/exercises/approval/start", { method: "POST" });
        setAssignment({ application_ref: exercise.application_ref, work_url: `/learning/exercise/${exercise.attempt_id}`, message: null });
        setResumeAttemptId(exercise.attempt_id);
        if (exercise.attempt_status === "draft") {
          const previous = await apiFetchJson<{ screenshots: Array<{ id: string }> }>(`/learning/attempts/${exercise.attempt_id}`);
          const shots = await Promise.all(previous.screenshots.map(async (shot, index) => {
            const response = await fetch(buildUrl(`/learning/screenshots/${shot.id}`), { headers: buildHeaders() });
            if (!response.ok) return null;
            const blob = await response.blob();
            return { id: shot.id, src: URL.createObjectURL(blob), file: new File([blob], `Снимок ${index + 1}.png`, { type: blob.type }) };
          }));
          setUploaded(shots);
          setFiles(shots.map((shot) => shot?.file ?? null));
        }
        await refresh();
        return;
      }
      const assigned = await apiFetchJson<Assignment>(`/learning/assignments/${lesson.code}`);
      setAssignment(assigned);
      const state = progress?.lessons[lesson.code];
      if (state?.attempt_id && (["draft", "failed"].includes(state.status) || (state.status === "passed" && retake))) {
        const previous = await apiFetchJson<{ id: string; record_id: string; screenshots: Array<{ id: string }> }>(`/learning/attempts/${state.attempt_id}`);
        if (state.status === "failed" || (state.status === "passed" && retake)) {
          setRetryRecordId(previous.record_id);
          const next = await apiFetchJson<{ id: string }>("/learning/attempts", { method: "POST", body: { lesson_code: lesson.code, record_id: previous.record_id } });
          setResumeAttemptId(next.id);
          await refresh();
        }
        if (state.status === "draft") {
          setResumeAttemptId(previous.id);
          const shots = await Promise.all(previous.screenshots.map(async (shot, index) => {
            const response = await fetch(buildUrl(`/learning/screenshots/${shot.id}`), { headers: buildHeaders() });
            if (!response.ok) return null;
            const blob = await response.blob();
            return { id: shot.id, src: URL.createObjectURL(blob), file: new File([blob], `Снимок ${index + 1}.png`, { type: blob.type }) };
          }));
          setUploaded(shots);
          setFiles(shots.map((shot) => shot?.file ?? null));
        }
      }
    } catch (e) { setMessage(e instanceof Error ? e.message : "Не удалось открыть задание"); }
  }

  async function submitLesson() {
    if (!selected || selected.source !== "courses") return;
    const lesson = selected.lesson;
    if (!assignment || lesson.screenshots.some((_, index) => !files[index])) { setMessage(`Приложите ${lesson.screenshots.length} снимок(а) из карточки`); return; }
    setBusy(true); setMessage("");
    try {
      let attemptId = resumeAttemptId;
      if (!attemptId) {
        if (lesson.code === "resolution_2") throw new Error("Учебное заявление ещё не подготовлено. Откройте занятие повторно.");
        const recordId = retryRecordId || (await apiFetchJson<{ id: string }>("/learning/records", { method: "POST", body: { application_ref: assignment.application_ref, action: lesson.expected_action, detail } })).id;
        attemptId = (await apiFetchJson<{ id: string }>("/learning/attempts", { method: "POST", body: { lesson_code: lesson.code, record_id: recordId } })).id;
      }
      for (const old of uploaded) if (old) await apiFetchJson(`/learning/screenshots/${old.id}`, { method: "DELETE" });
      for (const [index, file] of files.entries()) {
        if (!file) continue;
        const form = new FormData(); form.set("file", file); form.set("slot", String(index));
        const response = await fetch(buildUrl(`/learning/attempts/${attemptId}/screenshots`), { method: "POST", headers: buildHeaders(), body: form });
        if (!response.ok) throw toApiError(response.status, await readJsonSafe(response));
      }
      const result = await apiFetchJson<{ status: string }>(`/learning/attempts/${attemptId}/submit`, { method: "POST" });
      await refresh(); setSelected(null); setTab("courses"); setFiles([]);
      setMessage(result.status === "manual_review" ? "Работа ожидает ручной проверки." : "Работа оценена. Результат появился в «Моём прогрессе».");
    } catch (e) { setMessage(e instanceof Error ? e.message : "Не удалось отправить работу"); }
    finally { setBusy(false); }
  }
  function openExercise() {
    if (assignment?.work_url) window.open(assignment.work_url, "_blank", "noopener,noreferrer");
    else setMessage(assignment?.message || "Учебная запись пока не назначена");
  }
  async function openGuide() {
    if (!catalog?.guide.available) { setMessage("Утверждённая версия руководства ещё не прикреплена к курсу."); return; }
    const newTab = window.open("", "_blank");
    try {
      const response = await fetch(buildUrl("/learning/guide"), { headers: buildHeaders() });
      if (!response.ok) throw toApiError(response.status, await readJsonSafe(response));
      const url = URL.createObjectURL(await response.blob());
      if (newTab) newTab.location.href = url;
      else setMessage("Браузер заблокировал вкладку руководства. Разрешите всплывающие окна для локального адреса.");
    } catch (e) { newTab?.close(); setMessage(e instanceof Error ? e.message : "Не удалось открыть руководство"); }
  }
  async function review(id: string) {
    setBusy(true); setMessage("");
    try { await apiFetchJson(`/learning/attempts/${id}/review`, { method: "POST", body: { score: scores[id] ?? 0, required_met: required[id] ?? false, criteria: criteriaMarks[id] ?? Array(5).fill(false), note: reviewNotes[id] ?? "" } }); await refresh(); setMessage("Оценка сохранена"); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Не удалось сохранить оценку"); }
    finally { setBusy(false); }
  }
  async function inspect(id: string) {
    setMessage("");
    try {
      const data = await apiFetchJson<{ record: { application_ref: string; action: string }; screenshots: Array<{ id: string }> }>(`/learning/attempts/${id}`);
      const images: string[] = [];
      for (const shot of data.screenshots) {
        const response = await fetch(buildUrl(`/learning/screenshots/${shot.id}`), { headers: buildHeaders() });
        if (!response.ok) throw toApiError(response.status, await readJsonSafe(response));
        images.push(URL.createObjectURL(await response.blob()));
      }
      setEvidence((previous) => ({ ...previous, [id]: { ref: data.record.application_ref, action: data.record.action, images } }));
    } catch (e) { setMessage(e instanceof Error ? e.message : "Не удалось открыть снимки"); }
  }

  const learnerCatalog = catalog && progress && HIRE_ROUTE_LESSON_CODES.every(code => Boolean(progress.lessons[code]))
    ? { ...catalog, lessons: catalog.lessons.filter(lesson => !HIRE_ROUTE_LESSON_CODES.includes(lesson.code)) } : catalog;
  return <main className="min-h-screen bg-white px-4 py-8 text-zinc-900 sm:px-6"><div className="mx-auto max-w-5xl space-y-6">
    <TrainingNavigation active="progress" />
    <header><p className="text-sm font-medium text-blue-700">Учебные занятия Corpsite</p><h1 className="mt-1 text-3xl font-semibold">Обучение</h1><p className="mt-1 text-zinc-600">Курс «{catalog?.course.title ?? "Администрирование заявлениями"}»</p></header>
    <nav aria-label="Разделы обучения" className="flex flex-wrap gap-2 border-b border-zinc-200 pb-3">
      {([["catalog", "Каталог"], ["courses", "Мои курсы"], ...(summary ? [["summary", "Мой прогресс"]] : []), ...(reviews.length ? [["reviews", "Проверка работ"]] : [])] as Array<[Tab, string]>).map(([key, label]) => <button key={key} className={tab === key && !selected ? primary : secondary} onClick={() => { setTab(key); setSelected(null); setMessage(""); }}>{label}</button>)}
    </nav>
    {message && <p role="status" className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm">{message}</p>}
    {selected ? <section className={`${panel} space-y-6`}>
      <button className="text-sm text-blue-700 underline" onClick={() => { setTab(selected.source); setSelected(null); setMessage(""); }}>← {selected.source === "catalog" ? "Каталог" : "Мои курсы"}</button>
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-sm text-zinc-500">{selected.source === "catalog" ? "Справка о занятии" : "Занятие курса"}</p><h2 className="mt-1 text-2xl font-semibold">{selected.lesson.title}</h2></div><button className={secondary} onClick={() => { setSelected(null); setTab("summary"); }}>Мой прогресс</button></div>
      {selected.source === "catalog" && <button className={primary} onClick={() => { setTab("courses"); void openLesson(selected.lesson, "courses"); }}>{progress?.lessons[selected.lesson.code]?.status === "draft" ? "Продолжить задание" : "Приступить к выполнению задания"}</button>}
      <Instruction lesson={selected.lesson} />
      {selected.source === "catalog" && <Criteria lesson={selected.lesson} />}
      {selected.source === "courses" && <div className="space-y-4 border-t border-zinc-200 pt-5">
        <div><h3 className="text-lg font-semibold">Учебное задание</h3><a className="mt-1 inline-block text-sm text-blue-700 underline" href={selected.lesson.guide_url ?? buildUrl("/learning/guide").toString()} target="_blank" rel="noopener noreferrer" onClick={selected.lesson.guide_url ? undefined : (event) => { event.preventDefault(); void openGuide(); }}>Руководство по выполнению задания</a><span className="ml-2 text-xs text-zinc-500">{selected.lesson.guide_url ? "Google Диск · откроется в новой вкладке" : catalog?.guide.available ? `Утверждённая версия ${catalog.guide.version}` : "Файл пока не прикреплён"}</span><p className="mt-2 text-sm">{selected.lesson.task}</p><p className="mt-1 text-sm text-zinc-600">Состояние: {statusLabel(currentStatus)}</p></div>
        {(selected.lesson.code === "resolution_2" || !cannotSubmit) && <div className="flex flex-wrap items-center gap-3"><button className={secondary} disabled={busy || !assignment} onClick={openExercise}>{isHireLesson(selected.lesson) ? "Открыть кадровую форму" : "Открыть учебную запись"}</button><span className="text-sm text-zinc-600">{isHireLesson(selected.lesson) && hireState?.application ? `Заявление № ${hireState.application.application_id} · статус ${hireState.application.status}` : assignment ? `${assignment.work_url ? "Учебное заявление" : "Локальный номер сценария"} ${assignment.application_ref}` : "Готовим учебное заявление…"}</span>{isHireLesson(selected.lesson) && <button className="text-sm text-blue-700 underline" onClick={() => void refreshHireState()}>Обновить статус</button>}</div>}
        {!cannotSubmit && <>
          {assignment && !assignment.work_url && <p className="text-sm text-amber-800">Рабочий экран записи пока недоступен в пилоте. Снимки можно сдать для проверки учебного сценария.</p>}
          <div className="grid gap-3 sm:grid-cols-2">{selected.lesson.screenshots.map((label, index) => <label key={label} className="block rounded-lg border border-zinc-200 p-3 text-sm font-medium">{label}<input className="mt-2 block w-full text-sm" type="file" accept="image/png,image/jpeg" onChange={(e) => { const next = [...files]; next[index] = e.target.files?.[0] ?? null; setFiles(next); }} />{previews[index] && <div className="mt-2"><Image src={previews[index]} alt={`Выбран: ${label}`} width={320} height={180} unoptimized className="max-h-32 w-auto rounded border object-contain" /><span className="mt-1 block text-xs text-zinc-600">{files[index]?.name} · выберите новый файл, чтобы заменить</span></div>}</label>)}</div>
          {selected.lesson.expected_action === "rejected" && <label className="block text-sm font-medium">Причина возражения <input className="mt-1 block w-full max-w-sm rounded-lg border border-zinc-300 p-2" value={detail} onChange={(e) => setDetail(e.target.value)} /></label>}
          <button className={primary} disabled={busy || !assignment || selected.lesson.screenshots.some((_, index) => !files[index])} onClick={submitLesson}>Отправить на проверку</button>
        </>}
        <Criteria lesson={selected.lesson} />
      </div>}
    </section> : tab === "catalog" && learnerCatalog ? <CatalogPanel catalog={learnerCatalog} selectedCourseCode={selectedCourseCode} onChooseCourse={setSelectedCourseCode} onOpenLesson={(lesson) => openLesson(lesson, "catalog")} />
    : tab === "courses" && catalog && progress ? <MyCoursesPanel catalog={catalog} progress={progress} onChooseCourse={setSelectedCourseCode} onOpenLesson={(lesson, referenceOnly) => openLesson(lesson, referenceOnly ? "catalog" : "courses")} onOpenProgress={() => setTab("summary")} />
    : tab === "reviews" ? <section className="space-y-3"><h2 className="text-2xl font-semibold">Проверка работ</h2>{reviews.map((item) => <article className={`${panel} space-y-3`} key={item.id}>
      <p>Участник #{item.participant_id} · {catalog?.lessons.find((lesson) => lesson.code === item.lesson_code)?.title ?? item.lesson_code} · попытка {item.attempt_no} · автоматическая оценка недоступна</p><button className="text-sm text-blue-700 underline" onClick={() => inspect(item.id)}>Показать снимки и запись</button>
      {evidence[item.id] && <div className="space-y-2"><p className="text-sm">Учебная запись {evidence[item.id].ref}: {actionLabels[evidence[item.id].action]}</p><div className="flex flex-wrap gap-2">{evidence[item.id].images.map((src, index) => <Image key={src} src={src} alt={`Снимок ${index + 1} попытки`} width={800} height={600} unoptimized className="max-h-96 max-w-full rounded border object-contain" />)}</div></div>}
      <div className="space-y-2"><p className="text-sm font-medium">Результаты по критериям</p>{catalog?.lessons.find((lesson) => lesson.code === item.lesson_code)?.criteria.map((criterion, index) => <label key={criterion} className="block text-sm"><input type="checkbox" checked={criteriaMarks[item.id]?.[index] ?? false} onChange={(e) => { const marks = [...(criteriaMarks[item.id] ?? Array(5).fill(false))]; marks[index] = e.target.checked; setCriteriaMarks({ ...criteriaMarks, [item.id]: marks }); setScores({ ...scores, [item.id]: marks.filter(Boolean).length }); const lesson = catalog.lessons.find((entry) => entry.code === item.lesson_code); if (criterion === lesson?.required) setRequired({ ...required, [item.id]: e.target.checked }); }} /> {criterion}{criterion === catalog.lessons.find((entry) => entry.code === item.lesson_code)?.required ? " (обязательный)" : ""}</label>)}</div>
      <label className="block text-sm">Комментарий проверяющего <textarea className="mt-1 block w-full rounded border border-zinc-300 p-2" value={reviewNotes[item.id] ?? ""} onChange={(e) => setReviewNotes({ ...reviewNotes, [item.id]: e.target.value })} /></label>
      <div className="flex flex-wrap items-center gap-3"><label className="text-sm">Баллы <select className="ml-2 rounded border border-zinc-300 p-2" value={scores[item.id] ?? 0} onChange={(e) => setScores({ ...scores, [item.id]: Number(e.target.value) })}>{[0,1,2,3,4,5].map((n) => <option key={n} value={n}>{n}/5</option>)}</select></label><span className="text-xs text-zinc-500">1 балл за каждый выполненный критерий</span><button className={primary} disabled={busy} onClick={() => review(item.id)}>Подтвердить оценку</button></div>
    </article>)}</section> : catalog && summary ? <SummaryPanel key={selectedCourseCode} catalog={catalog} selectedCourseCode={selectedCourseCode} summary={summary} viewerId={viewerId} viewerName={viewerName} onChooseCourse={(code) => { setSummary(null); setSelectedCourseCode(code); }} onOpenLesson={(lesson) => { setTab("courses"); void openLesson(lesson, "courses"); }} onRetake={(lesson) => { setTab("courses"); void openLesson(lesson, "courses", true); }} /> : null}
  </div></main>;
}
