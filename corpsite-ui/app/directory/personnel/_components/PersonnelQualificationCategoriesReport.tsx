"use client";

import Link from "next/link";
import * as React from "react";

import { buildPprMigrationCardHref } from "@/lib/employeeCardNav";

export type QualificationCategory = {
  specialty: string;
  category: string;
  category_label: string;
  valid_until: string | null;
  status: string;
  status_label: string;
  document_status: string;
};
export type QualificationEmployee = {
  employee_id: number;
  person_id: number | null;
  full_name: string;
  org_unit_id: number | null;
  org_unit_name: string | null;
  categories: QualificationCategory[];
  pending_categories: string[];
};
export type QualificationCategoriesReportData = { as_of_date: string; employees: QualificationEmployee[] };

export function qualificationEmployeesInUnit(report: QualificationCategoriesReportData | null, unitId: string): QualificationEmployee[] {
  return (report?.employees ?? []).filter((employee) => !unitId || String(employee.org_unit_id) === unitId);
}

export function qualificationUnitOptions(report: QualificationCategoriesReportData | null): Array<[number, string]> {
  const unique = new Map<number, string>();
  for (const employee of report?.employees ?? []) {
    if (employee.org_unit_id != null) unique.set(employee.org_unit_id, employee.org_unit_name || `№ ${employee.org_unit_id}`);
  }
  return [...unique].sort((a, b) => a[1].localeCompare(b[1], "ru"));
}

const STATUS_OPTIONS = [
  ["ACTIVE", "Действует"],
  ["EXPIRING_SOON", "Скоро истекает"],
  ["EXPIRED", "Истекла"],
  ["NO_EXPIRY", "Срок не указан"],
  ["NO_CATEGORY", "Категория не внесена"],
] as const;

const STATUS_COLORS: Record<string, string> = {
  ACTIVE: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  EXPIRING_SOON: "bg-yellow-100 text-yellow-900 dark:bg-yellow-950 dark:text-yellow-200",
  EXPIRED: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  NO_EXPIRY: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200",
  NO_CATEGORY: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-200",
};

type Props = {
  report: QualificationCategoriesReportData | null;
  error: string | null;
  unitId: string;
  onUnitIdChange: (unitId: string) => void;
};

export default function PersonnelQualificationCategoriesReport({ report, error, unitId, onUnitIdChange }: Props) {
  const [search, setSearch] = React.useState("");
  const [status, setStatus] = React.useState("");

  const units = React.useMemo(() => qualificationUnitOptions(report), [report]);
  const employees = React.useMemo(() => qualificationEmployeesInUnit(report, unitId).filter((employee) =>
    employee.full_name.toLocaleLowerCase("ru").includes(search.trim().toLocaleLowerCase("ru")) &&
    (!status || employee.categories.some((category) => category.status === status))
  ), [report, search, unitId, status]);

  return <section className="space-y-4" aria-label="Квалификационные категории сотрудников" data-testid="qualification-categories-report">
    <div>
      <h2 className="text-xl font-semibold">Квалификационные категории</h2>
      <p className="text-sm text-zinc-500">Срок показан только если он указан в карточке. Наличие подтверждающего файла в записи категории пока не определяется. «На оформлении» означает связанный черновик приказа или приказ на подписи.</p>
      {report ? <p className="text-sm text-zinc-500">На дату {report.as_of_date}</p> : null}
    </div>
    {error ? <p role="alert">{error}</p> : null}
    {!report && !error ? <p role="status">Загрузка…</p> : null}
    {report ? <>
      <div className="flex flex-wrap gap-3">
        <input aria-label="Поиск по ФИО" placeholder="Поиск по ФИО" value={search} onChange={(event) => setSearch(event.target.value)} className="rounded border px-3 py-2 text-sm" />
        <select aria-label="Подразделение" value={unitId} onChange={(event) => onUnitIdChange(event.target.value)} className="rounded border px-3 py-2 text-sm">
          <option value="">Все подразделения</option>
          {units.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select>
        <select aria-label="Статус категории" value={status} onChange={(event) => setStatus(event.target.value)} className="rounded border px-3 py-2 text-sm">
          <option value="">Все статусы</option>
          {STATUS_OPTIONS.map(([code, label]) => <option key={code} value={code}>{label}</option>)}
        </select>
      </div>
      <div className="overflow-x-auto rounded-lg border">
        <table className="min-w-full divide-y text-left text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-900"><tr>
            {(["Сотрудник", "Подразделение", "Квалификационная категория", "Действует до", "Статус", "Подтверждающий документ"] as const).map((title) => <th key={title} className="p-3 font-semibold">{title}</th>)}
          </tr></thead>
          <tbody className="divide-y">{employees.map((employee) => <tr key={employee.employee_id} data-testid={`qualification-category-employee-${employee.employee_id}`}>
            <td className="p-3 align-top">{employee.person_id ? <Link className="text-blue-700 underline" href={buildPprMigrationCardHref(employee.person_id, "category")}>{employee.full_name}</Link> : employee.full_name}</td>
            <td className="p-3 align-top">{employee.org_unit_name || "—"}</td>
            <td className="p-3 align-top">{employee.categories.map((category, index) => <div key={index}>{category.category_label}{category.specialty ? ` · ${category.specialty}` : ""}</div>)}
              {employee.pending_categories?.map((name) => <div key={name} className="mt-1"><span>{name}</span> <span className="rounded bg-blue-100 px-2 py-0.5 text-blue-800 dark:bg-blue-950 dark:text-blue-200">На оформлении</span></div>)}
            </td>
            <td className="p-3 align-top">{employee.categories.map((category, index) => <div key={index}>{category.valid_until || "—"}</div>)}</td>
            <td className="p-3 align-top">{employee.categories.map((category, index) => <div key={index}><span className={`inline-block rounded px-2 py-0.5 ${STATUS_COLORS[category.status] || STATUS_COLORS.NO_EXPIRY}`}>{category.status_label}</span></div>)}</td>
            <td className="p-3 align-top">{employee.categories.map((category, index) => <div key={index}>{category.document_status}</div>)}</td>
          </tr>)}</tbody>
        </table>
      </div>
      {employees.length === 0 ? <p>Сотрудники по заданным фильтрам не найдены.</p> : null}
    </> : null}
  </section>;
}
