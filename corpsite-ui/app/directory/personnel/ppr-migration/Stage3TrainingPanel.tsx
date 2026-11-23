"use client";

import { useEffect, useRef, useState } from "react";

import { apiFetchJson } from "@/lib/api";

type Values = Record<string, unknown>;
type Preview = { stage0_cohort_run_id: number; preview_fingerprint: string; participant_count: number };
type Fragment = { fragment_index: number; source: Values; current: Values; proposal: Values; outcome: string; reason_code: string };
type Participant = { stage_run_participant_id: number; position: number; employee_id: number; person_id?: number; status: string; fragments: Fragment[]; error_code?: string | null };
type Run = { run: { stage_run_id: number; stage0_cohort_run_id?: number; status: string; current_position: number; paused_operation?: string | null; stopped_participant_id?: number | null }; participants: Participant[]; counts: Record<string, number> };
type Summary = { stage_run_id: number; employee_count: number; records_by_kind: Record<string, number>; skipped_count: number; acceptance_fingerprint: string };

const BASE = "/personnel/ppr-migration/stage-3/training";
const labels: Record<string, string> = {
  DRY_RUN_COMPLETED: "Проверка завершена", APPROVED: "Утверждён к запуску", RUNNING: "Выполняется",
  PAUSED_ON_ERROR: "Остановлен из-за ошибки", COMPLETED_PENDING_REVIEW: "Готов к принятию",
  ACCEPTED: "Этап принят", CANCELLED: "Отменён", PENDING: "Ожидает обработки",
  COMPLETED: "Черновик PMF подготовлен", ERROR: "Требуется исправление",
  SKIPPED_BY_DECISION: "Исключён по решению", READY_TO_ADD: "Будет добавлено",
  ALREADY_APPLIED: "Уже записано", DUPLICATE_IN_RUN: "Дубликат в запуске",
  REVIEW_REQUIRED: "Требуется ручное решение", CANONICAL_CONFLICT: "Конфликт с карточкой",
};
const errors: Record<string, string> = {
  STAGE3_PREVIEW_DISABLED: "Предварительная проверка Stage 3 отключена feature flag.",
  STAGE3_EXECUTION_DISABLED: "Выполнение Stage 3 отключено feature flag.",
  STAGE3_ACCEPT_DISABLED: "Принятие Stage 3 отключено feature flag.",
  STAGE3_COHORT_OUT_OF_SCOPE: "Запуск недоступен в вашей организационной области.",
  STAGE3_SCOPE_UNRESOLVED: "Не удалось безопасно определить организационную область доступа.",
  STAGE3_PREVIEW_STALE: "Исходные данные изменились. Выполните новую предварительную проверку.",
  STAGE3_RESUME_STALE: "Данные участника изменились. Выполните новую предварительную проверку.",
  STAGE3_ACCEPTANCE_STALE: "Данные изменились перед принятием. Нужны новый preview и повторная проверка.",
  STAGE3_ACCEPTANCE_APPROVAL_STALE: "После утверждения изменились решения HR. Требуется повторное утверждение.",
  STAGE3_APPROVAL_BLOCKED: "Утверждение заблокировано: есть предложения, требующие ручного решения.",
  STAGE3_ACCEPTANCE_PAUSED: "Принятие остановлено. Проверьте причину и повторите принятие.",
  STAGE3_SKIP_NOT_ALLOWED: "Исключение этого участника недоступно в текущем состоянии запуска.",
  STAGE3_INVALID_STATE: "Действие недоступно в текущем состоянии запуска. Обновите запуск и следуйте его статусу.",
  STAGE3_ACCEPTANCE_NOT_READY: "Принятие пока недоступно: завершите обработку участников или устраните остановку.",
  STAGE3_FRAGMENT_REVIEW_REQUIRED: "Есть фрагменты, требующие ручного решения. Исправьте источник или исключите участника.",
};

function errorMessage(error: unknown): string {
  const value = error as { status?: number; details?: { code?: unknown; message?: unknown; detail?: { code?: unknown; message?: unknown } }; message?: unknown };
  if (value?.status === 403) return "Нет права Stage 3 или доступа к организационной области.";
  const detail = value?.details?.detail ?? value?.details;
  const code = String(detail?.code ?? "");
  return errors[code] ?? String(detail?.message ?? value?.message ?? "Не удалось выполнить действие.");
}
function field(values: Values, name: string, fallback = "—"): string { const value = values[name]; return value == null || value === "" ? fallback : String(value); }
function path(id: number, suffix: string): string { return `${BASE}/runs/${id}${suffix}`; }

function AcceptanceDialog({ summary, retry, busy, onClose, onAccept }: { summary: Summary; retry: boolean; busy: boolean; onClose: () => void; onAccept: () => void }) {
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
    <div role="dialog" aria-modal="true" aria-labelledby="stage3-accept-title" className="w-full max-w-lg space-y-4 rounded-xl bg-white p-6 shadow-xl dark:bg-zinc-950">
      <div><h3 id="stage3-accept-title" className="text-lg font-semibold">{retry ? "Повторить принятие" : "Принять этап «Обучение и повышение квалификации»"}?</h3><p className="mt-1 text-sm">Сотрудников: {summary.employee_count}; исключено: {summary.skipped_count}.</p></div>
      <div className="rounded border p-3 text-sm"><p className="font-medium">Будет записано по расчёту сервера</p><ul className="mt-1 list-disc pl-5">{Object.entries(summary.records_by_kind).map(([kind, count]) => <li key={kind}>{kind}: {count}</li>)}</ul></div>
      <p className="text-sm text-zinc-700 dark:text-zinc-300">До статуса «Этап принят» карточка сотрудника не изменяется. Предложения не редактируются в этом интерфейсе.</p>
      <div className="flex justify-end gap-2"><button type="button" disabled={busy} onClick={onClose} className="rounded border px-3 py-2 text-sm">Отмена</button><button type="button" disabled={busy} onClick={onAccept} className="rounded bg-emerald-700 px-3 py-2 text-sm text-white">{busy ? "Принятие…" : retry ? "Повторить принятие" : "Принять этап"}</button></div>
    </div>
  </div>;
}

function ParticipantCard({ participant, accepted, busy, skipAllowed, onSkip }: { participant: Participant; accepted: boolean; busy: boolean; skipAllowed: boolean; onSkip: (reason: string) => void }) {
  const [reason, setReason] = useState("");
  return <article className="space-y-3 rounded-lg border bg-white p-4 dark:bg-zinc-950" aria-label={`Участник ${participant.position}`}>
    <header className="flex flex-wrap items-baseline justify-between gap-2"><div><h3 className="font-medium">Сотрудник #{participant.employee_id}</h3><p className="text-xs text-zinc-600">Позиция: {participant.position}; предложений: {participant.fragments.length}.</p></div><p className="text-sm"><b>Статус: </b>{accepted && participant.status === "COMPLETED" ? "Данные записаны" : (labels[participant.status] ?? participant.status)}</p></header>
    {participant.error_code ? <p role="status" className="rounded border border-amber-300 bg-amber-50 p-2 text-sm">{errors[participant.error_code] ?? "Обработка остановлена. Проверьте исходные данные."}</p> : null}
    <div className="overflow-x-auto"><table className="min-w-full text-sm"><thead><tr className="border-b text-left"><th className="p-2">Фрагмент</th><th className="p-2">Источник</th><th className="p-2">Сейчас в карточке</th><th className="p-2">Предложение</th><th className="p-2">Результат</th></tr></thead><tbody>{participant.fragments.map((fragment) => <tr key={fragment.fragment_index} className="border-b align-top"><th scope="row" className="p-2">#{fragment.fragment_index + 1}</th><td className="p-2">{field(fragment.source, "title")}<br /><span className="text-xs text-zinc-500">{field(fragment.source, "provider_name")}</span></td><td className="p-2">{field(fragment.current, "title", "Нет записи")}</td><td className="p-2">{field(fragment.proposal, "title", "Без изменений")}<br /><span className="text-xs text-zinc-500">{field(fragment.proposal, "training_kind")}{Object.prototype.hasOwnProperty.call(fragment.proposal, "certificate_number") ? ` · сертификат: ${field(fragment.proposal, "certificate_number")}` : ""}</span></td><td className="p-2">{labels[fragment.outcome] ?? fragment.outcome}<details className="mt-1 text-xs"><summary>Технические сведения</summary>{fragment.reason_code}</details></td></tr>)}</tbody></table></div>
    {skipAllowed ? <div className="flex flex-wrap items-end gap-2"><label className="text-sm">Причина исключения <input aria-label={`Причина исключения ${participant.position}`} value={reason} onChange={(event) => setReason(event.target.value)} className="ml-2 rounded border p-1" /></label><button type="button" disabled={busy || !reason.trim()} onClick={() => onSkip(reason)} className="rounded border px-3 py-2 text-sm">Исключить участника</button></div> : null}
  </article>;
}

export default function Stage3TrainingPanel({ cohortRunId }: { cohortRunId?: number }) {
  const [cohort, setCohort] = useState(cohortRunId ? String(cohortRunId) : "");
  const [runInput, setRunInput] = useState(""); const [preview, setPreview] = useState<Preview | null>(null);
  const [run, setRun] = useState<Run | null>(null); const [summary, setSummary] = useState<Summary | null>(null);
  const [cancelReason, setCancelReason] = useState(""); const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false); const [dialogOpen, setDialogOpen] = useState(false); const inFlight = useRef(false);
  useEffect(() => { if (cohortRunId) setCohort(String(cohortRunId)); }, [cohortRunId]);
  const id = run?.run.stage_run_id; const accepted = run?.run.status === "ACCEPTED";
  const approvalBlocked = run?.participants.some((participant) => participant.status !== "SKIPPED_BY_DECISION" && participant.fragments.some((fragment) => ["REVIEW_REQUIRED", "CANONICAL_CONFLICT"].includes(fragment.outcome)));
  function skipAllowed(participant: Participant): boolean {
    if (!run || accepted || !["PENDING", "ERROR"].includes(participant.status)) return false;
    if (["DRY_RUN_COMPLETED", "APPROVED"].includes(run.run.status)) return true;
    return run.run.status === "PAUSED_ON_ERROR"
      && run.run.paused_operation === "PARTICIPANT_EXECUTION"
      && participant.status === "ERROR"
      && run.run.stopped_participant_id === participant.stage_run_participant_id;
  }

  async function request(nextPath: string, body?: Values, method: "GET" | "POST" = "POST") {
    if (inFlight.current) return null; inFlight.current = true; setBusy(true); setNotice("");
    try { const next = await apiFetchJson<Run>(nextPath, method === "GET" ? undefined : { method, body }); setRun(next); setRunInput(String(next.run.stage_run_id)); return next; }
    catch (error) { setNotice(errorMessage(error)); return null; } finally { inFlight.current = false; setBusy(false); }
  }
  async function dryRun() { if (!cohort || inFlight.current) return; inFlight.current = true; setBusy(true); setNotice(""); setRun(null); try { const next = await apiFetchJson<Preview>(`${BASE}/preview`, { method: "POST", body: { stage0_cohort_run_id: Number(cohort) } }); setPreview(next); setNotice("Предварительная проверка завершена: запуск, PMF и личные карточки не изменялись."); } catch (error) { setNotice(errorMessage(error)); } finally { inFlight.current = false; setBusy(false); } }
  async function createRun() { if (!preview) return; await request(`${BASE}/runs`, { stage0_cohort_run_id: preview.stage0_cohort_run_id, preview_fingerprint: preview.preview_fingerprint }); }
  async function action(suffix: string, body: Values = {}) { if (id) await request(path(id, suffix), body); }
  async function showSummary() { if (!id || inFlight.current) return; inFlight.current = true; setBusy(true); setNotice(""); try { setSummary(await apiFetchJson<Summary>(path(id, "/acceptance-summary"))); setDialogOpen(true); } catch (error) { setNotice(errorMessage(error)); } finally { inFlight.current = false; setBusy(false); } }
  async function accept() { if (!id || !summary) return; const retry = run?.run.paused_operation === "ACCEPTANCE"; setDialogOpen(false); await action(retry ? "/retry-accept" : "/accept", { stage_run_id: id, acceptance_fingerprint: summary.acceptance_fingerprint }); }

  return <section className="space-y-4 rounded-xl border border-violet-300 bg-violet-50/40 p-4 dark:border-violet-900 dark:bg-violet-950/20" data-testid="stage3-training-panel">
    <header><p className="text-sm text-violet-800 dark:text-violet-200">Этап 3</p><h2 className="text-xl font-semibold">Обучение и повышение квалификации</h2><p className="text-sm text-zinc-600 dark:text-zinc-400">Рабочее место HR_HEAD: предложения только просматриваются. Карточка не изменяется до явного принятия этапа.</p></header>
    <div className="flex flex-wrap items-end gap-2"><label className="text-sm">ID зафиксированного списка <input aria-label="ID зафиксированного списка Stage 3" value={cohort} onChange={(event) => { setCohort(event.target.value); setPreview(null); }} className="ml-2 w-24 rounded border p-1" /></label><button type="button" disabled={busy || !cohort} onClick={() => void dryRun()} className="rounded bg-violet-700 px-3 py-2 text-sm text-white disabled:opacity-50">Выполнить dry-run preview</button>{preview ? <button type="button" disabled={busy} onClick={() => void createRun()} className="rounded bg-emerald-700 px-3 py-2 text-sm text-white disabled:opacity-50">Создать запуск</button> : null}<label className="text-sm">ID запуска <input aria-label="ID запуска Stage 3" value={runInput} onChange={(event) => setRunInput(event.target.value)} className="ml-2 w-20 rounded border p-1" /></label><button type="button" disabled={busy || !runInput} onClick={() => void request(path(Number(runInput), ""), undefined, "GET")} className="rounded border px-3 py-2 text-sm disabled:opacity-50">Открыть запуск</button></div>
    {preview ? <p className="rounded border border-violet-200 bg-white p-3 text-sm dark:bg-zinc-950">Dry-run: участников в проверке: {preview.participant_count}. Создание запуска — отдельное действие; личные карточки не меняются.</p> : null}
    {notice ? <p role="status" className="rounded border border-amber-300 bg-amber-50 p-3 text-sm">{notice}</p> : null}
    {run ? <><div className="rounded border bg-white p-3 text-sm dark:bg-zinc-950"><p><b>Статус: </b>{labels[run.run.status] ?? run.run.status}</p><p>Подготовлено PMF: {run.counts.COMPLETED ?? 0} из {run.participants.length}; исключено: {run.counts.SKIPPED_BY_DECISION ?? 0}.</p>{accepted ? <p className="mt-2 font-medium">Этап принят: данные записаны через PPR bridge.</p> : <p className="mt-2">До ACCEPTED личные карточки не изменяются.</p>}</div>
      {approvalBlocked && run.run.status === "DRY_RUN_COMPLETED" ? <p role="status" className="text-sm">Утверждение недоступно: исключите участников с ручными решениями либо исправьте источник и создайте новый preview.</p> : null}
      <div className="flex flex-wrap gap-2">{run.run.status === "DRY_RUN_COMPLETED" ? <button type="button" disabled={busy || approvalBlocked} onClick={() => void action("/approve")} className="rounded bg-violet-700 px-3 py-2 text-sm text-white disabled:opacity-50">Утвердить запуск</button> : null}{["APPROVED", "RUNNING"].includes(run.run.status) ? <button type="button" disabled={busy} onClick={() => void action("/execute-next")} className="rounded bg-violet-700 px-3 py-2 text-sm text-white">Обработать следующего</button> : null}{run.run.status === "PAUSED_ON_ERROR" && run.run.paused_operation === "PARTICIPANT_EXECUTION" ? <button type="button" disabled={busy} onClick={() => void action("/resume")} className="rounded bg-amber-700 px-3 py-2 text-sm text-white">Продолжить обработку</button> : null}{run.run.status === "COMPLETED_PENDING_REVIEW" || (run.run.status === "PAUSED_ON_ERROR" && run.run.paused_operation === "ACCEPTANCE") ? <button type="button" disabled={busy} onClick={() => void showSummary()} className="rounded bg-emerald-700 px-3 py-2 text-sm text-white">{run.run.paused_operation === "ACCEPTANCE" ? "Повторить принятие" : "Показать итог принятия"}</button> : null}</div>
      {!accepted && run.run.status !== "CANCELLED" ? <div className="flex flex-wrap items-end gap-2 rounded border p-3"><label className="text-sm">Причина отмены <input aria-label="Причина отмены Stage 3" value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} className="ml-2 rounded border p-1" /></label><button type="button" disabled={busy || !cancelReason.trim()} onClick={() => void action("/cancel", { reason: cancelReason })} className="rounded border px-3 py-2 text-sm">Отменить запуск</button></div> : null}
      <div className="space-y-3">{[...run.participants].sort((left, right) => left.position - right.position).map((participant) => <ParticipantCard key={participant.stage_run_participant_id} participant={participant} accepted={Boolean(accepted)} busy={busy} skipAllowed={skipAllowed(participant)} onSkip={(reason) => void action(`/participants/${participant.stage_run_participant_id}/skip`, { reason })} />)}</div>
    </> : null}
    {dialogOpen && summary ? <AcceptanceDialog summary={summary} retry={run?.run.paused_operation === "ACCEPTANCE"} busy={busy} onClose={() => setDialogOpen(false)} onAccept={() => void accept()} /> : null}
  </section>;
}
