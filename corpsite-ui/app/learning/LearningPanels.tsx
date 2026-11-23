"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { apiFetchJson, buildHeaders, buildUrl } from "@/lib/api";

export const HIRE_ROUTE_LESSON_CODES = ["lesson_5b2e5028ea63", "hire_path_02_personal_card", "hire_path_03_order_draft", "hire_path_04_sign_register", "hire_path_05_notify_ack"];

export type Lesson = { code: string; course_code: string; target_role: string; state: string; function: string; skill: string; number: number; route_step?: number; route_title?: string; minutes: number; title: string; instruction: string; task: string; screenshots: string[]; criteria: string[]; required: string; expected_action: string; guide_url?: string };
export type Course = { code: string; title: string; state?: string };
export type Catalog = { course: Course; courses: Course[]; lessons: Lesson[]; guide: { available: boolean; version: string } };
export type Score = { points: number; maximum: number; passed: number; pending: number; total: number; average?: number | null };
export type LessonProgress = { status: string; score: number | null; review_source?: string | null; best_score: number | null; maximum: number; attempt_id?: string | null; result_attempt_id?: string | null; attempt_no?: number | null };
export type Progress = { course: Course & Score; courses?: Array<Course & Score>; skills: Record<string, Score>; functions: Record<string, Score>; lessons: Record<string, LessonProgress>; completed_courses?: CourseProgress[] };
export type CourseProgress = { course: Course & Score; lessons: Record<string, LessonProgress>; example?: boolean };
export type Summary = { course: Course & Score; lessons: Record<string, LessonProgress> };

const section = "overflow-hidden rounded-xl border border-zinc-200 bg-white";
const rowButton = "text-left text-blue-700 hover:underline";
const actionButton = "rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-800 hover:bg-zinc-50";

export function statusLabel(value?: string) {
  return ({ passed: "Зачтено", manual_review: "Ожидает ручной проверки", draft: "Черновик", failed: "Не зачтено" } as Record<string, string>)[value ?? ""] ?? "Не начато";
}

export function finalResultLabel(score: number | null | undefined, status?: string | null, source?: string | null) {
  if (score === null || score === undefined) return statusLabel(status ?? undefined);
  const sourceLabel = source === "manual" ? "Ручная" : source === "automatic" ? "Автоматическая" : "Источник не указан";
  return `${score}/5 · ${sourceLabel}`;
}

export function CatalogPanel({ catalog, selectedCourseCode, onChooseCourse, onOpenLesson }: {
  catalog: Catalog; selectedCourseCode: string; onChooseCourse: (code: string) => void; onOpenLesson: (lesson: Lesson) => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const filtered = catalog.lessons.filter((lesson) => lesson.course_code === selectedCourseCode && lesson.title.toLocaleLowerCase("ru").includes(query.trim().toLocaleLowerCase("ru")));
  return <section className="space-y-4">
    <div><h2 className="text-2xl font-semibold">Каталог</h2><p className="text-sm text-zinc-600">Выберите курс, чтобы посмотреть занятия.</p></div>
    <div className={section}>
      {catalog.courses.map((course) => <div key={course.code} className="border-b border-zinc-200 last:border-b-0">
        {course.state === "preparing" ? <div className="flex items-center justify-between gap-3 px-4 py-3"><span className="font-medium">{course.title}</span><span className="rounded-full bg-zinc-100 px-3 py-1 text-xs text-zinc-600">В подготовке</span></div>
          : <><button aria-expanded={open && selectedCourseCode === course.code} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-zinc-50" onClick={() => { onChooseCourse(course.code); setOpen(selectedCourseCode === course.code ? !open : true); }}><span aria-hidden="true" className="w-4 text-blue-700">{open && selectedCourseCode === course.code ? "▾" : "▸"}</span><span className="font-medium">{course.title}</span><span className="ml-auto text-xs text-zinc-500">{catalog.lessons.filter((lesson) => lesson.course_code === course.code).length} занятия</span></button>
            {open && selectedCourseCode === course.code && <div className="border-t border-zinc-200 bg-zinc-50/50 px-4 py-3">
              <label className="block text-sm font-medium">Поиск по названиям занятий <input type="search" className="mt-1 block w-full max-w-md rounded-md border border-zinc-300 bg-white px-3 py-2" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Название занятия" /></label>
              <div className="mt-3 divide-y divide-zinc-200 rounded-lg border border-zinc-200 bg-white">{filtered.map((lesson) => <div key={lesson.code} className="flex items-center gap-3 px-3 py-2 text-sm"><span className="w-5 text-zinc-400">{lesson.number}</span><button className={rowButton} onClick={() => onOpenLesson(lesson)}>{lesson.title}</button><span className="ml-auto whitespace-nowrap text-zinc-500">{lesson.minutes} мин</span></div>)}</div>
              {filtered.length === 0 && <p className="mt-2 text-sm text-zinc-600">Занятия не найдены.</p>}
            </div>}</>}
      </div>)}
    </div>
  </section>;
}

function CourseTable({ title, tint, entries, catalog, onOpenLesson, onChooseCourse }: {
  title: string; tint: "blue" | "green"; entries: CourseProgress[]; catalog: Catalog;
  onOpenLesson: (lesson: Lesson, referenceOnly: boolean) => void; onChooseCourse: (code: string) => void;
}) {
  const [blockOpen, setBlockOpen] = useState(true);
  const [openCourses, setOpenCourses] = useState<string[]>([]);
  const [openLessons, setOpenLessons] = useState<string[]>([]);
  const toggle = (values: string[], setter: (value: string[]) => void, key: string) => setter(values.includes(key) ? values.filter((item) => item !== key) : [...values, key]);
  const tintClass = tint === "blue" ? "bg-sky-100 text-sky-950" : "bg-emerald-100 text-emerald-950";
  return <section className={section} aria-label={title}>
    <button className={`flex w-full items-center gap-2 px-4 py-3 text-left font-semibold ${tintClass}`} aria-expanded={blockOpen} onClick={() => setBlockOpen(!blockOpen)}><span aria-hidden="true">{blockOpen ? "▾" : "▸"}</span>{title}<span className="ml-auto text-sm font-normal">{entries.length}</span></button>
    {blockOpen && <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-sm"><thead><tr className="border-b border-zinc-200 bg-zinc-50 text-left text-zinc-600"><th className="px-4 py-2 font-medium">Курс</th><th className="px-3 py-2 font-medium">Зачтено</th><th className="px-3 py-2 font-medium">Баллы</th><th className="px-3 py-2 font-medium">Итоговая оценка</th><th className="px-4 py-2 font-medium">Действие</th></tr></thead><tbody>
      {entries.map((entry) => {
        const key = entry.course.code;
        const courseOpen = openCourses.includes(key);
        const next = catalog.lessons.find((lesson) => lesson.course_code === key && ["not_started", "draft", "failed"].includes(entry.lessons[lesson.code]?.status));
        return <tr key={key} className="border-b border-zinc-200 last:border-b-0"><td colSpan={5} className="p-0"><table className="w-full table-fixed text-sm"><tbody><tr className="border-b border-zinc-100"><td className="w-[40%] px-4 py-2"><button className="flex items-center gap-2 text-left font-medium hover:underline" aria-expanded={courseOpen} onClick={() => { toggle(openCourses, setOpenCourses, key); if (!entry.example) onChooseCourse(key); }}><span aria-hidden="true" className="w-4 text-blue-700">{courseOpen ? "▾" : "▸"}</span>{entry.course.title}</button>{entry.example && <span className="ml-6 text-xs text-zinc-500">Учебный пример · архивный проход</span>}</td><td className="w-[14%] px-3 py-2">{entry.course.passed}/{entry.course.total}</td><td className="w-[14%] px-3 py-2">{entry.course.points}/{entry.course.maximum}</td><td className="w-[16%] px-3 py-2">{entry.course.average === null ? "—" : `${entry.course.average}/5`}</td><td className="w-[16%] px-4 py-2">{next && !entry.example && <button className={actionButton} onClick={() => { onChooseCourse(key); onOpenLesson(next, false); }}>Продолжить</button>}</td></tr>
          {courseOpen && <tr><td colSpan={5} className="bg-zinc-50/60 px-6 py-2"><table className="w-full text-sm"><thead><tr className="text-left text-xs text-zinc-500"><th className="py-1 font-medium">Занятие</th><th className="w-32 py-1 font-medium">Статус</th><th className="w-24 py-1 font-medium">Баллы</th><th className="w-24 py-1 font-medium">Раскрыть</th></tr></thead><tbody>{catalog.lessons.filter((lesson) => lesson.course_code === key).map((lesson) => {
            const lessonKey = `${key}:${lesson.code}`;
            const expanded = openLessons.includes(lessonKey);
            const value = entry.lessons[lesson.code];
            return <tr key={lessonKey} className="border-t border-zinc-200"><td colSpan={4} className="p-0"><table className="w-full text-sm"><tbody><tr><td className="py-1.5"><button className="text-left hover:underline" aria-expanded={expanded} onClick={() => toggle(openLessons, setOpenLessons, lessonKey)}>{lesson.title}</button></td><td className="w-32 py-1.5">{statusLabel(value?.status)}</td><td className="w-24 py-1.5">{value?.score === null || value?.score === undefined ? "—" : `${value.score}/5`}</td><td className="w-24 py-1.5"><button aria-label={`Раскрыть ${lesson.title}`} onClick={() => toggle(openLessons, setOpenLessons, lessonKey)}>{expanded ? "▾" : "▸"}</button></td></tr>
              {expanded && <tr><td colSpan={4} className="pb-3 text-zinc-600"><p>{lesson.function} · {lesson.skill} · {lesson.minutes} минут</p><p className="mt-1">{lesson.instruction}</p><button className={`${actionButton} mt-2`} onClick={() => onOpenLesson(lesson, Boolean(entry.example))}>{value?.status === "failed" && !entry.example ? "Пересдать" : "Открыть занятие"}</button></td></tr>}
            </tbody></table></td></tr>;
          })}</tbody></table></td></tr>}
        </tbody></table></td></tr>;
      })}
      {entries.length === 0 && <tr><td colSpan={5} className="px-4 py-4 text-zinc-500">Курсов пока нет.</td></tr>}
    </tbody></table></div>}
  </section>;
}

export function MyCoursesPanel({ catalog, progress, onChooseCourse, onOpenLesson, onOpenProgress }: {
  catalog: Catalog; progress: Progress; onChooseCourse: (code: string) => void; onOpenLesson: (lesson: Lesson, referenceOnly: boolean) => void; onOpenProgress: () => void;
}) {
  const showHireRoute = HIRE_ROUTE_LESSON_CODES.every(code => Boolean(progress.lessons[code]));
  const visibleCatalog = showHireRoute ? { ...catalog, lessons: catalog.lessons.filter(lesson => !HIRE_ROUTE_LESSON_CODES.includes(lesson.code)) } : catalog;
  const current: CourseProgress[] = (progress.courses?.length ? progress.courses : progress.course.total ? [progress.course] : [])
    .map((course) => ({ course, lessons: Object.fromEntries(Object.entries(progress.lessons).filter(([code]) => visibleCatalog.lessons.some((lesson) => lesson.code === code && lesson.course_code === course.code))) }))
    .filter(item => Object.keys(item.lessons).length > 0);
  const inProgress = current.filter((item) => item.course.passed !== item.course.total);
  const completed = [...current.filter((item) => item.course.passed === item.course.total), ...(progress.completed_courses ?? [])];
  return <div className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-2xl font-semibold">Мои курсы</h2><button className={actionButton} onClick={onOpenProgress}>Мой прогресс</button></div>
    {showHireRoute && <article className="rounded-xl border border-blue-200 bg-blue-50 p-5"><h3 className="text-xl font-semibold">Приём нового сотрудника на работу</h3><p className="mt-1 text-sm">Одна карточка с пятью этапами. Прежние результаты и оценки доступны в «Моём прогрессе».</p><a className="mt-3 inline-block rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white" href="/learning/hire-path?variant=single&step=1">Открыть маршрут</a></article>}
    {inProgress.length > 0 && <CourseTable title="Курсы в процессе" tint="blue" entries={inProgress} catalog={visibleCatalog} onOpenLesson={onOpenLesson} onChooseCourse={onChooseCourse} />}
    {completed.length > 0 && <CourseTable title="Пройденные курсы" tint="green" entries={completed} catalog={visibleCatalog} onOpenLesson={onOpenLesson} onChooseCourse={onChooseCourse} />}
  </div>;
}

type AttemptDetail = { id: string; attempt_no: number; status: string; score: number | null; required_met: boolean | null; review_note: string; review_source: string | null; auto_status: string; auto_note: string; pre_score: number | null; lesson?: Lesson; hire_application?: { application_id: number; status: string } | null; screenshots: Array<{ id: string }>; criteria_results: Record<string, boolean>; record: { application_ref: string; action: string } };

function SubmissionHistory({ participantId, lesson, preferredAttemptId }: { participantId: number; lesson: Lesson; preferredAttemptId?: string | null }) {
  const [items, setItems] = useState<Array<{ id: string; attempt_no: number; status: string; score: number | null; review_source: string | null }>>([]);
  const [chosen, setChosen] = useState<string | null>(null);
  const [detail, setDetail] = useState<AttemptDetail | null>(null);
  const [images, setImages] = useState<Array<{ id: string; src?: string }>>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    apiFetchJson<{ items: typeof items }>(`/learning/participants/${participantId}/lessons/${lesson.code}/attempts`)
      .then((value) => { setItems(value.items); setChosen(value.items.find((item) => item.id === preferredAttemptId)?.id ?? value.items[0]?.id ?? null); }).catch((e) => setError(e.message));
  }, [participantId, lesson.code, preferredAttemptId]);
  useEffect(() => {
    if (!chosen) return;
    let active = true;
    const urls: string[] = [];
    apiFetchJson<AttemptDetail>(`/learning/attempts/${chosen}`).then(async (value) => {
      const shots = await Promise.all(value.screenshots.map(async (shot) => {
        const response = await fetch(buildUrl(`/learning/screenshots/${shot.id}`), { headers: buildHeaders() });
        if (!response.ok) return { id: shot.id };
        const src = URL.createObjectURL(await response.blob()); urls.push(src); return { id: shot.id, src };
      }));
      if (active) { setDetail(value); setImages(shots); }
    }).catch((e) => { if (active) setError(e.message); });
    return () => { active = false; urls.forEach(URL.revokeObjectURL); };
  }, [chosen]);
  const attemptLesson = detail?.lesson ?? lesson;
  return <div className="space-y-3 rounded-lg border border-zinc-200 bg-white p-3">
    <h4 className="font-semibold">Детали сдачи · {lesson.title}</h4>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    <div className="flex flex-wrap gap-2">{items.map((item) => <button key={item.id} className={actionButton} aria-pressed={chosen === item.id} onClick={() => setChosen(item.id)}>Попытка {item.attempt_no} · {finalResultLabel(item.score, item.status, item.review_source)}</button>)}</div>
    {detail && detail.id === chosen && <>
      {detail.hire_application && <p>Кадровое заявление № {detail.hire_application.application_id} · статус {detail.hire_application.status}</p>}
      <p>Учебная запись: {detail.record.application_ref}</p>
      <p>Автоматическая проверка: {detail.auto_status === "complete" ? detail.auto_note || "выполнена" : detail.auto_status === "failed" ? "не удалось определить итог" : "недоступна"}</p>
      <p>Итоговая оценка: {finalResultLabel(detail.score, detail.status, detail.review_source)}</p>
      <div className="grid gap-3 sm:grid-cols-2">{attemptLesson.screenshots.map((label, index) => <div key={label} className="rounded border border-zinc-200 p-2"><p className="mb-2 font-medium">{label}</p>{images[index]?.src ? <Image src={images[index].src} alt={label} width={500} height={300} unoptimized className="max-h-40 w-auto object-contain" /> : <p className="text-zinc-500">Снимок недоступен в этом локальном запуске</p>}</div>)}</div>
      <div><p className="font-medium">Критерии</p><ul className="mt-1 space-y-1">{attemptLesson.criteria.map((criterion, index) => {
        const result = detail.criteria_results[index];
        const known = Object.hasOwn(detail.criteria_results, index) ? result : criterion === attemptLesson.required ? detail.required_met : null;
        return <li key={criterion}>{criterion}{criterion === attemptLesson.required ? " (обязательный)" : ""} · {known === null ? "не отмечен отдельно" : known ? "выполнен" : "не выполнен"}</li>;
      })}</ul></div>
      <p>Комментарий проверяющего: {detail.review_note || "Нет комментария"}</p>
    </>}
  </div>;
}

export function SummaryPanel({ catalog, selectedCourseCode, summary, viewerId, viewerName, onChooseCourse, onOpenLesson, onRetake }: {
  catalog: Catalog; selectedCourseCode: string; summary: Summary; viewerId: number | null; viewerName: string;
  onChooseCourse: (code: string) => void; onOpenLesson: (lesson: Lesson) => void; onRetake: (lesson: Lesson) => void;
}) {
  const [detailLesson, setDetailLesson] = useState<string | null>(null);
  const lessons = catalog.lessons.filter((lesson) => (summary.course.code === "all" || lesson.course_code === summary.course.code) && summary.lessons[lesson.code]);
  const shown = lessons.find((lesson) => lesson.code === detailLesson);
  const next = lessons.find((lesson) => ["draft", "failed", "not_started"].includes(summary.lessons[lesson.code]?.status)) ?? lessons.find((lesson) => summary.lessons[lesson.code]?.status === "manual_review");
  const nextState = next ? summary.lessons[next.code] : null;
  const nextLabel = nextState?.status === "draft" ? "Продолжить" : nextState?.status === "failed" ? "Пересдать" : nextState?.status === "manual_review" ? "Открыть попытку" : "Начать";
  const openHistory = (code: string) => setDetailLesson(detailLesson === code ? null : code);
  return <section className="space-y-4">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><h2 className="text-2xl font-semibold">Мой прогресс</h2><p className="mt-1 text-sm text-zinc-600">{viewerName}</p></div><label className="text-sm font-medium">Курс <select className="ml-2 rounded-md border border-zinc-300 bg-white px-3 py-2" value={selectedCourseCode} onChange={(e) => onChooseCourse(e.target.value)}><option value="all">Все назначения</option>{catalog.courses.map((item) => <option key={item.code} value={item.code}>{item.title}</option>)}</select></label></div>
    <div className="grid gap-3 sm:grid-cols-3">{[["Очки", summary.course.points], ["Зачтено занятий", `${summary.course.passed} из ${summary.course.total}`], ["На проверке", summary.course.pending]].map(([label, value]) => <div key={label} className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-4"><p className="text-sm text-blue-900">{label}</p><p className="mt-1 text-3xl font-semibold text-blue-950">{value}</p></div>)}</div>
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-200 bg-zinc-50 px-4 py-3"><p className="text-sm"><span className="font-semibold">Ближайшее действие:</span> {next ? next.title : "Все занятия зачтены"}</p>{next && <button className={actionButton} onClick={() => nextState?.status === "manual_review" ? openHistory(next.code) : nextState?.status === "failed" ? onRetake(next) : onOpenLesson(next)}>{nextLabel}</button>}</div>
    <div className={section}><table className="w-full text-sm"><thead><tr className="border-b border-zinc-200 bg-zinc-50 text-left"><th className="px-4 py-3">Занятие</th><th className="px-3 py-3">Статус</th><th className="px-3 py-3">Оценка</th><th className="px-4 py-3">Действия</th></tr></thead><tbody>{lessons.map((lesson) => {
      const value = summary.lessons[lesson.code];
      const action = value?.status === "not_started" ? "Начать" : value?.status === "draft" ? "Продолжить" : value?.status === "manual_review" ? "Открыть попытку" : value?.status === "failed" ? "Пересдать" : "Посмотреть результат";
      return <tr key={lesson.code} className="border-t border-zinc-200"><td className="px-4 py-3">{lesson.title}</td><td className="px-3 py-3">{statusLabel(value?.status)}</td><td className="px-3 py-3">{finalResultLabel(value?.score, value?.status, value?.review_source)}</td><td className="space-x-3 px-4 py-3"><button className="text-blue-700 underline" onClick={() => action === "Начать" || action === "Продолжить" ? onOpenLesson(lesson) : action === "Пересдать" ? onRetake(lesson) : openHistory(lesson.code)}>{action}</button>{value?.status === "passed" && <button className="text-blue-700 underline" onClick={() => onRetake(lesson)}>Пересдать</button>}{value?.result_attempt_id && value?.status !== "passed" && <button className="text-blue-700 underline" onClick={() => openHistory(lesson.code)}>История результатов</button>}</td></tr>;
    })}</tbody></table></div>
    {shown && viewerId !== null && <SubmissionHistory key={shown.code} participantId={viewerId} lesson={shown} preferredAttemptId={summary.lessons[shown.code]?.result_attempt_id} />}
  </section>;
}
