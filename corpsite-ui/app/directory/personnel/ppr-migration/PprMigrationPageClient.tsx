"use client";

import { useEffect, useState } from "react";

import { apiAuthMe, apiFetchJson } from "@/lib/api";
import type { MeInfo } from "@/lib/types";

type Batch = { batch_id: number; status: string; imported_at?: string | null; source_row_count: number };
type Candidate = { position?: number; employee_id: number | null; person_id: number | null; source_batch_id: number; source_row_id: number; safe_fingerprint: string; display_name?: string | null };
type Blocker = { employee_id?: number | null; person_id?: number | null; source_batch_id?: number | null; source_row_id?: number | null; category: string; reason_code: string; safe_detail: string; candidate_key: string; display_name?: string | null };
type Preview = { source_batch_id: number; source_batch_status: string; preview_fingerprint: string; counts: Record<string, number>; eligible: Candidate[]; blockers: Blocker[] };
type Frozen = { stage0_cohort_run_id: number; replay: boolean; counts: Record<string, number> };
type Cohort = { run: { stage0_cohort_run_id: number; run_kind: string; source_batch_id: number; source_batch_status: string; frozen_at: string; preview_fingerprint: string }; participants: Candidate[] };

const reasonLabels: Record<string, string> = {
  STAGE0_SOURCE_EMPLOYEE_MISSING: "Источник не связан с сотрудником.",
  STAGE0_EMPLOYEE_NOT_ACTIVE: "Сотрудник не является активным.",
  STAGE0_EMPLOYEE_PERSON_MISSING: "Нет однозначной связи Employee → Person.",
  STAGE0_PERSON_NOT_ACTIVE: "Person объединён, удалён или неактивен.",
  STAGE0_MULTIPLE_OPERATIONAL_EMPLOYEES: "У Person несколько активных operational Employee.",
  STAGE0_SOURCE_ANCHOR_NOT_UNIQUE: "В контрольном списке найдено несколько source anchor для сотрудника.",
  STAGE0_BATCH_PENDING_REMOVALS: "В batch есть неурегулированные удаления; FREEZE запрещён.",
  STAGE0_PPR_LIFECYCLE_NOT_MATERIALIZABLE: "Lifecycle PPR не допускает materialization/start collection.",
};

function apiMessage(error: any): string {
  return String(error?.details?.message ?? error?.message ?? "Не удалось выполнить запрос.");
}

function personLabel(row: { display_name?: string | null; employee_id?: number | null; person_id?: number | null }): string {
  const name = String(row.display_name ?? "").trim();
  const ids = `Employee #${row.employee_id ?? "—"} · Person #${row.person_id ?? "—"}`;
  return name ? `${name} (${ids})` : ids;
}

export default function PprMigrationPageClient() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [batchId, setBatchId] = useState<number | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [cohort, setCohort] = useState<Cohort | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    void (async () => {
      try {
        const me: MeInfo = await apiAuthMe();
        if (String(me.role_code ?? "").toUpperCase() !== "HR_HEAD") { setMessage("Доступ к Stage 0 разрешён только HR_HEAD."); return; }
        const response = await apiFetchJson<{ items: Batch[] }>("/personnel/ppr-migration/stage-0/source-batches");
        setBatches(response.items);
        if (response.items[0]) setBatchId(response.items[0].batch_id);
      } catch (error) { setMessage(apiMessage(error)); }
      finally { setLoading(false); }
    })();
  }, []);

  async function runPreview() {
    if (!batchId) return;
    setBusy(true); setMessage(""); setCohort(null);
    try {
      const result = await apiFetchJson<Preview>("/personnel/ppr-migration/stage-0/preview", { method: "POST", body: { source_batch_id: batchId, correction_details: true } });
      setPreview(result);
      setMessage("PREVIEW завершён. Данные не записывались.");
    } catch (error) { setMessage(apiMessage(error)); }
    finally { setBusy(false); }
  }

  async function freeze() {
    if (!preview) return;
    setBusy(true); setMessage("");
    try {
      const result = await apiFetchJson<Frozen>("/personnel/ppr-migration/stage-0/freeze", { method: "POST", body: { source_batch_id: preview.source_batch_id, preview_fingerprint: preview.preview_fingerprint } });
      const saved = await apiFetchJson<Cohort>(`/personnel/ppr-migration/stage-0/runs/${result.stage0_cohort_run_id}?correction_details=true`);
      setCohort(saved);
      setMessage(result.replay ? `Сохранённый cohort #${result.stage0_cohort_run_id} открыт повторно (replay).` : `Cohort #${result.stage0_cohort_run_id} зафиксирован (FROZEN).`);
    } catch (error) { setMessage(apiMessage(error)); }
    finally { setBusy(false); }
  }

  if (loading) return <div className="rounded-xl border border-zinc-200 bg-white p-4 text-sm dark:border-zinc-800 dark:bg-zinc-900">Загрузка Stage 0…</div>;
  return <main className="space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-3 border-b border-zinc-200 pb-4 dark:border-zinc-800">
      <div><p className="text-sm text-zinc-500">Программа миграции личных карточек</p><h1 className="text-2xl font-semibold">Stage 0 — подготовка и frozen cohort</h1><p className="mt-1 max-w-3xl text-sm text-zinc-600 dark:text-zinc-400">PREVIEW только проверяет. FREEZE сохраняет metadata, допущенных участников и blocker report; данные карточек не переносятся.</p></div>
      <span className="rounded-full border border-blue-300 bg-blue-50 px-3 py-1 text-sm font-medium text-blue-900 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-100">Роль: HR_HEAD</span>
    </header>
    <section className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <label className="block text-sm font-medium" htmlFor="stage0-batch">Контрольный список</label>
      <div className="mt-2 flex flex-wrap items-center gap-3"><select id="stage0-batch" value={batchId ?? ""} onChange={(e) => { setBatchId(Number(e.target.value)); setPreview(null); setCohort(null); }} className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950">
        {batches.length === 0 ? <option value="">Нет batch в допустимом статусе</option> : batches.map((batch) => <option key={batch.batch_id} value={batch.batch_id}>Batch #{batch.batch_id} · {batch.status} · строк: {batch.source_row_count}</option>)}</select>
        <button type="button" onClick={runPreview} disabled={!batchId || busy} className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{busy ? "Выполняется…" : "Запустить PREVIEW"}</button>
        <span className="text-sm text-zinc-500">Полный ИИН не отображается.</span></div>
    </section>
    {message ? <div role="status" className="rounded-lg border border-zinc-300 bg-zinc-50 px-4 py-3 text-sm dark:border-zinc-700 dark:bg-zinc-950">{message}</div> : null}
    {preview ? <section className="space-y-4"><div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Итог PREVIEW</h2><p className="text-sm text-zinc-600 dark:text-zinc-400">Batch #{preview.source_batch_id}, статус источника: {preview.source_batch_status}. Fingerprint: <span className="font-mono text-xs">{preview.preview_fingerprint.slice(0, 12)}…</span></p></div><button type="button" onClick={freeze} disabled={busy} className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Зафиксировать cohort (FREEZE)</button></div><div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{Object.entries(preview.counts).map(([status, count]) => <div key={status} className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-700"><div className="font-medium">{status === "ELIGIBLE" ? "Допущены" : status}</div><div className="text-2xl font-semibold">{count}</div></div>)}</div></div>
      <CandidateTable title="Допущенные сотрудники" items={preview.eligible} />
      <BlockerTable items={preview.blockers} />
    </section> : null}
    {cohort ? <section className="rounded-xl border border-emerald-300 bg-emerald-50 p-4 dark:border-emerald-900 dark:bg-emerald-950/25"><h2 className="text-lg font-semibold">Сохранённый cohort #{cohort.run.stage0_cohort_run_id}</h2><p className="text-sm">Статус: FROZEN · batch #{cohort.run.source_batch_id} · сохранён: {new Date(cohort.run.frozen_at).toLocaleString("ru-RU")}</p><CandidateTable title="Участники сохранённого cohort" items={cohort.participants} /></section> : null}
  </main>;
}

function CandidateTable({ title, items }: { title: string; items: Candidate[] }) { return <section className="overflow-hidden rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"><h2 className="border-b border-zinc-200 px-4 py-3 text-lg font-semibold dark:border-zinc-800">{title} — {items.length}</h2><div className="overflow-x-auto"><table className="min-w-full text-sm"><thead className="bg-zinc-100 text-left dark:bg-zinc-950"><tr><th className="px-3 py-2">Позиция</th><th className="px-3 py-2">Сотрудник</th><th className="px-3 py-2">Source row</th><th className="px-3 py-2">Статус</th></tr></thead><tbody>{items.length ? items.map((item) => <tr key={`${item.employee_id}-${item.source_row_id}`} className="border-t border-zinc-200 dark:border-zinc-800"><td className="px-3 py-2">{item.position ?? "—"}</td><td className="px-3 py-2">{personLabel(item)}</td><td className="px-3 py-2">#{item.source_row_id}</td><td className="px-3 py-2">Допущен (ELIGIBLE)</td></tr>) : <tr><td colSpan={4} className="px-3 py-5 text-center text-zinc-500">Нет допущенных сотрудников.</td></tr>}</tbody></table></div></section>; }
function BlockerTable({ items }: { items: Blocker[] }) { return <section className="overflow-hidden rounded-xl border border-amber-300 bg-white dark:border-amber-900 dark:bg-zinc-900"><h2 className="border-b border-amber-200 px-4 py-3 text-lg font-semibold dark:border-amber-900">Заблокированные сотрудники — {items.length}</h2><div className="overflow-x-auto"><table className="min-w-full text-sm"><thead className="bg-amber-50 text-left dark:bg-amber-950/30"><tr><th className="px-3 py-2">Сотрудник</th><th className="px-3 py-2">Причина</th><th className="px-3 py-2">Технический код</th></tr></thead><tbody>{items.length ? items.map((item) => <tr key={`${item.candidate_key}-${item.reason_code}`} className="border-t border-zinc-200 dark:border-zinc-800"><td className="px-3 py-2">{personLabel(item)}</td><td className="px-3 py-2">{reasonLabels[item.reason_code] ?? item.safe_detail}</td><td className="px-3 py-2 font-mono text-xs">{item.reason_code}</td></tr>) : <tr><td colSpan={3} className="px-3 py-5 text-center text-zinc-500">Нет blockers.</td></tr>}</tbody></table></div></section>; }
