"use client";

import * as React from "react";
import { apiFetchJson } from "@/lib/api";
import type { PprStatusFactResponse } from "../_lib/pprQueryTypes";

type PensionRow = Pick<PprStatusFactResponse, "status_fact_id" | "version" | "effective_date" | "pension_kind">;
type DisabilityRow = Pick<PprStatusFactResponse, "status_fact_id" | "version" | "effective_date" | "disability_group" | "icd10_code">;

function pensionRows(facts: PprStatusFactResponse[]): PensionRow[] {
  return facts.filter((fact) => fact.fact_kind === "PENSION").map((fact) => ({
    status_fact_id: fact.status_fact_id, version: fact.version, effective_date: fact.effective_date, pension_kind: fact.pension_kind,
  }));
}
function disabilityRows(facts: PprStatusFactResponse[]): DisabilityRow[] {
  return facts.filter((fact) => fact.fact_kind === "DISABILITY").map((fact) => ({
    status_fact_id: fact.status_fact_id, version: fact.version, effective_date: fact.effective_date,
    disability_group: fact.disability_group, icd10_code: fact.icd10_code,
  }));
}

export default function PprAdditionalStatusFactsEditor({ personId, facts, onSaved }: {
  personId: number; facts: PprStatusFactResponse[]; onSaved: () => void;
}) {
  const [pension, setPension] = React.useState<PensionRow[]>(() => pensionRows(facts));
  const [disability, setDisability] = React.useState<DisabilityRow[]>(() => disabilityRows(facts));
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function save() {
    setSaving(true); setError(null);
    try {
      await apiFetchJson(`/directory/personnel/migration-status/persons/${personId}/additional-status-facts`, {
        method: "PUT", body: {
          pension_rows: pension,
          disability_rows: disability,
          expected_fact_ids: facts.map((fact) => fact.status_fact_id),
        },
      });
      onSaved();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось сохранить примечание.");
    } finally { setSaving(false); }
  }

  return <div className="space-y-6" data-testid="ppr-additional-status-facts-editor">
    <section className="space-y-2">
      <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Пенсионный статус</h4>
      <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
        <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800">
          <thead className="bg-zinc-50 dark:bg-zinc-900/60"><tr>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Вид</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Дата установления</th>
            <th className="px-3 py-2"><span className="sr-only">Действия</span></th>
          </tr></thead>
          <tbody>{pension.map((row, index) => <tr key={row.status_fact_id ?? `new-pension-${index}`}>
            <td className="px-3 py-2"><select aria-label={`Вид пенсионного статуса ${index + 1}`} value={row.pension_kind ?? ""} onChange={(event) => setPension(pension.map((item, i) => i === index ? {...item, pension_kind: event.target.value || null} : item))} className="w-full rounded border border-zinc-300 bg-white p-1.5 dark:border-zinc-700 dark:bg-zinc-950">
              <option value="">Не указан</option><option value="AGE">По возрасту</option><option value="SERVICE">За выслугу лет</option>
            </select></td>
            <td className="px-3 py-2"><input aria-label={`Дата пенсионного статуса ${index + 1}`} type="date" value={row.effective_date ?? ""} onChange={(event) => setPension(pension.map((item, i) => i === index ? {...item, effective_date: event.target.value || null} : item))} className="w-full rounded border border-zinc-300 bg-white p-1.5 dark:border-zinc-700 dark:bg-zinc-950" /></td>
            <td className="px-3 py-2"><button type="button" onClick={() => setPension(pension.filter((_, i) => i !== index))} className="text-sm text-red-700 underline">Удалить</button></td>
          </tr>)}</tbody>
        </table>
      </div>
      <button type="button" onClick={() => setPension([...pension, { status_fact_id: undefined as never, version: undefined as never, pension_kind: null, effective_date: null }])} className="text-sm font-medium text-blue-700 underline">Добавить пенсионный статус</button>
    </section>

    <section className="space-y-2">
      <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Инвалидность</h4>
      <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
        <table className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800">
          <thead className="bg-zinc-50 dark:bg-zinc-900/60"><tr>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Группа</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Дата установления</th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500">Код заболевания по МКБ-10</th>
            <th className="px-3 py-2"><span className="sr-only">Действия</span></th>
          </tr></thead>
          <tbody>{disability.map((row, index) => <tr key={row.status_fact_id ?? `new-disability-${index}`}>
            <td className="px-3 py-2"><select aria-label={`Группа инвалидности ${index + 1}`} value={row.disability_group ?? ""} onChange={(event) => setDisability(disability.map((item, i) => i === index ? {...item, disability_group: event.target.value || null} : item))} className="w-full rounded border border-zinc-300 bg-white p-1.5 dark:border-zinc-700 dark:bg-zinc-950"><option value="">Не указана</option><option value="I">1</option><option value="II">2</option><option value="III">3</option></select></td>
            <td className="px-3 py-2"><input aria-label={`Дата инвалидности ${index + 1}`} type="date" value={row.effective_date ?? ""} onChange={(event) => setDisability(disability.map((item, i) => i === index ? {...item, effective_date: event.target.value || null} : item))} className="w-full rounded border border-zinc-300 bg-white p-1.5 dark:border-zinc-700 dark:bg-zinc-950" /></td>
            <td className="px-3 py-2"><input aria-label={`Код МКБ-10 ${index + 1}`} value={row.icd10_code ?? ""} onChange={(event) => setDisability(disability.map((item, i) => i === index ? {...item, icd10_code: event.target.value.toUpperCase() || null} : item))} className="w-full rounded border border-zinc-300 bg-white p-1.5 dark:border-zinc-700 dark:bg-zinc-950" /></td>
            <td className="px-3 py-2"><button type="button" onClick={() => setDisability(disability.filter((_, i) => i !== index))} className="text-sm text-red-700 underline">Удалить</button></td>
          </tr>)}</tbody>
        </table>
      </div>
      <button type="button" onClick={() => setDisability([...disability, { status_fact_id: undefined as never, version: undefined as never, disability_group: null, effective_date: null, icd10_code: null }])} className="text-sm font-medium text-blue-700 underline">Добавить запись об инвалидности</button>
    </section>
    <div className="flex items-center gap-3"><button type="button" onClick={() => void save()} disabled={saving} className="rounded bg-blue-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-60">{saving ? "Сохранение…" : "Сохранить примечание"}</button>{error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}</div>
  </div>;
}
