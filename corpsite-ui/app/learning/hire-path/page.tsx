"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Image from "next/image";
import { apiFetchJson, buildHeaders, buildUrl, readJsonSafe, toApiError } from "@/lib/api";
import PersonnelOrderDocumentView from "@/app/directory/personnel/_components/PersonnelOrderDocumentView";
import type { PersonnelOrderDetailResponse, PersonnelOrderEditorialState } from "@/app/directory/personnel/_lib/personnelOrdersApi.client";

const CODES: Record<number, string> = {
  1: "lesson_5b2e5028ea63",
  2: "hire_path_02_personal_card",
  3: "hire_path_03_order_draft",
  4: "hire_path_04_sign_register",
  5: "hire_path_05_notify_ack",
};
const TITLES: Record<number, string> = {
  1: "Создать электронное заявление",
  2: "Запросить заполнение личной карточки",
  3: "Подготовить проект приказа о приёме",
  4: "Подписать и зарегистрировать приказ",
  5: "Уведомить сотрудника и зафиксировать ознакомление",
};
type Root = { root_attempt_id: string; application_id: number; attempt_no: number };
type Step = { step: number; attempt_id: string; status: string; attempt_no: number; score: number | null; review_source: string | null };
type SourceAttempt = { attempt_id: string; attempt_no: number; attempt_status: string; application: { application_id: number; status: string } | null };
type PathState = {
  application_id: number; application_status: string; person_id: number;
  source_attempt: { status: string; score: number | null; review_source: string | null };
  intake_link: { status: string; url_path: string | null; expires_at: string | null };
  personal_card: { complete: boolean; missing_fields: string[]; candidate_checked_at: string | null; intake_link_status: string | null; intake_draft_status: string | null };
  order_draft: { order_id: number; status: string; number: string | null; date: string | null } | null;
  steps: Step[]; messages: Array<{ kind: string; at: string }>;
  candidate_login: string | null; employee_id: number | null; signed_at: string | null;
  acknowledgement: { method: string; evidence: string; at: string } | null;
  numbering?: { year: number; last_registered_number: string | null; last_registered_date: string | null; suggested_number: string; current_number: string | null };
  start_requirements: Record<string, { ready: boolean; reason: string | null; return_to_step: number | null; requires_submission: boolean; requires_pass: boolean }>;
};
type Review = { sections: Array<{ code: string; status: string }>; can_transfer: boolean; blocked_reason: string | null; draft_status: string; payload: Record<string, unknown> };
type OrderPack = { detail: PersonnelOrderDetailResponse; editorial: PersonnelOrderEditorialState };
type Lesson = { code: string; task: string; screenshots: string[]; guide_url?: string | null };

function stageStatus(value?: string) {
  return ({ passed: "Зачтено", manual_review: "На проверке", draft: "В работе", failed: "Требует пересдачи" } as Record<string, string>)[value ?? ""] ?? "Не начато";
}

function routeHref(step: number, sourceId?: string) {
  const query = new URLSearchParams({ variant: "single", step: String(step) });
  if (sourceId) query.set("application", sourceId);
  return `/learning/hire-path?${query.toString()}`;
}

const action = "rounded border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100";
const card = "rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-700 dark:bg-zinc-900";

export default function HirePathPage() {
  const [single, setSingle] = useState(true);
  const [loading, setLoading] = useState(true);
  const [roots, setRoots] = useState<Root[]>([]);
  const [rootId, setRootId] = useState("");
  const [sourceAttemptId, setSourceAttemptId] = useState("");
  const [sourceAttempt, setSourceAttempt] = useState<SourceAttempt | null>(null);
  const [origin, setOrigin] = useState("");
  const [step, setStep] = useState(2);
  const [state, setState] = useState<PathState | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [order, setOrder] = useState<OrderPack | null>(null);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [number, setNumber] = useState("");
  const numberInputRef = useRef<HTMLInputElement>(null);
  const [locale, setLocale] = useState<"ru" | "kk">("ru");
  const [bodyText, setBodyText] = useState<Record<"ru" | "kk", string>>({ ru: "", kk: "" });
  const bodyInputRef = useRef<HTMLTextAreaElement>(null);
  const [savedShots, setSavedShots] = useState<Array<{ id: string; slot: number | null; url: string | null }>>([]);
  const [shotsLoading, setShotsLoading] = useState(false);
  const [uploadingSlot, setUploadingSlot] = useState<number | null>(null);
  const [shotRevision, setShotRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const refresh = useCallback(async (id: string) => {
    if (!id) return;
    const next = await apiFetchJson<PathState>(`/learning/hire-path/${id}`);
    setState(next);
    setSourceAttemptId(id);
    setSourceAttempt(await apiFetchJson<SourceAttempt>(`/learning/attempts/${id}/hire-application`));
    if (document.activeElement !== numberInputRef.current) {
      setNumber(next.numbering?.current_number || next.numbering?.suggested_number || "");
    }
    if (next.order_draft) {
      try {
        const pack = await apiFetchJson<OrderPack>(`/learning/hire-path/${id}/order`);
        setOrder(pack);
        const body = (language: "ru" | "kk") => pack.editorial.items.flatMap(item => item.blocks)
          .find(block => block.locale === language && block.block_type === "body");
        if (document.activeElement !== bodyInputRef.current) {
          setBodyText({ ru: body("ru")?.effective_text || "", kk: body("kk")?.effective_text || "" });
        }
      }
      catch { setOrder(null); }
    } else setOrder(null);
  }, []);

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const isSingle = true;
    const requested = Number(query.get("step"));
    const requestedSource = query.get("application") || "";
    setSingle(isSingle);
    setOrigin(window.location.origin);
    if (requested >= (isSingle ? 1 : 2) && requested <= 5) setStep(requested);
    else if (isSingle) setStep(1);
    void Promise.all([
      apiFetchJson<{ items: Root[] }>("/learning/hire-path/roots"),
      apiFetchJson<{ lessons: Lesson[] }>("/learning/catalog"),
    ]).then(async ([list, catalog]) => {
      setRoots(list.items); setLessons(catalog.lessons);
      if (requestedSource) {
        if (list.items.some(item => item.root_attempt_id === requestedSource)) setRootId(requestedSource);
        else {
          const source = await apiFetchJson<SourceAttempt>(`/learning/attempts/${requestedSource}/hire-application`);
          setSourceAttemptId(requestedSource); setSourceAttempt(source);
        }
      } else if (list.items.length) {
        setRootId(list.items[0].root_attempt_id);
        if (isSingle) window.history.replaceState(null, "", routeHref(requested >= 1 && requested <= 5 ? requested : 1, list.items[0].root_attempt_id));
      }
    }).catch(error => setMessage(error instanceof Error ? error.message : "Не удалось открыть учебный маршрут"))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { void refresh(rootId).catch(error => setMessage(error instanceof Error ? error.message : "Не удалось загрузить заявление")); }, [rootId, refresh]);

  const attempt = step === 1
    ? sourceAttemptId && sourceAttempt ? { attempt_id: sourceAttemptId, status: state?.source_attempt.status ?? sourceAttempt.attempt_status } : undefined
    : state ? [...state.steps].reverse().find(item => item.step === step) : undefined;
  const attemptId = attempt?.attempt_id || "";
  const shotLabels = lessons.find(item => item.code === CODES[step])?.screenshots || [];
  const candidateUrl = state?.intake_link.url_path && origin ? new URL(state.intake_link.url_path, origin).toString() : null;
  const isLocalOrigin = origin ? ["localhost", "127.0.0.1"].includes(new URL(origin).hostname) : false;
  useEffect(() => {
    let active = true;
    const urls: string[] = [];
    setSavedShots([]);
    setShotsLoading(Boolean(attemptId));
    if (attemptId) {
      void (async () => {
        const detail = await apiFetchJson<{ screenshots: Array<{ id: string; slot: number | null }> }>(`/learning/attempts/${attemptId}`);
        const shots = await Promise.all(detail.screenshots.map(async shot => {
          const response = await fetch(buildUrl(`/learning/screenshots/${shot.id}`), { headers: buildHeaders() });
          if (!response.ok) return { ...shot, url: null };
          const url = URL.createObjectURL(await response.blob());
          urls.push(url);
          return { ...shot, url };
        }));
        if (active) setSavedShots(shots);
      })().catch(error => { if (active) setMessage(error instanceof Error ? error.message : "Не удалось загрузить сохранённые снимки"); })
        .finally(() => { if (active) setShotsLoading(false); });
    }
    return () => { active = false; urls.forEach(url => URL.revokeObjectURL(url)); };
  }, [attemptId, shotRevision]);
  async function reloadSelected() {
    const list = await apiFetchJson<{ items: Root[] }>("/learning/hire-path/roots");
    setRoots(list.items);
    if (sourceAttemptId && list.items.some(item => item.root_attempt_id === sourceAttemptId)) {
      setRootId(sourceAttemptId);
      await refresh(sourceAttemptId);
    } else if (sourceAttemptId) {
      setSourceAttempt(await apiFetchJson<SourceAttempt>(`/learning/attempts/${sourceAttemptId}/hire-application`));
    }
  }
  async function startFirst() {
    const first = lessons.find(item => item.code === CODES[1]);
    if (!first) { setMessage("Первое занятие не назначено"); return; }
    setBusy(true); setMessage("");
    try {
      const result = await apiFetchJson<{ id: string }>(`/learning/lessons/${first.code}/hire-attempts`, { method: "POST" });
      window.location.assign(routeHref(1, result.id));
    } catch (error) { setMessage(error instanceof Error ? error.message : "Не удалось начать заявление"); setBusy(false); }
  }
  async function copyLink() {
    if (!candidateUrl) return;
    try { await navigator.clipboard.writeText(candidateUrl); setMessage("Ссылка на анкету скопирована."); }
    catch { setMessage("Не удалось скопировать автоматически. Выделите ссылку и скопируйте её вручную."); }
  }
  async function post(path: string, body?: unknown) {
    if (!rootId) return;
    setBusy(true); setMessage("");
    try {
      await apiFetchJson(`/learning/hire-path/${rootId}/${path}`, { method: "POST", ...(body === undefined ? {} : { body }) });
      await refresh(rootId);
      setMessage("Действие выполнено. Проверьте обновлённое состояние ниже.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Действие не выполнено"); }
    finally { setBusy(false); }
  }
  async function start(n: number) {
    setStep(n);
    await post(`steps/${CODES[n]}`);
  }
  async function loadReview() {
    if (!rootId) return;
    try { setReview(await apiFetchJson<Review>(`/learning/hire-path/${rootId}/review`)); await refresh(rootId); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Анкета ещё не отправлена"); }
  }
  async function decide(section: string, decision: "accept" | "skip") {
    await post(`review/${section}`, { decision });
    await loadReview();
  }
  async function uploadScreenshot(slot: number, file?: File) {
    if (!attempt || !file) return;
    setBusy(true); setUploadingSlot(slot); setMessage("");
    try {
      const prior = savedShots.find(item => item.slot === slot);
      if (prior) await apiFetchJson(`/learning/screenshots/${prior.id}`, { method: "DELETE" });
      const form = new FormData(); form.set("file", file); form.set("slot", String(slot));
      const response = await fetch(buildUrl(`/learning/attempts/${attempt.attempt_id}/screenshots`),
        { method: "POST", headers: buildHeaders(), body: form });
      if (!response.ok) throw toApiError(response.status, await readJsonSafe(response));
      setMessage(`Снимок ${slot + 1} сохранён в черновике. Он останется после обновления страницы.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Не удалось сохранить снимок"); }
    finally { setShotRevision(value => value + 1); setUploadingSlot(null); setBusy(false); }
  }
  async function submitEvidence() {
    if (!attempt || !shotLabels.length || shotLabels.some((_, slot) => !savedShots.some(item => item.slot === slot))) return;
    if (step === 1 && !rootId) { setMessage("Сначала сохраните заявление в кадровой форме и обновите данные этапа."); return; }
    setBusy(true); setMessage("");
    try {
      const detail = await apiFetchJson<{ screenshots: { slot: number | null }[] }>(`/learning/attempts/${attempt.attempt_id}`);
      const savedSlots = new Set(detail.screenshots.map(item => item.slot));
      if (shotLabels.some((_, slot) => !savedSlots.has(slot))) throw new Error("Сначала сохраните все снимки в черновике.");
      await apiFetchJson(`/learning/attempts/${attempt.attempt_id}/submit`, { method: "POST" });
      await refresh(rootId);
      setMessage("Снимки отправлены на проверку учебного занятия.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Не удалось отправить снимки"); }
    finally { setBusy(false); }
  }
  const evidencePanel = attempt && shotLabels.length > 0 && (step !== 1 || Boolean(rootId)) &&
    <section className={`${card} print:hidden`}><h3 className="text-lg font-semibold">Выполнение задач обучения</h3>
      <h4 className="mt-3 font-semibold">Снимки для проверки</h4>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-300">Снимок сохраняется в попытке сразу после выбора файла. После обновления страницы он доступен в предпросмотре.</p>
      {attempt.status !== "draft" && <p className="mt-2 rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">Снимки переданы на проверку</p>}
      {shotLabels.map((label, slot) => {
        const saved = savedShots.find(item => item.slot === slot);
        return <div key={slot} className="mt-3 rounded border border-zinc-200 p-3 dark:border-zinc-700">
          <p className="text-sm font-medium">Снимок {slot + 1}: {label}</p>
          {uploadingSlot === slot
            ? <p className="mt-1 text-sm" role="status">Файл проверяется и сохраняется. Это может занять до минуты; дождитесь результата.</p>
            : saved ? <p className="mt-1 text-sm text-emerald-700 dark:text-emerald-300">Сохранён в попытке</p> : <p className="mt-1 text-sm">Ещё не сохранён</p>}
          {saved?.url && <Image src={saved.url} width={640} height={400} alt={`Предпросмотр сохранённого снимка ${slot + 1}`} unoptimized className="mt-2 max-h-72 w-auto rounded border object-contain" />}
          {saved && !saved.url && <p className="mt-1 text-sm text-amber-700">Не удалось открыть предпросмотр. Обновите страницу.</p>}
          {attempt.status === "draft" && <label className="mt-2 block text-sm">{saved ? "Заменить снимок" : "Загрузить снимок"}<input className="mt-1 block" type="file" accept="image/png,image/jpeg" disabled={busy || shotsLoading} onChange={event => { void uploadScreenshot(slot, event.target.files?.[0]); event.target.value = ""; }} /></label>}
        </div>;
      })}
      {attempt.status === "draft" && <button className={`${action} mt-4`} disabled={busy || shotsLoading || shotLabels.some((_, slot) => !savedShots.some(item => item.slot === slot))} onClick={() => void submitEvidence()}>{step === 1 ? "Сдать этап 1" : single ? "Отправить этап на проверку" : "Отправить занятие на проверку"}</button>}
    </section>;

  return <main className="hire-path-print-root min-h-screen bg-zinc-50 px-4 py-8 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
    <div className="mx-auto max-w-5xl space-y-5">
      <header className={card}><a href={single ? "/training" : "/learning"} className="text-sm text-blue-700 underline dark:text-blue-300">← К занятиям</a>
        <h1 className="mt-2 text-2xl font-semibold">{single ? "Приём нового сотрудника на работу" : "Учебный маршрут приёма сотрудника"}</h1>
        <p className="mt-1 text-sm">{single ? "Одна карточка с пятью этапами. Все этапы связаны с одним учебным заявлением." : "Выберите заявление из занятия 1."} Все действия выполняются только с вымышленными данными учебного стенда.</p>
        <p className="mt-2 text-sm"><a href="/learning/hire-path/guide" target="_blank" rel="noopener noreferrer" className="text-blue-700 underline dark:text-blue-300">Единое руководство по пяти этапам</a></p>
      </header>
      {message && <p role="status" className="rounded border border-blue-200 bg-blue-50 p-3 text-sm dark:border-blue-900 dark:bg-blue-950">{message}</p>}
      <section className={card}><label className="text-sm font-medium">Заявление из этапа 1
        <select className="mt-1 block w-full rounded border p-2 dark:bg-zinc-800" value={rootId} onChange={event => { if (single) window.location.assign(routeHref(step, event.target.value)); else { setRootId(event.target.value); setReview(null); } }}>
          {!rootId && <option value="">{sourceAttemptId ? "Новое заявление ещё не сохранено" : "Выберите заявление"}</option>}
          {roots.map(root => <option key={root.root_attempt_id} value={root.root_attempt_id}>Заявление № {root.application_id} · попытка {root.attempt_no}</option>)}
        </select></label>{!roots.length && !single && <p className="mt-2 text-sm">Сначала сохраните новое учебное заявление в занятии 1.</p>}</section>
      {single && loading && <p className={card}>Загружаем выбранное заявление и этапы…</p>}
      {single && !loading && <nav className={`${card} space-y-2`} aria-label="Пять этапов маршрута">
        <p className="font-semibold">Текущий этап: {step} из 5 · {TITLES[step]}</p>
        <ol className="space-y-2">{[1,2,3,4,5].map(n => {
          const current = n === 1 ? (state?.source_attempt ?? (sourceAttempt ? { status: sourceAttempt.attempt_status, score: null } : undefined)) : [...(state?.steps ?? [])].reverse().find(item => item.step === n);
          return <li key={n} className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded border border-zinc-200 p-2 dark:border-zinc-700">
            <a href={routeHref(n, rootId || sourceAttemptId)} aria-current={step === n ? "step" : undefined} className="font-medium text-blue-700 underline dark:text-blue-300">{n}. {TITLES[n]}</a>
            <span className="text-sm text-zinc-600 dark:text-zinc-300">{stageStatus(current?.status)}{current?.score !== null && current?.score !== undefined ? ` · ${current.score}/5` : ""}</span>
          </li>;
        })}</ol>
      </nav>}
      {single && !loading && <section className={card}>
        <h2 className="text-xl font-semibold">Этап {step}. {TITLES[step]}</h2>
        <div className="mt-3 flex flex-wrap gap-3 text-sm">
          {step > 1 && <a href={routeHref(step - 1, rootId || sourceAttemptId)} className="text-blue-700 underline dark:text-blue-300">← Предыдущий этап</a>}
          {step < 5 && <a href={routeHref(step + 1, rootId || sourceAttemptId)} className="text-blue-700 underline dark:text-blue-300">Следующий этап →</a>}
        </div>
        <h3 className="mt-5 font-semibold">Что сделать</h3>
        <p className="mt-1 text-sm">{lessons.find(item => item.code === CODES[step])?.task || TITLES[step]}</p>
        <h3 className="mt-4 font-semibold">Что приложить для проверки</h3>
        <ol className="mt-1 list-decimal space-y-2 pl-5 text-sm">{shotLabels.map((label, index) => <li key={index}>{step === 2 && index === 0
          ? "Сделайте скриншот окна заявления после выдачи ссылки кандидату и загрузите его сюда. На снимке должно быть видно, что ссылка выдана. Саму ссылку закройте."
          : step === 2 && index === 1
          ? "После проверки анкеты сделайте скриншот заполненной карточки со статусом проверки кадровиком и загрузите его сюда."
          : `Сделайте скриншот: ${label}. Загрузите его в поле ниже.`}</li>)}</ol>
      </section>}
      {single && step === 1 && <section className={card}>
        <h3 className="text-lg font-semibold">Заявление</h3>
        <p className="mt-2 text-sm">{state ? `Заявление № ${state.application_id} · ${state.application_status}` : sourceAttempt?.application ? `Заявление № ${sourceAttempt.application.application_id} сохранено` : "Начните новую попытку и сохраните заявление в кадровой форме."}</p>
        <p className="mt-1 text-sm">Статус попытки: {stageStatus(attempt?.status)}</p>
        <div className="mt-3 flex flex-wrap gap-2"><button className={action} disabled={busy || loading} onClick={() => void startFirst()}>Начать новое заявление</button>
          {sourceAttemptId && <a className={action} href={`/learning/hire/${sourceAttemptId}`} target="_blank" rel="noopener noreferrer">Открыть кадровую форму</a>}
          {sourceAttemptId && <button className={action} onClick={() => void reloadSelected()}>Обновить данные заявления</button>}</div>
        {sourceAttemptId && attempt?.status === "draft" && <div className="mt-4 space-y-2"><p className="text-sm text-zinc-600 dark:text-zinc-300">Сохраните заявление в форме ниже и нажмите «Обновить данные заявления». При необходимости откройте форму в отдельной вкладке.</p>
          <iframe title="Кадровая форма учебного заявления" src={`/learning/hire/${sourceAttemptId}?embedded=1`} className="h-[800px] w-full rounded border border-zinc-300 bg-white dark:border-zinc-700" /></div>}
      </section>}
      {single && step === 1 && evidencePanel}
      {state && step >= 2 && <>
        {!single && <nav className="flex flex-wrap gap-2" aria-label="Занятия маршрута">{[2,3,4,5].map(n => <button key={n} className={action} onClick={() => setStep(n)}>{n}. {TITLES[n]}</button>)}</nav>}
        <section className={card}><h3 className="text-lg font-semibold">Рабочее действие</h3>
          <p className="mt-1 text-sm">Заявление № {state.application_id} · запись кандидата № {state.person_id} · статус {state.application_status}</p>
          <div className="mt-3 flex flex-wrap gap-2"><button className={action} disabled={busy || state.start_requirements?.[String(step)]?.ready === false} onClick={() => void start(step)}>{attempt ? "Продолжить попытку" : "Начать попытку"}</button><button className={action} onClick={() => void refresh(rootId)}>Обновить данные</button></div>
          <p className="mt-2 text-sm">Попытка: {attempt ? `${attempt.status} · ${attempt.attempt_id}` : "ещё не начата"}</p>{state.start_requirements?.[String(step)]?.ready === false && <p className="mt-2 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
            Начать пока нельзя: {state.start_requirements[String(step)].reason} {state.start_requirements[String(step)].return_to_step && <a className="text-blue-700 underline" href={routeHref(state.start_requirements[String(step)].return_to_step!, rootId)}>Вернуться к этапу {state.start_requirements[String(step)].return_to_step}</a>}
          </p>}
          {step > 1 && <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-300">Для перехода нужен сохранённый результат предыдущего кадрового действия. Отправка снимков на проверку и зачёт предыдущего этапа не обязательны.</p>}
        </section>
        {step === 2 && <section className={card}><h3 className="text-lg font-semibold">Личная карточка</h3>
          <p>Кандидат открывает бланк по ссылке без входа в личный кабинет сотрудника. Скопируйте адрес и передайте его вручную.</p>
          {state.intake_link.status === "submitted" ? <p className="mt-2 rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">Анкета отправлена. Прежнюю ссылку можно снова скопировать; кандидат увидит подтверждение отправки без возможности редактирования.</p>
            : <p>Ссылка: {state.personal_card.intake_link_status || "не выдана"} · анкета: {state.personal_card.intake_draft_status || "не заполнена"}</p>}
          {candidateUrl && <div className="mt-3 rounded border border-blue-200 bg-blue-50 p-3 text-sm text-blue-950 dark:bg-blue-950 dark:text-blue-100"><p className="font-semibold">Ссылка на бланк личной карточки кандидата</p>
            <input aria-label="Ссылка на анкету кандидата" className="mt-2 w-full rounded border bg-white p-2 text-zinc-900" readOnly value={candidateUrl} onFocus={event => event.target.select()} />
            <div className="mt-2 flex flex-wrap gap-3"><button className={action} onClick={() => void copyLink()}>Скопировать ссылку кандидата</button><a href={candidateUrl} target="_blank" rel="noopener noreferrer" className="self-center text-blue-700 underline dark:text-blue-300">Проверить ссылку глазами кандидата</a></div>
            {isLocalOrigin && <p className="mt-2 text-amber-800 dark:text-amber-200">Адрес 127.0.0.1 работает только на этом компьютере. Для телефона откройте учебный стенд через его публичный HTTPS-адрес и скопируйте ссылку там.</p>}
            {state.intake_link.status === "active" && state.intake_link.expires_at && <p className="mt-1">Действует до {new Date(state.intake_link.expires_at).toLocaleString("ru-RU")}.</p>}</div>}
          <p>Карточка: {state.personal_card.complete ? "обязательные поля заполнены" : `не хватает: ${state.personal_card.missing_fields.join(", ")}`}</p>
          <p>Проверка кадровика: {state.personal_card.candidate_checked_at || "не выполнена"}</p>
          <div className="mt-3 flex flex-wrap gap-2">{!candidateUrl && state.intake_link.status !== "submitted" && <button className={action} disabled={busy || !attempt} onClick={() => void post("intake-link")}>Выдать ссылку кандидату</button>}
            <button className={action} disabled={!attempt || Boolean(state.personal_card.candidate_checked_at)} onClick={() => void loadReview()}>Открыть проверку анкеты</button></div>
          {review && <div className="mt-4 space-y-3"><p>Статус анкеты: {review.draft_status}</p>
            {review.sections.map(item => <details key={item.code} className="rounded border p-3"><summary>{item.code} · {item.status}</summary>
              <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(review.payload[item.code], null, 2)}</pre>
              <div className="mt-2 flex gap-2"><button className={action} onClick={() => void decide(item.code, "accept")}>Принять раздел</button><button className={action} onClick={() => void decide(item.code, "skip")}>Пропустить пустой</button></div>
            </details>)}<p>{review.can_transfer ? "Все разделы проверены" : review.blocked_reason}</p>
            <button className={action} disabled={!review.can_transfer || busy} onClick={() => void post("transfer")}>Перенести данные в личную карточку</button></div>}
          <button className={`${action} mt-3`} disabled={!state.personal_card.complete || busy} onClick={() => void post("check-card")}>Подтвердить проверку карточки</button>
        </section>}
        {step === 3 && <section className={card}><h3 className="text-lg font-semibold">Проект приказа</h3>
          <p>Связанное заявление № {state.application_id}; проект: {state.order_draft ? `№ ${state.order_draft.order_id}, ${state.order_draft.status}` : "ещё не создан"}.</p>
          <div className="mt-3 flex flex-wrap gap-2"><button className={action} disabled={!attempt || busy} onClick={() => void post("order-draft")}>Создать связанный проект</button>
            <button className={action} disabled={!state.order_draft || busy} onClick={() => void post("generate")}>Сформировать RU/KK текст</button></div>
          {order && state.order_draft?.status === "DRAFT" && <div className="mt-4 space-y-2"><label className="block text-sm">Пункт приказа ({locale === "ru" ? "русский" : "казахский"})
            <textarea ref={bodyInputRef} className="mt-1 min-h-32 w-full rounded border p-2 dark:bg-zinc-800" value={bodyText[locale]} onChange={event => setBodyText(previous => ({ ...previous, [locale]: event.target.value }))} /></label>
            <button className={action} disabled={busy || !bodyText[locale].trim()} onClick={() => void post("editorial-body", { locale, text: bodyInputRef.current?.value ?? bodyText[locale] })}>Сохранить исправленный текст</button></div>}
        </section>}
        {step === 4 && <section className={card}><h3 className="text-lg font-semibold">Номер, подпись и регистрация</h3>
          <p>Последний зарегистрированный номер за {state.numbering?.year || "—"} год: {state.numbering?.last_registered_number || "нет"}; предложен: {state.numbering?.suggested_number || "—"}.</p>
          <p>Статус приказа: {state.order_draft?.status || "проект ещё не создан"}. Номер: {state.order_draft?.number || "—"}; дата: {state.order_draft?.date || "—"}.</p>
          <label className="mt-2 block text-sm">Номер приказа<input ref={numberInputRef} className="mt-1 block w-48 rounded border p-2 dark:bg-zinc-800" value={number} onChange={e => setNumber(e.target.value)} /></label>
          <div className="mt-3 flex flex-wrap gap-2"><button className={action} disabled={!attempt || state.order_draft?.status !== "DRAFT" || busy} onClick={() => void post("number", { number: numberInputRef.current?.value ?? number })}>Закрепить номер</button>
            <button className={action} disabled={!attempt || state.order_draft?.status !== "DRAFT" || !state.numbering?.current_number || busy} onClick={() => void post("ready")}>Подготовить к подписи</button>
            <button className={action} disabled={state.order_draft?.status !== "SIGNED" || !state.signed_at || busy} onClick={() => void post("register")}>Зарегистрировать подписанный приказ</button></div>
          <p className="mt-2 text-sm">Подпись: {state.signed_at || "ожидается"}. Подписант выполняет своё действие в отдельном учебном кабинете.</p>
        </section>}
        {step === 5 && <section className={card}><h3 className="text-lg font-semibold">Уведомление и ознакомление</h3>
          <p>Зарегистрированный приказ № {state.order_draft?.number || "—"}; учебная запись сотрудника: {state.employee_id || "ещё не создана"}.</p>
          <div className="mt-3 flex flex-wrap gap-2"><button className={action} disabled={!attempt || busy} onClick={() => void post("apply")}>Применить приказ и создать сотрудника</button>
            <button className={action} disabled={!state.employee_id || busy} onClick={() => void post("notify")}>Уведомить через учебный кабинет</button></div>
          <ul className="mt-3 list-disc pl-5 text-sm">{state.messages.map((item, i) => <li key={i}>{item.kind === "intake_link" ? "Ссылка кандидату" : "Уведомление о приказе"} · {item.at}</li>)}</ul>
          <p className="mt-2">Ознакомление: {state.acknowledgement ? `${state.acknowledgement.at}, ${state.acknowledgement.method}` : "ожидается"}</p>
        </section>}
        {order && <section className={`${card} print-document`}><div className="flex flex-wrap gap-2 print:hidden"><button className={action} onClick={() => setLocale("ru")}>Русский</button><button className={action} onClick={() => setLocale("kk")}>Қазақша</button><button className={action} onClick={() => window.print()}>Печать текущей версии</button></div>
          <div className="mt-4"><PersonnelOrderDocumentView detail={order.detail} editorial={order.editorial} language={locale} /></div></section>}
        {evidencePanel}
      </>}
    </div>
    <style>{`@media print {
      body { background: white !important; }
      body:has(main.hire-path-print-root) > main > div { min-height: auto !important; }
      body:has(main.hire-path-print-root) > main > div > div { padding: 0 !important; }
      body:has(main.hire-path-print-root) > main > div > div > :not(.grid) { display: none !important; }
      main.hire-path-print-root { min-height: auto !important; padding: 0 !important; background: white !important; }
      main.hire-path-print-root > div { max-width: none !important; margin: 0 !important; }
      main.hire-path-print-root > div > :not(.print-document) { display: none !important; }
      .print-document, .print-document article { border: 0 !important; box-shadow: none !important; padding: 0 !important; max-width: none !important; }
    }`}</style>
  </main>;
}
