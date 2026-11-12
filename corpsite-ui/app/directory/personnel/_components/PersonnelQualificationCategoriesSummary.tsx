"use client";

import * as React from "react";

import {
  qualificationEmployeesInUnit,
  qualificationUnitOptions,
  type QualificationCategoriesReportData,
  type QualificationEmployee,
} from "./PersonnelQualificationCategoriesReport";

const STATUS_METRICS = [
  ["ACTIVE", "Действует"],
  ["EXPIRING_SOON", "Скоро истекает"],
  ["EXPIRED", "Истекла"],
  ["NO_EXPIRY", "Срок не указан"],
  ["NO_CATEGORY", "Категория не внесена"],
] as const;

const CATEGORY_LEVELS = [
  ["highest", "Высшая"],
  ["first", "Первая"],
  ["second", "Вторая"],
] as const;

function calendarDay(iso: string | null | undefined): number | null {
  if (!iso || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null;
  const milliseconds = Date.parse(`${iso}T00:00:00Z`);
  if (!Number.isFinite(milliseconds) || new Date(milliseconds).toISOString().slice(0, 10) !== iso) return null;
  // UTC is used only for calendar-day arithmetic. The date itself comes from
  // Corpsite's local as_of_date, not from the browser's timezone.
  return milliseconds / 86_400_000;
}

export function qualificationCategoryDetailedTables(employees: QualificationEmployee[], asOfDate: string) {
  const today = calendarDay(asOfDate);
  const unique = (matches: (employee: QualificationEmployee) => boolean) =>
    new Set(employees.filter(matches).map((employee) => employee.employee_id)).size;
  const hasExpiryWithin = (employee: QualificationEmployee, days: number) => employee.categories.some((category) => {
    if (!category.category || today == null) return false;
    const expiry = calendarDay(category.valid_until);
    return expiry != null && expiry >= today && expiry <= today + days;
  });
  return {
    levels: [
      ...CATEGORY_LEVELS.map(([code, label]) => ({ code, label, all: unique((employee) => employee.categories.some((category) => category.category === code)) })),
      { code: "NO_CATEGORY", label: "Категория не внесена", all: qualificationCategorySummary(employees).statuses.NO_CATEGORY },
    ],
    expiry: [
      { code: "WITHIN_30", label: "В течение 30 дней", all: unique((employee) => hasExpiryWithin(employee, 30)) },
      { code: "WITHIN_90", label: "В течение 90 дней", all: unique((employee) => hasExpiryWithin(employee, 90)) },
      { code: "NO_EXPIRY", label: "Дата окончания не указана", all: unique((employee) => employee.categories.some((category) => Boolean(category.category) && category.status === "NO_EXPIRY")) },
    ],
  };
}

export function qualificationCategorySummary(employees: QualificationEmployee[]) {
  const unique = (matches: (employee: QualificationEmployee) => boolean) =>
    new Set(employees.filter(matches).map((employee) => employee.employee_id)).size;
  return {
    total: unique(() => true),
    statuses: Object.fromEntries(STATUS_METRICS.map(([code]) => [code, unique((employee) => employee.categories.some((category) => category.status === code))])) as Record<string, number>,
    pending: unique((employee) => employee.pending_categories?.length > 0),
  };
}

type Props = {
  report: QualificationCategoriesReportData | null;
  error: string | null;
  unitId: string;
  onUnitIdChange: (unitId: string) => void;
};

export default function PersonnelQualificationCategoriesSummary({ report, error, unitId, onUnitIdChange }: Props) {
  const units = React.useMemo(() => qualificationUnitOptions(report), [report]);
  const employees = React.useMemo(() => qualificationEmployeesInUnit(report, unitId), [report, unitId]);
  const counts = React.useMemo(() => qualificationCategorySummary(employees), [employees]);
  const detailed = React.useMemo(() => qualificationCategoryDetailedTables(employees, report?.as_of_date || ""), [employees, report]);
  return <section className="space-y-4 px-4 pb-4" aria-label="Отчёт по квалификационным категориям" data-testid="qualification-categories-summary">
    <h1 className="text-xl font-semibold">Квалификационные категории — отчёт</h1>
    {error ? <p role="alert">{error}</p> : null}
    {!report && !error ? <p role="status">Загрузка…</p> : null}
    {report ? <>
      <select aria-label="Подразделение" value={unitId} onChange={(event) => onUnitIdChange(event.target.value)} className="rounded border px-3 py-2 text-sm">
        <option value="">Все подразделения</option>
        {units.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
      </select>
      <div className="max-w-2xl overflow-x-auto rounded-lg border">
        <table className="w-full divide-y text-left text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-900"><tr><th className="p-3 font-semibold">Показатель</th><th className="p-3 text-right font-semibold">Сотрудников</th></tr></thead>
          <tbody className="divide-y">
            <tr><td className="p-3">Всего сотрудников</td><td className="p-3 text-right font-semibold" data-testid="qualification-summary-total">{counts.total}</td></tr>
            {STATUS_METRICS.map(([code, label]) => <tr key={code}><td className="p-3">{label}</td><td className="p-3 text-right font-semibold" data-testid={`qualification-summary-${code}`}>{counts.statuses[code]}</td></tr>)}
            <tr><td className="p-3">На оформлении</td><td className="p-3 text-right font-semibold" data-testid="qualification-summary-pending">{counts.pending}</td></tr>
          </tbody>
        </table>
      </div>
      <p className="text-sm text-zinc-500">Сотрудник с несколькими категориями может учитываться в нескольких статусах. «На оформлении» учитывается отдельно.</p>
      {([
        ["По уровню категории", detailed.levels, "level"],
        ["Истекают в ближайшие 30 и 90 дней", detailed.expiry, "expiry"],
      ] as const).map(([title, rows, kind]) => <div key={kind} className="space-y-2">
        <h2 className="text-lg font-semibold">{title}</h2>
        <div className="max-w-3xl overflow-x-auto rounded-lg border">
          <table className="w-full divide-y text-left text-sm" data-testid={`qualification-${kind}-table`}>
            <thead className="bg-zinc-50 dark:bg-zinc-900"><tr>
              <th className="p-3 font-semibold">{kind === "level" ? "Категория" : "Срок"}</th>
              <th className="p-3 text-right font-semibold">Все сотрудники</th>
              <th className="p-3 text-right font-semibold">Врачи</th>
              <th className="p-3 text-right font-semibold">Медсёстры</th>
            </tr></thead>
            <tbody className="divide-y">{rows.map((row) => <tr key={row.code}>
              <td className="p-3">{row.label}</td>
              <td className="p-3 text-right font-semibold" data-testid={`qualification-${kind}-${row.code}-all`}>{row.all}</td>
              <td className="p-3 text-right text-zinc-500" aria-label="Нет классификации текущей должности">—</td>
              <td className="p-3 text-right text-zinc-500" aria-label="Нет классификации текущей должности">—</td>
            </tr>)}</tbody>
          </table>
        </div>
      </div>)}
      <p className="text-sm text-zinc-500">Для разбивки на врачей и медсестёр справочнику текущих должностей нужен проверенный признак группы персонала. Общая категория «medical» не различает эти группы; пустые колонки не означают ноль.</p>
    </> : null}
  </section>;
}
