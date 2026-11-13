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

const LEVEL_NAMES: Record<string, string> = Object.fromEntries(CATEGORY_LEVELS);
const TYPE_NAMES: Record<number, string> = {
  1: "Врачи", 2: "Медсёстры и фельдшеры", 3: "Санитарки", 4: "Прочий персонал",
};

function uniqueEmployees(employees: QualificationEmployee[]): QualificationEmployee[] {
  return [...new Map(employees.map((employee) => [employee.employee_id, employee])).values()];
}

function isReportEmployee(employee: QualificationEmployee): boolean {
  return employee.type_code === 1 || employee.type_code === 2;
}

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
  const selected = uniqueEmployees(employees);
  const metric = (code: string, label: string, matches: (employee: QualificationEmployee) => boolean) => {
    const matching = selected.filter(matches);
    const doctors = matching.filter((employee) => employee.type_code === 1).length;
    const nurses = matching.filter((employee) => employee.type_code === 2).length;
    return {
      code, label, all: doctors + nurses, doctors, nurses,
      excluded: matching.filter((employee) => !isReportEmployee(employee)),
    };
  };
  const hasExpiryWithin = (employee: QualificationEmployee, days: number) => employee.categories.some((category) => {
    if (!category.category || today == null) return false;
    const expiry = calendarDay(category.valid_until);
    return expiry != null && expiry >= today && expiry <= today + days;
  });
  return {
    levels: [
      ...CATEGORY_LEVELS.map(([code, label]) => metric(code, label, (employee) => employee.categories.some((category) => category.category === code))),
      metric("NO_CATEGORY", "Категория не внесена", (employee) => employee.categories.some((category) => category.status === "NO_CATEGORY")),
    ],
    expiry: [
      metric("WITHIN_30", "В течение 30 дней", (employee) => hasExpiryWithin(employee, 30)),
      metric("WITHIN_90", "В течение 90 дней", (employee) => hasExpiryWithin(employee, 90)),
      metric("NO_EXPIRY", "Дата окончания не указана", (employee) => employee.categories.some((category) => Boolean(category.category) && category.status === "NO_EXPIRY")),
    ],
  };
}

export function qualificationCategorySummary(employees: QualificationEmployee[]) {
  const reportEmployees = uniqueEmployees(employees).filter(isReportEmployee);
  const unique = (matches: (employee: QualificationEmployee) => boolean) =>
    reportEmployees.filter(matches).length;
  const levelsFor = (employee: QualificationEmployee) => new Set(employee.categories
    .map((category) => category.category).filter((code) => Object.prototype.hasOwnProperty.call(LEVEL_NAMES, code)));
  return {
    total: unique(() => true),
    statuses: Object.fromEntries(STATUS_METRICS.map(([code]) => [code, unique((employee) => employee.categories.some((category) => category.status === code))])) as Record<string, number>,
    pending: unique((employee) => employee.pending_categories?.length > 0),
    withCategory: unique((employee) => employee.categories.some((category) => Boolean(category.category))),
    multipleLevels: reportEmployees.filter((employee) => levelsFor(employee).size > 1),
    repeatedSameLevel: reportEmployees.filter((employee) => {
      const codes = employee.categories.map((category) => category.category)
        .filter((code) => Object.prototype.hasOwnProperty.call(LEVEL_NAMES, code));
      return codes.length > new Set(codes).size;
    }),
    unmappedLevels: reportEmployees.filter((employee) => employee.categories.some((category) =>
      category.category && !Object.prototype.hasOwnProperty.call(LEVEL_NAMES, category.category))),
  };
}

type Props = {
  report: QualificationCategoriesReportData | null;
  error: string | null;
  unitId: string;
  onUnitIdChange: (unitId: string) => void;
};

function categoryText(employee: QualificationEmployee, levelCode?: string): string {
  if (levelCode === "NO_CATEGORY") return "Категория не внесена";
  const categories = employee.categories.filter((category) =>
    Boolean(category.category) && (!levelCode || category.category === levelCode));
  const labels = categories.map((category) =>
    `${LEVEL_NAMES[category.category] || category.category_label || category.category}${category.specialty ? ` — ${category.specialty}` : ""}`);
  return [...new Set(labels)].join("; ") || "Категория не внесена";
}

function EmployeeBreakdown({ employees, includeType = false, levelCode }: {
  employees: QualificationEmployee[]; includeType?: boolean; levelCode?: string;
}) {
  return <div className="overflow-x-auto p-3"><table className="w-full text-sm">
    <thead><tr className="text-left text-xs text-zinc-500">
      <th className="p-2">Сотрудник (ФИО)</th><th className="p-2">Должность</th>
      <th className="p-2">Отделение</th><th className="p-2">Категория</th>
      {includeType ? <th className="p-2">Тип</th> : null}
    </tr></thead>
    <tbody>{employees.map((employee) => <tr key={employee.employee_id} className="border-t">
      <td className="p-2">{employee.full_name}</td>
      <td className="p-2">{employee.position_name || "—"}</td>
      <td className="p-2">{employee.org_unit_name || "—"}</td>
      <td className="p-2">{categoryText(employee, levelCode)}</td>
      {includeType ? <td className="p-2">{TYPE_NAMES[employee.type_code ?? 0] || "Не указан"}</td> : null}
    </tr>)}</tbody>
  </table></div>;
}

export default function PersonnelQualificationCategoriesSummary({ report, error, unitId, onUnitIdChange }: Props) {
  const units = React.useMemo(() => qualificationUnitOptions(report), [report]);
  const employees = React.useMemo(() => qualificationEmployeesInUnit(report, unitId), [report, unitId]);
  const counts = React.useMemo(() => qualificationCategorySummary(employees), [employees]);
  const detailed = React.useMemo(() => qualificationCategoryDetailedTables(employees, report?.as_of_date || ""), [employees, report]);
  const levelSum = detailed.levels.filter((row) => row.code !== "NO_CATEGORY").reduce((sum, row) => sum + row.all, 0);
  const [expandedLevel, setExpandedLevel] = React.useState<string | null>(null);
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
          <thead className="bg-zinc-50 dark:bg-zinc-900"><tr><th className="p-3 font-semibold">Показатель</th><th className="p-3 text-right font-semibold">Сотрудников типов 1 и 2</th></tr></thead>
          <tbody className="divide-y">
            <tr><td className="p-3">Всего врачей, медсестёр и фельдшеров</td><td className="p-3 text-right font-semibold" data-testid="qualification-summary-total">{counts.total}</td></tr>
            {STATUS_METRICS.filter(([code]) => code !== "NO_CATEGORY").map(([code, label]) => <tr key={code}><td className="p-3">{label}</td><td className="p-3 text-right font-semibold" data-testid={`qualification-summary-${code}`}>{counts.statuses[code]}</td></tr>)}
            <tr><td className="p-3">На оформлении</td><td className="p-3 text-right font-semibold" data-testid="qualification-summary-pending">{counts.pending}</td></tr>
          </tbody>
        </table>
      </div>
      <details className="rounded border p-3" data-testid="qualification-multiple-levels-details">
        <summary className="cursor-pointer font-medium">Учтены в нескольких уровнях: {counts.multipleLevels.length}</summary>
        <EmployeeBreakdown employees={counts.multipleLevels} />
      </details>
      <p className="text-sm text-zinc-600" data-testid="qualification-level-difference">
        Сумма строк уровней: {levelSum}; уникальных сотрудников с категорией: {counts.withCategory}; разница: {levelSum - counts.withCategory}.
      </p>
      <details className="rounded border p-3" data-testid="qualification-repeated-level-details">
        <summary className="cursor-pointer font-medium">Повторные записи одного уровня: {counts.repeatedSameLevel.length}</summary>
        <EmployeeBreakdown employees={counts.repeatedSameLevel} />
      </details>
      {counts.unmappedLevels.length > 0 ? <details className="rounded border p-3">
        <summary className="cursor-pointer font-medium">Категории вне строк уровней: {counts.unmappedLevels.length}</summary>
        <EmployeeBreakdown employees={counts.unmappedLevels} />
      </details> : null}
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
              <th className="p-3 text-right font-semibold">Итого</th>
              <th className="p-3 text-right font-semibold">Врачи</th>
              <th className="p-3 text-right font-semibold">Медсёстры и фельдшеры</th>
              {kind === "level" ? <th className="p-3 text-right font-semibold">Исключено по типу</th> : null}
            </tr></thead>
            <tbody className="divide-y">{rows.map((row) => <React.Fragment key={row.code}><tr>
              <td className="p-3">{row.label}</td>
              <td className="p-3 text-right font-semibold" data-testid={`qualification-${kind}-${row.code}-all`}>{row.all}</td>
              <td className="p-3 text-right font-semibold" data-testid={`qualification-${kind}-${row.code}-doctors`}>{row.doctors}</td>
              <td className="p-3 text-right font-semibold" data-testid={`qualification-${kind}-${row.code}-nurses`}>{row.nurses}</td>
              {kind === "level" ? <td className="p-3 text-right"><button type="button"
                aria-label={`Показать исключённых: ${row.label}`}
                aria-expanded={expandedLevel === row.code}
                onClick={() => setExpandedLevel(expandedLevel === row.code ? null : row.code)}
                className="rounded px-2 py-1 font-semibold text-blue-700 hover:bg-blue-50"
                data-testid={`qualification-level-${row.code}-excluded`}>{row.excluded.length}</button></td> : null}
            </tr>
            {kind === "level" && expandedLevel === row.code ? <tr data-testid={`qualification-level-${row.code}-excluded-list`}>
              <td colSpan={5}><EmployeeBreakdown employees={row.excluded} includeType levelCode={row.code} /></td>
            </tr> : null}
            </React.Fragment>)}</tbody>
          </table>
        </div>
      </div>)}
    </> : null}
  </section>;
}
