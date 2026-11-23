"use client";

import { useEffect, useRef, useState } from "react";

import { apiFetchJson } from "@/lib/api";

type Values = Record<string, unknown>;
type Fragment = { fragment_index: number; source: Values; current: Values; proposal: Values; outcome: string; reason_code: string };
type Participant = { stage_run_participant_id: number; position: number; employee_id: number; status: string; fragments: Fragment[]; error_code?: string | null };
type Run = { run: { stage_run_id: number; stage0_cohort_run_id?: number; status: string; current_position: number; paused_operation?: string | null; acceptance_outcome?: Values }; participants: Participant[]; counts: Record<string, number>; organization_timezone?: string };
type Summary = { stage_run_id: number; employee_count: number; records_by_kind: Record<string, number>; skipped_count: number; acceptance_fingerprint: string };

const BASE = "/personnel/ppr-migration/stage-2/education";
const stateLabel: Record<string, string> = { DRY_RUN_COMPLETED: "Проверка завершена", APPROVED: "Утверждён к запуску", RUNNING: "Выполняется", PAUSED_ON_ERROR: "Остановлен из-за ошибки", COMPLETED_PENDING_REVIEW: "Готов к принятию", ACCEPTED: "Этап принят", CANCELLED: "Отменён", PENDING: "Ожидает обработки", COMPLETED: "Черновик подготовлен", ERROR: "Требуется исправление", SKIPPED_BY_DECISION: "Исключён по решению", READY_TO_ADD: "Будет добавлено", ALREADY_APPLIED: "Уже записано", CANONICAL_CONFLICT: "Конфликт — требуется решение", REVIEW_REQUIRED: "Требуется проверка" };
const errorLabel: Record<string, string> = { STAGE2_PREVIEW_STALE: "Данные изменились. Требуется новый PREVIEW.", STAGE2_ACCEPTANCE_STALE: "Данные изменились перед принятием. Требуется новый PREVIEW.", STAGE2_RESUME_STALE: "Данные участника изменились. Требуется новый PREVIEW.", STAGE2_FRAGMENT_REVIEW_REQUIRED: "Есть фрагменты, требующие проверки. Исправьте источник или исключите участника.", STAGE2_APPROVAL_BLOCKED: "Утверждение заблокировано: требуется проверка фрагментов.", STAGE2_COHORT_OUT_OF_SCOPE: "Прогон недоступен в вашем подразделении.", STAGE2_ACCEPTANCE_PAUSED: "Принятие остановлено. Повторите принятие после проверки причины." };

function message(error: unknown): string {
  const value = error as { details?: { code?: unknown; message?: unknown }; message?: unknown };
  const code = String(value?.details?.code ?? "");
  return errorLabel[code] ?? String(value?.details?.message ?? value?.message ?? "Не удалось выполнить действие.");
}
function field(values: Values, name: string, fallback = "—"): string { const value = values[name]; return value == null || value === "" ? fallback : String(value); }
function runPath(runId: number, suffix: string): string { return `${BASE}/runs/${runId}${suffix}`; }

function AcceptanceDialog({ summary, busy, onCancel, onConfirm }: { summary: Summary; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4"><div role="dialog" aria-modal="true" aria-labelledby="stage2-accept-title" className="w-full max-w-lg space-y-4 rounded-xl bg-white p-6 shadow-xl dark:bg-zinc-950">
    <div><h3 id="stage2-accept-title" className="text-lg font-semibold">Принять этап «Образование»?</h3><p className="mt-1 text-sm">Сотрудников: {summary.employee_count}; исключено: {summary.skipped_count}.</p></div>
    <div className="rounded border p-3 text-sm"><p className="font-medium">Будет записано (расчёт сервера)</p><ul className="mt-1 list-disc pl-5">{Object.entries(summary.records_by_kind).map(([kind, count]) => <li key={kind}>{kind}: {count}</li>) || <li>Новых записей нет.</li>}</ul></div>
    <ul className="space-y-1 text-sm text-zinc-700 dark:text-zinc-300"><li>Непустые значения в карточке не перезаписываются.</li><li>Принятие атомарно: при ошибке ничего не будет записано.</li><li>Полный ИИН не отображается.</li></ul>
    <div className="flex justify-end gap-2"><button type="button" disabled={busy} onClick={onCancel} className="rounded border px-3 py-2 text-sm">Отмена</button><button type="button" disabled={busy} onClick={onConfirm} className="rounded bg-emerald-700 px-3 py-2 text-sm text-white">{busy ? "Принятие…" : "Принять этап"}</button></div>
  </div></div>;
}

function ParticipantCard({ participant, accepted, onSkip, busy }: { participant: Participant; accepted: boolean; onSkip: (participant: Participant, reason: string) => void; busy: boolean }) {
  const [reason, setReason] = useState("");
  return <article className="space-y-3 rounded-lg border bg-white p-4 dark:bg-zinc-950" aria-label={`Участник ${participant.position}`}>
    <header className="flex flex-wrap items-baseline justify-between gap-2"><div><h3 className="font-medium">Сотрудник #{participant.employee_id}</h3><p className="text-xs text-zinc-600">Зафиксированная позиция: {participant.position}; фрагментов: {participant.fragments.length}.</p></div><p className="text-sm"><b>Статус: </b>{accepted && participant.status === "COMPLETED" ? "Данные записаны" : (stateLabel[participant.status] ?? participant.status)}</p></header>
    {participant.error_code ? <p role="status" className="rounded border border-amber-300 bg-amber-50 p-2 text-sm">{errorLabel[participant.error_code] ?? "Обработка остановлена: проверьте исходные данные. Код причины доступен в технических сведениях."}</p> : null}
    <div className="overflow-x-auto"><table className="min-w-full text-sm"><thead><tr className="border-b text-left"><th className="p-2">Фрагмент</th><th className="p-2">В контрольном списке</th><th className="p-2">Сейчас в карточке</th><th className="p-2">Будет записано</th><th className="p-2">Результат</th></tr></thead><tbody>{participant.fragments.map((fragment) => <tr key={fragment.fragment_index} className="border-b align-top"><th scope="row" className="p-2">#{fragment.fragment_index + 1}</th><td className="p-2">{field(fragment.source, "institution_name")}</td><td className="p-2">{field(fragment.current, "institution_name", "Нет записи")}</td><td className="p-2">{field(fragment.proposal, "institution_name", "Без изменений")}</td><td className="p-2"><span>{stateLabel[fragment.outcome] ?? fragment.outcome}</span><details className="mt-1 text-xs"><summary>Технические сведения</summary>{fragment.reason_code}</details></td></tr>)}</tbody></table></div>
    {!accepted && ["PENDING", "ERROR"].includes(participant.status) ? <div className="flex flex-wrap items-end gap-2"><label className="text-sm">Причина исключения <input aria-label={`Причина исключения ${participant.position}`} value={reason} onChange={(event) => setReason(event.target.value)} className="ml-2 rounded border p-1" /></label><button type="button" disabled={busy || !reason.trim()} onClick={() => onSkip(participant, reason)} className="rounded border px-3 py-2 text-sm">Исключить участника</button></div> : null}
  </article>;
}

export default function Stage2EducationPanel({ cohortRunId }: { cohortRunId?: number }) {
  const [cohort, setCohort] = useState(cohortRunId ? String(cohortRunId) : "");
  const [runInput, setRunInput] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [cancelReason, setCancelReason] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const inFlight = useRef(false);

  useEffect(() => { if (cohortRunId) setCohort(String(cohortRunId)); }, [cohortRunId]);
  const id = run?.run.stage_run_id;
  const accepted = run?.run.status === "ACCEPTED";
  const resumeStale = run?.run.paused_operation === "PARTICIPANT_EXECUTION" && run.participants.some((participant) => participant.error_code === "STAGE2_RESUME_STALE");
  const approvalBlocked = run?.participants.some((participant) => participant.status !== "COMPLETED" && participant.fragments.some((fragment) => ["REVIEW_REQUIRED", "CANONICAL_CONFLICT"].includes(fragment.outcome)));

  async function request(path: string, body?: Values, method: "GET" | "POST" = "POST"): Promise<Run | null> {
    if (inFlight.current) return null;
    inFlight.current = true; setBusy(true); setNotice("");
    try { const next = await apiFetchJson<Run>(path, method === "GET" ? undefined : { method, body }); setRun(next); setRunInput(String(next.run.stage_run_id)); return next; }
    catch (error) { setNotice(message(error)); return null; }
    finally { inFlight.current = false; setBusy(false); }
  }
  async function preview() { if (cohort) await request(`${BASE}/preview`, { stage0_cohort_run_id: Number(cohort) }); }
  async function open() { if (runInput) await request(runPath(Number(runInput), ""), undefined, "GET"); }
  async function action(suffix: string, body: Values = {}) { if (id) await request(runPath(id, suffix), body); }
  async function showAcceptance() {
    if (!id || inFlight.current) return;
    inFlight.current = true; setBusy(true); setNotice("");
    try { setSummary(await apiFetchJson<Summary>(runPath(id, "/acceptance-summary"))); setDialogOpen(true); }
    catch (error) { setNotice(message(error)); }
    finally { inFlight.current = false; setBusy(false); }
  }
  async function accept(retry = false) { if (!id || !summary || inFlight.current) return; setDialogOpen(false); await action(retry ? "/retry-accept" : "/accept", { stage_run_id: id, acceptance_fingerprint: summary.acceptance_fingerprint }); }

  return <section className="space-y-4 rounded-xl border border-sky-300 bg-sky-50/40 p-4 dark:border-sky-900 dark:bg-sky-950/20" data-testid="stage2-education-panel">
    <header><p className="text-sm text-sky-800 dark:text-sky-200">Этап 2</p><h2 className="text-xl font-semibold">Образование</h2><p className="text-sm text-zinc-600 dark:text-zinc-400">Черновики и сравнения доступны только HR_HEAD. Участники показаны в зафиксированном порядке; полный ИИН не отображается.</p></header>
    <div className="flex flex-wrap items-end gap-2"><label className="text-sm">ID зафиксированного списка <input aria-label="ID зафиксированного списка" value={cohort} onChange={(event) => setCohort(event.target.value)} className="ml-2 w-24 rounded border p-1" /></label><button type="button" disabled={busy || !cohort} onClick={() => void preview()} className="rounded bg-sky-700 px-3 py-2 text-sm text-white disabled:opacity-50">Проверить образование</button><label className="text-sm">ID прогона <input aria-label="ID прогона" value={runInput} onChange={(event) => setRunInput(event.target.value)} className="ml-2 w-20 rounded border p-1" /></label><button type="button" disabled={busy || !runInput} onClick={() => void open()} className="rounded border px-3 py-2 text-sm disabled:opacity-50">Открыть прогон</button></div>
    {notice ? <p role="status" className="rounded border border-amber-300 bg-amber-50 p-3 text-sm">{notice}</p> : null}
    {run ? <><div className="rounded border bg-white p-3 text-sm dark:bg-zinc-950"><p><b>Статус: </b>{stateLabel[run.run.status] ?? run.run.status}</p><p>Обработано: {run.counts.COMPLETED ?? 0} из {run.participants.length}; исключено: {run.counts.SKIPPED_BY_DECISION ?? 0}.</p>{accepted ? <p className="mt-2 font-medium">Принятие завершено. Повторное открытие показывает сохранённый результат без повторной записи.</p> : null}<details className="mt-1 text-xs"><summary>Технические сведения</summary>Код состояния: {run.run.status}; ID прогона: {id}</details></div>
      {approvalBlocked && run.run.status === "DRY_RUN_COMPLETED" ? <p role="status" className="text-sm">Утверждение недоступно: есть фрагменты, требующие проверки или разрешения конфликта. Исправьте источник либо исключите участника.</p> : null}{resumeStale ? <p role="status" className="text-sm">Текущий прогон продолжить нельзя: данные участника изменились. Создайте новый PREVIEW для этого зафиксированного списка.</p> : null}
      <div className="flex flex-wrap gap-2">{run.run.status === "DRY_RUN_COMPLETED" ? <button type="button" disabled={busy || approvalBlocked} onClick={() => void action("/approve")} className={approvalBlocked ? "cursor-not-allowed rounded border border-zinc-300 bg-zinc-100 px-3 py-2 text-sm text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200" : "rounded bg-blue-700 px-3 py-2 text-sm text-white"}>{approvalBlocked ? "Утверждение недоступно" : "Утвердить запуск"}</button> : null}{["APPROVED", "RUNNING"].includes(run.run.status) ? <button type="button" disabled={busy} onClick={() => void action("/execute-next")} className="rounded bg-blue-700 px-3 py-2 text-sm text-white">Обработать следующего</button> : null}{run.run.status === "PAUSED_ON_ERROR" && run.run.paused_operation === "PARTICIPANT_EXECUTION" && !resumeStale ? <button type="button" disabled={busy} onClick={() => void action("/resume")} className="rounded bg-amber-700 px-3 py-2 text-sm text-white">Продолжить обработку</button> : null}{resumeStale ? <button type="button" disabled={busy || !run.run.stage0_cohort_run_id} onClick={() => { setCohort(String(run.run.stage0_cohort_run_id)); void request(`${BASE}/preview`, { stage0_cohort_run_id: run.run.stage0_cohort_run_id }); }} className="rounded bg-sky-700 px-3 py-2 text-sm text-white">Создать новый PREVIEW</button> : null}{run.run.status === "PAUSED_ON_ERROR" && run.run.paused_operation === "ACCEPTANCE" ? <button type="button" disabled={busy} onClick={() => void showAcceptance()} className="rounded bg-amber-700 px-3 py-2 text-sm text-white">Повторить принятие</button> : null}{run.run.status === "COMPLETED_PENDING_REVIEW" ? <button type="button" disabled={busy} onClick={() => void showAcceptance()} className="rounded bg-emerald-700 px-3 py-2 text-sm text-white">Принять этап</button> : null}</div>
      {!accepted && run.run.status !== "CANCELLED" ? <div className="flex flex-wrap items-end gap-2 rounded border p-3"><label className="text-sm">Причина отмены <input aria-label="Причина отмены" value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} className="ml-2 rounded border p-1" /></label><button type="button" disabled={busy || !cancelReason.trim()} onClick={() => void action("/cancel", { reason: cancelReason })} className="rounded border px-3 py-2 text-sm">Отменить прогон</button></div> : null}
      <div className="space-y-3">{[...run.participants].sort((left, right) => left.position - right.position).map((participant) => <ParticipantCard key={participant.stage_run_participant_id} participant={participant} accepted={accepted} busy={busy} onSkip={(item, reason) => void action(`/participants/${item.stage_run_participant_id}/skip`, { reason })} />)}</div>
    </> : null}
    {dialogOpen && summary ? <AcceptanceDialog summary={summary} busy={busy} onCancel={() => setDialogOpen(false)} onConfirm={() => void accept(run?.run.paused_operation === "ACCEPTANCE")} /> : null}
  </section>;
}
