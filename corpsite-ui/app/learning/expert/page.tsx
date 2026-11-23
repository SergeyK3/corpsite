"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import { apiFetchJson, buildHeaders, buildUrl } from "@/lib/api";
import { finalResultLabel, statusLabel } from "../LearningPanels";
import type { Lesson } from "../LearningPanels";
import TrainingNavigation from "../../training/_components/TrainingNavigation";

type Course = { code: string; title: string; audience: string; state: string };
type Catalog = { courses: Course[]; lessons: Lesson[] };
type Person = { user_id: number; name: string; unit_id: number; position_name: string };
type Preview = { lessons: Array<{ code: string; title: string }>; recipients: Person[]; due_at: string | null };
type Completion = { participant_id: number; participant_name: string; unit_id: number; course_code: string; lesson_code: string; lesson_title: string; status: string; attempt_id: string | null; attempt_no: number | null; application_id: number | null; score: number | null; review_source: string | null; auto_status: string; due_at: string | null };
type Attempt = { id: string; attempt_no: number; status: string; score: number | null; auto_status: string; auto_note: string; review_note: string; pre_score: number | null; review_source: string | null };
type AttemptDetail = { attempt: Attempt; history: Attempt[]; review_events: Array<{ id: string; old_score: number | null; new_score: number | null; new_status: string; source: string | null; reason: string; actor_id: number; created_at: string }>; lesson: Lesson; hire_application?: { application_id: number; status: string; full_name: string } | null; screenshots: Array<{ id: string; slot: number | null }>; criteria_results: Record<string, boolean> };
type LessonForm = { course_code: string; title: string; target_role: string; minutes: number; task: string; instruction: string; guide_url: string; criteria: string; required_index: number; screenshots: string };
type AssignmentForm = { target_type: "lesson" | "course"; target_code: string; employee_ids: string; position_name: string; unit_id: string; due_at: string };

const primary = "rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50";
const secondary = "rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm hover:bg-zinc-50";
const input = "mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm";
const card = "rounded-xl border border-zinc-200 bg-white p-5 shadow-sm";
const emptyLesson = (course_code: string): LessonForm => ({ course_code, title: "", target_role: "", minutes: 12, task: "", instruction: "", guide_url: "", criteria: "", required_index: 0, screenshots: "Снимок результата" });
const splitLines = (value: string) => value.split("\n").map((part) => part.trim()).filter(Boolean);

export default function ExpertLearningPage() {
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [canReview, setCanReview] = useState(false);
  const [tab, setTab] = useState<"catalog" | "assignments" | "completion">("catalog");
  const [catalog, setCatalog] = useState<Catalog>({ courses: [], lessons: [] });
  const [courseCode, setCourseCode] = useState("");
  const [courseTitle, setCourseTitle] = useState("");
  const [courseAudience, setCourseAudience] = useState("");
  const [lessonCode, setLessonCode] = useState("");
  const [lessonForm, setLessonForm] = useState<LessonForm>(emptyLesson(""));
  const [previewLesson, setPreviewLesson] = useState<Lesson | null>(null);
  const [assignment, setAssignment] = useState<AssignmentForm>({ target_type: "lesson", target_code: "", employee_ids: "", position_name: "Кадровик", unit_id: "1", due_at: "" });
  const [preview, setPreview] = useState<Preview | null>(null);
  const [rows, setRows] = useState<Completion[]>([]);
  const [filters, setFilters] = useState({ employee_id: "", unit_id: "", course_code: "", lesson_code: "", status: "" });
  const [detail, setDetail] = useState<AttemptDetail | null>(null);
  const [chosenAttempt, setChosenAttempt] = useState<string | null>(null);
  const [images, setImages] = useState<Record<string, string>>({});
  const [marks, setMarks] = useState<boolean[]>([]);
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const [nextCatalog, nextRows] = await Promise.all([
      apiFetchJson<Catalog>("/learning/expert/catalog"),
      apiFetchJson<{ items: Completion[] }>("/learning/expert/completion"),
    ]);
    setCatalog(nextCatalog); setRows(nextRows.items);
    if (!courseCode && nextCatalog.courses[0]) setCourseCode(nextCatalog.courses[0].code);
  }, [courseCode]);
  useEffect(() => {
    apiFetchJson<{ has_learning_expert?: boolean; has_learning_review?: boolean }>("/auth/me")
      .then((me) => { setAllowed(me.has_learning_expert === true); setCanReview(me.has_learning_review === true); })
      .catch(() => setAllowed(false));
  }, []);
  useEffect(() => { if (allowed) refresh().catch((error) => setMessage(error.message)); }, [allowed, refresh]);
  useEffect(() => () => Object.values(images).forEach(URL.revokeObjectURL), [images]);
  useEffect(() => {
    const code = new URLSearchParams(window.location.search).get("lesson");
    const found = catalog.lessons.find((item) => item.code === code);
    if (!found) return;
    setCourseCode(found.course_code);
    setLessonCode(found.code);
    setLessonForm({ course_code: found.course_code, title: found.title, target_role: found.target_role,
      minutes: found.minutes, task: found.task, instruction: found.instruction,
      guide_url: found.guide_url ?? "", criteria: found.criteria.join("\n"),
      required_index: Math.max(0, found.criteria.indexOf(found.required)), screenshots: found.screenshots.join("\n") });
  }, [catalog.lessons]);

  function selectCourse(code: string) {
    const found = catalog.courses.find((item) => item.code === code);
    setCourseCode(code); setCourseTitle(found?.title ?? ""); setCourseAudience(found?.audience ?? "");
    setLessonCode(""); setLessonForm(emptyLesson(code)); setPreviewLesson(null);
  }
  function selectLesson(code: string) {
    const found = catalog.lessons.find((item) => item.code === code);
    const url = new URL(window.location.href);
    url.searchParams.set("lesson", code);
    window.history.replaceState(null, "", url.toString());
    setLessonCode(code); setPreviewLesson(null);
    setLessonForm(found ? { course_code: found.course_code, title: found.title, target_role: found.target_role, minutes: found.minutes,
      task: found.task, instruction: found.instruction, guide_url: found.guide_url ?? "", criteria: found.criteria.join("\n"),
      required_index: Math.max(0, found.criteria.indexOf(found.required)), screenshots: found.screenshots.join("\n") } : emptyLesson(courseCode));
  }
  async function run(action: () => Promise<void>) {
    setBusy(true); setMessage("");
    try { await action(); } catch (error) { setMessage(error instanceof Error ? error.message : "Не удалось выполнить действие"); }
    finally { setBusy(false); }
  }
  async function saveCourse() {
    await run(async () => {
      const saved = await apiFetchJson<Course>(courseCode ? `/learning/expert/courses/${courseCode}` : "/learning/expert/courses", { method: courseCode ? "PUT" : "POST", body: { title: courseTitle, audience: courseAudience } });
      await refresh(); selectCourse(saved.code); setMessage("Курс сохранён");
    });
  }
  async function saveLesson() {
    await run(async () => {
      const body = { ...lessonForm, criteria: splitLines(lessonForm.criteria), screenshots: splitLines(lessonForm.screenshots) };
      const saved = await apiFetchJson<Lesson>(lessonCode ? `/learning/expert/lessons/${lessonCode}` : "/learning/expert/lessons", { method: lessonCode ? "PUT" : "POST", body });
      await refresh(); setLessonCode(saved.code); setMessage("Черновик занятия сохранён");
    });
  }
  async function publishLesson() {
    if (!lessonCode) return;
    await run(async () => { await apiFetchJson(`/learning/expert/lessons/${lessonCode}/publish`, { method: "POST" }); await refresh(); setMessage("Занятие опубликовано"); });
  }
  function assignmentBody(expected_recipient_ids: number[] = []) {
    return { target_type: assignment.target_type, target_code: assignment.target_code,
      selector: { employee_ids: assignment.employee_ids.split(",").map((value) => Number(value.trim())).filter((value) => Number.isInteger(value) && value > 0), position_name: assignment.position_name.trim(), unit_id: assignment.unit_id ? Number(assignment.unit_id) : null },
      due_at: assignment.due_at ? new Date(assignment.due_at).toISOString() : null, expected_recipient_ids };
  }
  async function previewAssignment() {
    await run(async () => { setPreview(await apiFetchJson<Preview>("/learning/expert/assignments/preview", { method: "POST", body: assignmentBody() })); });
  }
  async function confirmAssignment() {
    if (!preview) return;
    await run(async () => {
      const saved = await apiFetchJson<{ created: number; existing: number }>("/learning/expert/assignments", { method: "POST", body: assignmentBody(preview.recipients.map((item) => item.user_id)) });
      setPreview(null); await refresh(); setMessage(`Назначено: ${saved.created}. Уже назначено: ${saved.existing}.`);
    });
  }
  async function loadCompletion() {
    await run(async () => {
      const query = Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== ""));
      const result = await apiFetchJson<{ items: Completion[] }>("/learning/expert/completion", { query });
      setRows(result.items); setDetail(null);
    });
  }
  async function openAttempt(id: string) {
    if (/^\d+$/.test(id)) {
      window.location.assign(`/training/attempts/${id}`);
      return;
    }
    await run(async () => {
      const result = await apiFetchJson<AttemptDetail>(`/learning/expert/attempts/${id}`);
      const blobs = await Promise.all(result.screenshots.map(async (shot) => {
        const response = await fetch(buildUrl(`/learning/screenshots/${shot.id}`), { headers: buildHeaders() });
        return [shot.id, response.ok ? URL.createObjectURL(await response.blob()) : ""] as const;
      }));
      setDetail(result); setChosenAttempt(id); setImages(Object.fromEntries(blobs));
      setMarks(result.lesson.criteria.map((_, index) => result.criteria_results[index] ?? false));
      setNote(result.attempt.review_note ?? ""); setReason("");
    });
  }
  async function saveReview() {
    if (!detail || !chosenAttempt) return;
    await run(async () => {
      const isCorrection = detail.attempt.score !== null;
      await apiFetchJson(`/learning/attempts/${chosenAttempt}/review`, { method: isCorrection ? "PATCH" : "POST", body: {
        score: marks.filter(Boolean).length, required_met: marks[detail.lesson.criteria.indexOf(detail.lesson.required)] ?? false,
        criteria: marks, note, reason,
      } });
      await openAttempt(chosenAttempt); await refresh(); setMessage(isCorrection ? "Итог пересмотрен, история сохранена" : "Итоговая оценка сохранена");
    });
  }

  if (allowed === null) return <main className="p-8">Загружаем кабинет…</main>;
  if (!allowed) return <main className="p-8"><h1 className="text-2xl font-semibold">Внутреннее обучение</h1><p className="mt-3">Нет разрешения на открытие кабинета.</p></main>;
  return <main className="min-h-screen bg-zinc-50 px-4 py-8 text-zinc-900 sm:px-6"><div className="mx-auto max-w-6xl space-y-5">
    <TrainingNavigation active="expert" />
    <header><p className="text-sm font-medium text-blue-700">Рабочий кабинет</p><h1 className="mt-1 text-3xl font-semibold">Внутреннее обучение</h1><p className="mt-1 text-zinc-600">Каталог, назначения и выполнение</p></header>
    <nav aria-label="Внутреннее обучение" className="flex gap-2 border-b border-zinc-200 pb-3">{([ ["catalog", "Каталог"], ["assignments", "Назначения"], ["completion", "Выполнение"] ] as const).map(([key, label]) => <button key={key} className={tab === key ? primary : secondary} onClick={() => { setTab(key); setMessage(""); }}>{label}</button>)}</nav>
    {message && <p role="status" className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm">{message}</p>}
    {tab === "catalog" && <div className="grid gap-5 lg:grid-cols-[300px_1fr]">
      <aside className={`${card} space-y-4`}><div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Курсы</h2><button className="text-sm text-blue-700 underline" onClick={() => { setCourseCode(""); setCourseTitle(""); setCourseAudience(""); setLessonCode(""); setLessonForm(emptyLesson("")); }}>Новый</button></div>
        <div className="space-y-1">{catalog.courses.map((item) => <button key={item.code} className={`block w-full rounded-lg px-3 py-2 text-left text-sm ${courseCode === item.code ? "bg-blue-50 text-blue-900" : "hover:bg-zinc-50"}`} onClick={() => selectCourse(item.code)}>{item.title}<span className="block text-xs text-zinc-500">{item.state === "published" ? "Опубликован" : "Черновик"}</span></button>)}</div>
        <label className="block text-sm">Название курса<input aria-label="Название курса" className={input} value={courseTitle} onChange={(e) => setCourseTitle(e.target.value)} /></label>
        <label className="block text-sm">Целевая аудитория<input className={input} value={courseAudience} onChange={(e) => setCourseAudience(e.target.value)} /></label>
        <button className={primary} disabled={busy || !courseTitle.trim()} onClick={saveCourse}>Сохранить курс</button>
        {courseCode && catalog.courses.find((item) => item.code === courseCode)?.state === "draft" && <button className={secondary} disabled={busy} onClick={() => void run(async () => { await apiFetchJson(`/learning/expert/courses/${courseCode}/publish`, { method: "POST" }); await refresh(); setMessage("Курс опубликован"); })}>Опубликовать курс</button>}
      </aside>
      <section className={`${card} space-y-4`}><div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Занятия</h2><button className="text-sm text-blue-700 underline" disabled={!courseCode} onClick={() => selectLesson("")}>Новое занятие</button></div>
        {catalog.lessons.some((item) => item.course_code === courseCode && item.route_step) && <p className="text-sm font-medium">Подкурс «Приём нового сотрудника на работу» · один кандидат и связанное заявление</p>}
        <div className="flex flex-wrap gap-2">{catalog.lessons.filter((item) => item.course_code === courseCode).map((item) => <button key={item.code} className={`rounded-lg border px-3 py-2 text-left text-sm ${lessonCode === item.code ? "border-blue-500 bg-blue-50" : "border-zinc-200"}`} onClick={() => selectLesson(item.code)}>{item.route_step ? `${item.route_step}. ` : ""}{item.title}<span className="ml-2 text-xs text-zinc-500">{item.state === "published" ? "Опубликовано" : "Черновик"}</span></button>)}</div>
        {courseCode && <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm sm:col-span-2">Название занятия<input aria-label="Название занятия" className={input} value={lessonForm.title} onChange={(e) => setLessonForm({ ...lessonForm, title: e.target.value })} /></label>
          <label className="block text-sm">Целевая роль<input aria-label="Целевая роль" className={input} value={lessonForm.target_role} onChange={(e) => setLessonForm({ ...lessonForm, target_role: e.target.value })} /></label>
          <label className="block text-sm">Длительность, минут<input aria-label="Длительность, минут" type="number" min={1} max={480} className={input} value={lessonForm.minutes} onChange={(e) => setLessonForm({ ...lessonForm, minutes: Number(e.target.value) })} /></label>
          <label className="block text-sm sm:col-span-2">Задание<textarea aria-label="Задание" rows={2} className={input} value={lessonForm.task} onChange={(e) => setLessonForm({ ...lessonForm, task: e.target.value })} /></label>
          <label className="block text-sm sm:col-span-2">Инструкция для участника<textarea rows={2} className={input} value={lessonForm.instruction} onChange={(e) => setLessonForm({ ...lessonForm, instruction: e.target.value })} /></label>
          <label className="block text-sm sm:col-span-2">Ссылка на Google Документ<input aria-label="Ссылка на Google Документ" type="url" className={input} value={lessonForm.guide_url} onChange={(e) => setLessonForm({ ...lessonForm, guide_url: e.target.value })} /></label>
          <label className="block text-sm">Критерии зачёта, по одному в строке<textarea aria-label="Критерии зачёта" rows={5} className={input} value={lessonForm.criteria} onChange={(e) => setLessonForm({ ...lessonForm, criteria: e.target.value })} /></label>
          <div className="space-y-3"><label className="block text-sm">Обязательный критерий<select className={input} value={lessonForm.required_index} onChange={(e) => setLessonForm({ ...lessonForm, required_index: Number(e.target.value) })}>{splitLines(lessonForm.criteria).map((item, index) => <option value={index} key={index}>{item}</option>)}</select></label><label className="block text-sm">Нужные снимки, по одному в строке<textarea rows={2} className={input} value={lessonForm.screenshots} onChange={(e) => setLessonForm({ ...lessonForm, screenshots: e.target.value })} /></label></div>
        </div>}
        {courseCode && <div className="flex flex-wrap gap-2"><button className={primary} disabled={busy} onClick={saveLesson}>Сохранить черновик</button><button className={secondary} disabled={!lessonCode || busy} onClick={() => void run(async () => setPreviewLesson(await apiFetchJson<Lesson>(`/learning/expert/lessons/${lessonCode}/preview`)))}>Предпросмотр глазами участника</button><button className={secondary} disabled={!lessonCode || busy} onClick={publishLesson}>Опубликовать занятие</button></div>}
        {previewLesson && <div className="rounded-xl border border-blue-200 bg-blue-50 p-4"><p className="text-xs font-semibold uppercase text-blue-700">Предпросмотр участника</p><h3 className="mt-1 text-xl font-semibold">{previewLesson.title}</h3><p className="mt-1 text-sm">{previewLesson.target_role} · {previewLesson.minutes} минут</p><p className="mt-3">{previewLesson.task}</p><p className="mt-2 text-sm">{previewLesson.instruction}</p>{previewLesson.guide_url && <a className="mt-2 inline-block text-blue-700 underline" href={previewLesson.guide_url} target="_blank" rel="noreferrer">Открыть инструкцию</a>}<ul className="mt-3 list-disc pl-5 text-sm">{previewLesson.criteria.map((item) => <li key={item}>{item}{item === previewLesson.required ? " (обязательный)" : ""}</li>)}</ul></div>}
      </section></div>}
    {tab === "assignments" && <section className={`${card} space-y-4`}><h2 className="text-xl font-semibold">Новое назначение</h2>
      <div className="grid gap-4 sm:grid-cols-2"><label className="block text-sm">Что назначить<select className={input} value={assignment.target_type} onChange={(e) => { setAssignment({ ...assignment, target_type: e.target.value as "course" | "lesson", target_code: "" }); setPreview(null); }}><option value="lesson">Занятие</option><option value="course">Курс</option></select></label><label className="block text-sm">Название<select aria-label="Назначаемое занятие или курс" className={input} value={assignment.target_code} onChange={(e) => { setAssignment({ ...assignment, target_code: e.target.value }); setPreview(null); }}><option value="">Выберите</option>{assignment.target_type === "lesson" && <><option value="hire_route_v1">Приём нового сотрудника на работу</option><option value="training:skill_2">Одобрить заявление о приёме на работу</option></>}{(assignment.target_type === "course" ? catalog.courses : catalog.lessons).filter((item) => item.state === "published" && (assignment.target_type === "course" || !["lesson_5b2e5028ea63", "hire_path_02_personal_card", "hire_path_03_order_draft", "hire_path_04_sign_register", "hire_path_05_notify_ack"].includes(item.code))).map((item) => <option key={item.code} value={item.code}>{item.title}</option>)}</select></label>
      <label className="block text-sm">ID сотрудников через запятую<input className={input} value={assignment.employee_ids} onChange={(e) => { setAssignment({ ...assignment, employee_ids: e.target.value }); setPreview(null); }} placeholder="401, 402" /></label>
      <label className="block text-sm">Должность<input aria-label="Должность получателей" className={input} value={assignment.position_name} onChange={(e) => { setAssignment({ ...assignment, position_name: e.target.value }); setPreview(null); }} /></label>
      <label className="block text-sm">ID подразделения<input aria-label="ID подразделения" type="number" className={input} value={assignment.unit_id} onChange={(e) => { setAssignment({ ...assignment, unit_id: e.target.value }); setPreview(null); }} /></label>
      <label className="block text-sm">Срок, если нужен<input type="datetime-local" className={input} value={assignment.due_at} onChange={(e) => { setAssignment({ ...assignment, due_at: e.target.value }); setPreview(null); }} /></label></div>
      <button className={primary} disabled={busy || !assignment.target_code} onClick={previewAssignment}>Показать получателей</button>
      {preview && <div className="rounded-xl border border-blue-200 bg-blue-50 p-4"><h3 className="font-semibold">Подтверждение назначения</h3><p className="mt-1 text-sm">Занятий: {preview.lessons.map((item) => item.title).join(", ")}</p><p className="mt-1 text-sm">Срок: {preview.due_at ? new Date(preview.due_at).toLocaleString("ru-RU") : "не задан"}</p><ul className="my-3 list-disc pl-5 text-sm">{preview.recipients.map((person) => <li key={person.user_id}>{person.name} · {person.position_name} · подразделение {person.unit_id}</li>)}</ul><button className={primary} disabled={busy} onClick={confirmAssignment}>Подтвердить назначение</button></div>}
    </section>}
    {tab === "completion" && <section className={`${card} space-y-4`}><h2 className="text-xl font-semibold">Выполнение</h2>
      <div className="grid gap-3 sm:grid-cols-5"><label className="text-sm">Сотрудник, ID<input className={input} value={filters.employee_id} onChange={(e) => setFilters({ ...filters, employee_id: e.target.value })} /></label><label className="text-sm">Подразделение, ID<input className={input} value={filters.unit_id} onChange={(e) => setFilters({ ...filters, unit_id: e.target.value })} /></label><label className="text-sm">Курс<select className={input} value={filters.course_code} onChange={(e) => setFilters({ ...filters, course_code: e.target.value })}><option value="">Все</option>{catalog.courses.map((item) => <option key={item.code} value={item.code}>{item.title}</option>)}</select></label><label className="text-sm">Занятие<select className={input} value={filters.lesson_code} onChange={(e) => setFilters({ ...filters, lesson_code: e.target.value })}><option value="">Все</option>{catalog.lessons.map((item) => <option key={item.code} value={item.code}>{item.title}</option>)}</select></label><label className="text-sm">Статус<select className={input} value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}><option value="">Все</option><option value="not_started">Не начато</option><option value="draft">Черновик</option><option value="manual_review">Ожидает ручной проверки</option><option value="passed">Зачтено</option><option value="failed">Не зачтено</option></select></label></div>
      <button className={secondary} onClick={loadCompletion}>Применить фильтры</button>
      <div className="overflow-x-auto"><table className="w-full min-w-[820px] text-sm"><thead><tr className="border-b border-zinc-200 text-left"><th className="p-2">Сотрудник</th><th className="p-2">Подразделение</th><th className="p-2">Занятие</th><th className="p-2">Заявление</th><th className="p-2">Статус</th><th className="p-2">Итог</th><th className="p-2">Попытка</th></tr></thead><tbody>{rows.map((row) => <tr key={row.attempt_id ?? `${row.participant_id}:${row.lesson_code}:not-started`} className="border-b border-zinc-100"><td className="p-2">{row.participant_name}</td><td className="p-2">{row.unit_id}</td><td className="p-2">{row.lesson_title}</td><td className="p-2">{row.application_id ? `№ ${row.application_id}` : "—"}</td><td className="p-2">{statusLabel(row.status)}</td><td className="p-2">{finalResultLabel(row.score, row.status, row.review_source)}</td><td className="p-2">{row.attempt_id && <button className="text-blue-700 underline" onClick={() => openAttempt(row.attempt_id!)}>Открыть попытку {row.attempt_no}</button>}</td></tr>)}</tbody></table>{rows.length === 0 && <p className="p-3 text-sm text-zinc-500">Назначений по фильтрам нет.</p>}</div>
      {detail && <div className="space-y-4 rounded-xl border border-zinc-200 bg-zinc-50 p-4"><h3 className="text-lg font-semibold">Попытка {detail.attempt.attempt_no}: {detail.lesson.title}</h3><div className="flex flex-wrap gap-2">{detail.history.map((item) => <button key={item.id} className={secondary} onClick={() => openAttempt(item.id)}>Попытка {item.attempt_no} · {finalResultLabel(item.score, item.status, item.review_source)}</button>)}</div>
        {detail.hire_application && <p className="rounded-lg bg-blue-50 p-3 text-sm">Кадровое заявление № {detail.hire_application.application_id} · {detail.hire_application.status} · {detail.hire_application.full_name}</p>}
        <p className="text-sm">Автоматическая проверка: {detail.attempt.auto_status === "complete" ? detail.attempt.auto_note || "Итог получен" : detail.attempt.auto_status === "failed" ? "Не удалось определить итог" : "Недоступна"}</p><p className="text-sm">Итоговая оценка: {finalResultLabel(detail.attempt.score, detail.attempt.status, detail.attempt.review_source)} · {detail.attempt.review_note || "Без комментария"}</p>
        <div className="grid gap-3 sm:grid-cols-2">{detail.screenshots.map((shot) => <div key={shot.id} className="rounded-lg border border-zinc-200 bg-white p-2"><p className="mb-2 text-sm">Снимок {shot.slot === null ? "" : shot.slot + 1}</p>{images[shot.id] && <Image src={images[shot.id]} width={640} height={400} alt="Снимок попытки" unoptimized className="max-h-64 w-auto object-contain" />}</div>)}</div>
        {canReview && <div className="space-y-3 border-t border-zinc-200 pt-4"><h4 className="font-semibold">{detail.attempt.score === null ? "Ручная проверка" : "Пересмотр итога"}</h4>{detail.lesson.criteria.map((item, index) => <label key={index} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={marks[index] ?? false} onChange={(e) => setMarks(marks.map((value, i) => i === index ? e.target.checked : value))} />{item}{item === detail.lesson.required && <strong>(обязательный)</strong>}</label>)}<label className="block text-sm">Комментарий<textarea className={input} value={note} onChange={(e) => setNote(e.target.value)} /></label>{detail.attempt.score !== null && <label className="block text-sm">Основание пересмотра<input aria-label="Основание пересмотра" className={input} value={reason} onChange={(e) => setReason(e.target.value)} /></label>}<button className={primary} disabled={busy || (detail.attempt.score !== null && !reason.trim())} onClick={saveReview}>Сохранить итог: {marks.filter(Boolean).length}/5</button></div>}
        {detail.review_events.length > 0 && <div><h4 className="font-semibold">История итогов</h4><ul className="mt-1 space-y-1 text-sm">{detail.review_events.map((item) => <li key={item.id}>{new Date(item.created_at).toLocaleString("ru-RU")} · {item.old_score === null ? "—" : `${item.old_score}/5`} → {finalResultLabel(item.new_score, item.new_status, item.source)} · {item.reason || "Первая оценка"} · автор {item.actor_id ?? "—"}</li>)}</ul></div>}
      </div>}
    </section>}
  </div></main>;
}
