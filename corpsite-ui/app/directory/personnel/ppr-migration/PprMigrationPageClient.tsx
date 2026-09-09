"use client";

import { useEffect, useState, type ReactNode } from "react";

import { apiAuthMe, apiFetchJson } from "@/lib/api";
import type { MeInfo } from "@/lib/types";
import Stage1GeneralPanel from "./Stage1GeneralPanel";
import Stage2EducationPanel from "./Stage2EducationPanel";

type Batch = { batch_id: number; status: string; imported_at?: string | null; source_row_count: number };
type Candidate = { position?: number; employee_id: number | null; person_id: number | null; source_batch_id: number; source_row_id: number; source_row_number?: number | null; safe_fingerprint: string; display_name?: string | null };
type Blocker = { employee_id?: number | null; person_id?: number | null; source_batch_id?: number | null; source_row_id?: number | null; source_row_number?: number | null; category: string; reason_code: string; safe_detail: string; candidate_key: string; display_name?: string | null };
type Preview = { source_batch_id: number; source_batch_status: string; preview_fingerprint: string; counts: Record<string, number>; eligible: Candidate[]; blockers: Blocker[] };
type Frozen = { stage0_cohort_run_id: number; replay: boolean; counts: Record<string, number> };
type Cohort = { run: { stage0_cohort_run_id: number; run_kind: string; source_batch_id: number; source_batch_status: string; frozen_at: string; preview_fingerprint: string }; participants: Candidate[]; organization_timezone: string };

const reasonLabels: Record<string, string> = {
  STAGE0_SOURCE_EMPLOYEE_MISSING: "Строка контрольного списка пока не связана с сотрудником.",
  STAGE0_EMPLOYEE_NOT_ACTIVE: "Сотрудник не находится в активном кадровом статусе.",
  STAGE0_EMPLOYEE_PERSON_MISSING: "Для сотрудника не найдена однозначная связь с личностью.",
  STAGE0_PERSON_NOT_ACTIVE: "Связанная личность объединена, удалена или неактивна.",
  STAGE0_MULTIPLE_OPERATIONAL_EMPLOYEES: "Для одной личности найдено несколько активных сотрудников.",
  STAGE0_SOURCE_ANCHOR_NOT_UNIQUE: "Для сотрудника найдено несколько строк контрольного списка.",
  STAGE0_BATCH_PENDING_REMOVALS: "В контрольном списке есть неурегулированные удаления; фиксация пока недоступна.",
  STAGE0_PPR_LIFECYCLE_NOT_MATERIALIZABLE: "Текущий жизненный цикл личной карточки не допускает её подготовку.",
};

const categoryLabels: Record<string, string> = {
  ELIGIBLE: "Допущен к следующему этапу",
  BLOCKED_NO_PERSON: "Нет связи с личностью",
  BLOCKED_AMBIGUOUS_PERSON: "Неоднозначная связь с личностью",
  BLOCKED_PERSON_MERGED_OR_DELETED: "Личность недоступна",
  BLOCKED_SOURCE_MISSING: "Нет корректной связи с контрольным списком",
  BLOCKED_SOURCE_AMBIGUOUS: "Неоднозначная строка контрольного списка",
  BLOCKED_SOURCE_STATUS: "Недопустимый статус контрольного списка",
  BLOCKED_SOURCE_DELETION_OR_REBINDING: "Требуется урегулировать изменения контрольного списка",
  BLOCKED_MATERIALIZATION_PATH: "Нет допустимого пути подготовки личной карточки",
};

const batchStatusLabels: Record<string, string> = {
  APPLY_PENDING: "готов к применению",
  APPLIED: "применён",
  PARTIALLY_APPLIED: "применён частично",
};

function batchStatusLabel(status: string): string { return batchStatusLabels[status] ?? status; }
function apiMessage(error: any): string { return String(error?.details?.message ?? error?.message ?? "Не удалось выполнить запрос."); }
function personLabel(row: { display_name?: string | null; employee_id?: number | null }): string { return String(row.display_name ?? "").trim() || `Сотрудник #${row.employee_id ?? "—"}`; }
function technicalIdentity(row: { employee_id?: number | null; person_id?: number | null }): string { return `ID сотрудника: ${row.employee_id ?? "—"}; ID личности: ${row.person_id ?? "—"}`; }
function technicalCode(code: string): ReactNode { return <details className="mt-1 text-xs text-zinc-500"><summary className="cursor-pointer">Технические сведения</summary><span className="font-mono">{code}</span></details>; }
export function formatStage0FrozenAt(value: string, timezone: string): string {
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) return value;
  try {
    return new Intl.DateTimeFormat("ru-RU", {
      timeZone: timezone,
      year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    }).format(instant);
  } catch { return new Intl.DateTimeFormat("ru-RU", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(instant); }
}

export default function PprMigrationPageClient() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [batchId, setBatchId] = useState<number | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [cohort, setCohort] = useState<Cohort | null>(null);
  const [freezeConfirmationOpen, setFreezeConfirmationOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [isHrHead, setIsHrHead] = useState(false);

  useEffect(() => { void (async () => {
    try {
      const me: MeInfo = await apiAuthMe();
      if (String(me.role_code ?? "").toUpperCase() !== "HR_HEAD") { setMessage("Доступ к подготовке списка сотрудников разрешён только руководителю кадровой службы."); return; }
      setIsHrHead(true);
      const response = await apiFetchJson<{ items: Batch[] }>("/personnel/ppr-migration/stage-0/source-batches");
      setBatches(response.items);
      if (response.items[0]) setBatchId(response.items[0].batch_id);
    } catch (error) { setMessage(apiMessage(error)); } finally { setLoading(false); }
  })(); }, []);

  async function runPreview() {
    if (!batchId) return;
    setBusy(true); setMessage(""); setCohort(null); setFreezeConfirmationOpen(false);
    try {
      const result = await apiFetchJson<Preview>("/personnel/ppr-migration/stage-0/preview", { method: "POST", body: { source_batch_id: batchId, correction_details: true } });
      setPreview(result); setMessage("Проверка завершена. Данные не сохранялись и личные карточки не изменялись.");
    } catch (error) { setMessage(apiMessage(error)); } finally { setBusy(false); }
  }

  async function freeze() {
    if (!preview) return;
    setBusy(true); setMessage("");
    try {
      const result = await apiFetchJson<Frozen>("/personnel/ppr-migration/stage-0/freeze", { method: "POST", body: { source_batch_id: preview.source_batch_id, preview_fingerprint: preview.preview_fingerprint } });
      const saved = await apiFetchJson<Cohort>(`/personnel/ppr-migration/stage-0/runs/${result.stage0_cohort_run_id}?correction_details=true`);
      setCohort(saved); setFreezeConfirmationOpen(false);
      const accepted = result.counts.ELIGIBLE ?? 0;
      const blocked = Object.entries(result.counts).filter(([status]) => status !== "ELIGIBLE").reduce((total, [, count]) => total + count, 0);
      setMessage(result.replay ? `Ранее зафиксированный список №${result.stage0_cohort_run_id} открыт повторно. Личные карточки не изменялись.` : `Список допущенных сотрудников зафиксирован: ${accepted}; заблокировано: ${blocked}. Личные карточки и сведения в них не изменялись.`);
    } catch (error) { setMessage(apiMessage(error)); } finally { setBusy(false); }
  }

  const eligibleCount = preview?.counts.ELIGIBLE ?? 0;
  const blockedCount = preview ? Object.entries(preview.counts).filter(([status]) => status !== "ELIGIBLE").reduce((total, [, count]) => total + count, 0) : 0;
  if (loading) return <div className="rounded-xl border border-zinc-200 bg-white p-4 text-sm dark:border-zinc-800 dark:bg-zinc-900">Загрузка подготовки списка сотрудников…</div>;
  return <main className="space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-3 border-b border-zinc-200 pb-4 dark:border-zinc-800">
      <div><p className="text-sm text-zinc-500">Программа миграции личных карточек</p><h1 className="text-2xl font-semibold">Подготовка списка сотрудников</h1><p className="mt-1 max-w-3xl text-sm text-zinc-600 dark:text-zinc-400">Проверьте контрольный список, исправьте выявленные проблемы и зафиксируйте только допущенных сотрудников. На этом шаге данные личных карточек не переносятся и не изменяются.</p></div>
      <span className="rounded-full border border-blue-300 bg-blue-50 px-3 py-1 text-sm font-medium text-blue-900 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-100">Роль: руководитель кадровой службы</span>
    </header>
    <section className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <label className="block text-sm font-medium" htmlFor="stage0-batch">Контрольный список</label>
      <div className="mt-2 flex flex-wrap items-center gap-3"><select id="stage0-batch" value={batchId ?? ""} onChange={(e) => { setBatchId(Number(e.target.value)); setPreview(null); setCohort(null); setFreezeConfirmationOpen(false); }} className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950">
        {batches.length === 0 ? <option value="">Нет контрольных списков в допустимом статусе</option> : batches.map((batch) => <option key={batch.batch_id} value={batch.batch_id}>Контрольный список №{batch.batch_id} · {batchStatusLabel(batch.status)} · строк: {batch.source_row_count}</option>)}</select>
        <button type="button" onClick={runPreview} disabled={!batchId || busy} className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{busy ? "Выполняется…" : "Проверить сотрудников"}</button>
        <span className="text-sm text-zinc-500">Полный ИИН не отображается.</span></div>
    </section>
    {message ? <div role="status" className="rounded-lg border border-zinc-300 bg-zinc-50 px-4 py-3 text-sm dark:border-zinc-700 dark:bg-zinc-950">{message}</div> : null}
    {preview ? <section className="space-y-4"><div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Результат проверки</h2><p className="text-sm text-zinc-600 dark:text-zinc-400">Контрольный список №{preview.source_batch_id}; статус: {batchStatusLabel(preview.source_batch_status)}.</p><details className="mt-1 text-xs text-zinc-500"><summary className="cursor-pointer">Технические сведения проверки</summary><span className="font-mono">Контрольный отпечаток: {preview.preview_fingerprint}</span></details></div>{cohort ? <span className="rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/25 dark:text-emerald-100">Список уже зафиксирован</span> : <button type="button" onClick={() => setFreezeConfirmationOpen(true)} disabled={busy} className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Зафиксировать список допущенных сотрудников</button>}</div><div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{Object.entries(preview.counts).map(([status, count]) => <div key={status} className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-700"><div className="font-medium">{categoryLabels[status] ?? "Требуется проверка"}</div><div className="text-2xl font-semibold">{count}</div>{technicalCode(status)}</div>)}</div></div>
      <CandidateTable title="Допущенные сотрудники" items={preview.eligible} />
      <BlockerTable items={preview.blockers} />
    </section> : null}
    {cohort ? <section className="rounded-xl border border-emerald-300 bg-emerald-50 p-4 dark:border-emerald-900 dark:bg-emerald-950/25"><h2 className="text-lg font-semibold">Список допущенных сотрудников зафиксирован</h2><p className="text-sm">Статус: список зафиксирован · контрольный список №{cohort.run.source_batch_id} · сохранён: {formatStage0FrozenAt(cohort.run.frozen_at, cohort.organization_timezone)} ({cohort.organization_timezone})</p><details className="mt-1 text-xs text-zinc-600"><summary className="cursor-pointer">Технические сведения</summary><span className="font-mono">Код статуса: FROZEN; ID списка: {cohort.run.stage0_cohort_run_id}</span></details><CandidateTable title="Участники зафиксированного списка" items={cohort.participants} /></section> : null}
    {freezeConfirmationOpen && preview ? <FreezeConfirmationDialog eligibleCount={eligibleCount} blockedCount={blockedCount} busy={busy} onCancel={() => setFreezeConfirmationOpen(false)} onConfirm={() => void freeze()} /> : null}
    <Stage1GeneralPanel cohortRunId={cohort?.run.stage0_cohort_run_id} />
    {isHrHead ? <Stage2EducationPanel cohortRunId={cohort?.run.stage0_cohort_run_id} /> : null}
  </main>;
}

function FreezeConfirmationDialog({ eligibleCount, blockedCount, busy, onCancel, onConfirm }: { eligibleCount: number; blockedCount: number; busy: boolean; onCancel: () => void; onConfirm: () => void }) { return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"><div role="dialog" aria-modal="true" aria-labelledby="stage0-freeze-title" className="w-full max-w-lg rounded-xl border border-zinc-200 bg-white p-5 shadow-xl dark:border-zinc-800 dark:bg-zinc-950" data-testid="stage0-freeze-confirmation"><h2 id="stage0-freeze-title" className="text-lg font-semibold">Зафиксировать список допущенных сотрудников?</h2><p className="mt-3 text-sm text-zinc-700 dark:text-zinc-300">Будет сохранён список из {eligibleCount} допущенных сотрудников. Заблокированных сотрудников: {blockedCount}; они в список не войдут.</p><p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">Данные личных карточек, общие сведения, образование и другие разделы на этом шаге не изменяются.</p><div className="mt-5 flex flex-wrap justify-end gap-2"><button type="button" disabled={busy} onClick={onCancel} className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-800 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200">Отмена</button><button type="button" disabled={busy} onClick={onConfirm} className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{busy ? "Сохранение…" : "Зафиксировать список"}</button></div></div></div>; }
function CandidateTable({ title, items }: { title: string; items: Candidate[] }) { return <section className="overflow-hidden rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"><h2 className="border-b border-zinc-200 px-4 py-3 text-lg font-semibold dark:border-zinc-800">{title} — {items.length}</h2><div className="overflow-x-auto"><table className="min-w-full text-sm"><thead className="bg-zinc-100 text-left dark:bg-zinc-950"><tr><th className="px-3 py-2">Позиция</th><th className="px-3 py-2">Сотрудник</th><th className="px-3 py-2">Строка контрольного списка</th><th className="px-3 py-2">Статус</th></tr></thead><tbody>{items.length ? items.map((item) => <tr key={`${item.employee_id}-${item.source_row_id}`} className="border-t border-zinc-200 dark:border-zinc-800"><td className="px-3 py-2">{item.position ?? "—"}</td><td className="px-3 py-2">{personLabel(item)}{technicalCode(technicalIdentity(item))}</td><td className="px-3 py-2">№{item.source_row_number ?? item.source_row_id}{technicalCode(`ID строки: ${item.source_row_id}`)}</td><td className="px-3 py-2">Допущен к следующему этапу{technicalCode("ELIGIBLE")}</td></tr>) : <tr><td colSpan={4} className="px-3 py-5 text-center text-zinc-500">Нет допущенных сотрудников.</td></tr>}</tbody></table></div></section>; }
function BlockerTable({ items }: { items: Blocker[] }) { return <section className="overflow-hidden rounded-xl border border-amber-300 bg-white dark:border-amber-900 dark:bg-zinc-900"><h2 className="border-b border-amber-200 px-4 py-3 text-lg font-semibold dark:border-amber-900">Сотрудники, требующие исправления — {items.length}</h2><p className="px-4 pt-3 text-sm text-zinc-600 dark:text-zinc-400">Исправьте связь или исходную строку, затем запустите проверку повторно. Полный ИИН не отображается.</p><div className="overflow-x-auto"><table className="min-w-full text-sm"><thead className="bg-amber-50 text-left dark:bg-amber-950/30"><tr><th className="px-3 py-2">Сотрудник из контрольного списка</th><th className="px-3 py-2">Строка контрольного списка</th><th className="px-3 py-2">Что нужно исправить</th></tr></thead><tbody>{items.length ? items.map((item) => <tr key={`${item.candidate_key}-${item.reason_code}`} className="border-t border-zinc-200 dark:border-zinc-800"><td className="px-3 py-2">{personLabel(item)}{technicalCode(technicalIdentity(item))}</td><td className="px-3 py-2">№{item.source_row_number ?? item.source_row_id ?? "—"}{item.source_row_id ? technicalCode(`ID строки: ${item.source_row_id}`) : null}</td><td className="px-3 py-2"><div className="font-medium">{categoryLabels[item.category] ?? "Требуется проверка"}</div><div className="mt-1">{reasonLabels[item.reason_code] ?? item.safe_detail}</div>{technicalCode(`${item.category}; ${item.reason_code}`)}</td></tr>) : <tr><td colSpan={3} className="px-3 py-5 text-center text-zinc-500">Нет заблокированных сотрудников.</td></tr>}</tbody></table></div></section>; }
