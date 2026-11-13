"use client";

import * as React from "react";

import { apiFetchJson } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";

type Employee = { employee_id: number; full_name: string; departments: string[] };
type PositionRow = {
  position_id: number;
  name: string;
  type_code: number | null;
  type_name: string | null;
  is_active: boolean | null;
  employee_count: number;
  employees: Employee[];
  possible_duplicate_ids: number[];
};
type AssignmentName = {
  name: string;
  normalized_name: string;
  employee_count: number;
  employees: Employee[];
  positions: Array<{
    position_id: number;
    name: string;
    employee_count: number;
    employees: Employee[];
  }>;
  possible_duplicate_ids: number[];
};
type Report = {
  as_of: string;
  independent_assignment_name_available: boolean;
  position_active_flag_available: boolean;
  metrics: {
    assignment_names: number;
    catalog_positions: number;
    active_catalog_positions: number | null;
    inactive_catalog_positions: number | null;
    assignment_names_missing_in_catalog: number | null;
    catalog_without_active_assignments: number;
  };
  assignment_names: AssignmentName[];
  catalog_positions: PositionRow[];
  assignment_names_missing_in_catalog: [];
  catalog_without_active_assignments: PositionRow[];
  missing_position_references: Array<{
    position_id: number;
    employee_count: number;
    employees: Employee[];
  }>;
};

type Section = "assignment_names" | "catalog_positions" | "missing_names" | "unused_positions";

function EmployeeList({ employees }: { employees: Employee[] }) {
  if (!employees.length) return <p className="text-xs text-zinc-500">Действующих сотрудников нет.</p>;
  return (
    <ul className="mt-2 space-y-1 pl-4 text-xs text-zinc-700 dark:text-zinc-300">
      {employees.map((employee) => (
        <li key={employee.employee_id} className="list-disc">
          {employee.full_name}
          {employee.departments.length ? ` — ${employee.departments.join(", ")}` : " — отделение не указано"}
        </li>
      ))}
    </ul>
  );
}

function PositionList({ positions }: { positions: PositionRow[] }) {
  return (
    <div className="space-y-2" data-testid="position-report-position-list">
      {positions.length === 0 ? <p className="text-sm text-zinc-600">Записей нет.</p> : null}
      {positions.map((position) => (
        <details key={position.position_id} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <summary className="cursor-pointer text-sm font-medium">
            <span className="mr-2 text-zinc-500">ID {position.position_id}</span>
            {position.name}
            <span className="ml-2 text-xs font-normal text-zinc-600 dark:text-zinc-400">
              · {position.type_name ?? "Тип не указан"} · сотрудников: {position.employee_count}
            </span>
            {position.possible_duplicate_ids.length ? (
              <span className="ml-2 text-xs font-normal text-amber-700 dark:text-amber-300">
                Возможный дубль названия: ID {position.possible_duplicate_ids.join(", ")}
              </span>
            ) : null}
          </summary>
          <EmployeeList employees={position.employees} />
        </details>
      ))}
    </div>
  );
}

export default function PositionAssignmentReport() {
  const [report, setReport] = React.useState<Report | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [section, setSection] = React.useState<Section | null>(null);

  const reload = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    setReport(null);
    setSection(null);
    try {
      setReport(await apiFetchJson<Report>("/directory/personnel/reports/position-assignment-reconciliation"));
    } catch (err) {
      setError(formatThrownError(err, { fallback: "Не удалось загрузить отчёт." }));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { void reload(); }, [reload]);

  const cards: Array<{ key: Section; title: string; value: number | string; note?: string }> = report ? [
    {
      key: "assignment_names",
      title: "Должности справочника, которые сейчас занимают сотрудники",
      value: report.metrics.assignment_names,
      note: "Одно и то же название должности в разных отделениях считается один раз",
    },
    {
      key: "catalog_positions", title: "Позиций в справочнике", value: report.metrics.catalog_positions,
      note: report.position_active_flag_available
        ? `Активных: ${report.metrics.active_catalog_positions} · неактивных: ${report.metrics.inactive_catalog_positions}`
        : "У позиции нет отдельного признака активности",
    },
    {
      key: "missing_names", title: "Названия из назначений, которых нет в справочнике",
      value: report.independent_assignment_name_available
        ? (report.metrics.assignment_names_missing_in_catalog ?? 0) : "Н/Д",
      note: report.independent_assignment_name_available ? undefined : "В назначении хранится только ID позиции",
    },
    { key: "unused_positions", title: "Позиции справочника без действующих назначений", value: report.metrics.catalog_without_active_assignments },
  ] : [];

  return (
    <section className="mx-auto w-full max-w-[1440px] space-y-4 px-4 py-4" aria-label="Сверка должностей с назначениями сотрудников">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Сверка должностей с назначениями сотрудников</h2>
          <p className="mt-1 max-w-3xl text-sm text-zinc-600 dark:text-zinc-400">
            Действующие основные и дополнительные назначения действующих сотрудников. Название в назначении отдельно не хранится:
            оно показано по ID позиции из справочника и не служит независимым подтверждением совпадения названий.
          </p>
          {report ? <p className="mt-1 text-xs text-zinc-500">По состоянию на {report.as_of}</p> : null}
        </div>
        <button type="button" onClick={() => void reload()} disabled={loading}
          className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm disabled:opacity-50 dark:border-zinc-700">
          Обновить
        </button>
      </div>

      {loading ? <p role="status" className="text-sm">Загрузка отчёта…</p> : null}
      {error ? <p role="alert" className="rounded-lg border border-red-200 p-3 text-sm text-red-700">{error}</p> : null}
      {report ? (
        <>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {cards.map((card) => (
              <button key={card.key} type="button" onClick={() => setSection(section === card.key ? null : card.key)}
                aria-expanded={section === card.key}
                className={`rounded-xl border p-4 text-left transition hover:bg-zinc-50 dark:hover:bg-zinc-900 ${section === card.key ? "border-blue-500" : "border-zinc-200 dark:border-zinc-800"}`}>
                <span className="block text-xs text-zinc-600 dark:text-zinc-400">{card.title}</span>
                <span className="mt-2 block text-2xl font-semibold">{card.value}</span>
                {card.note ? <span className="mt-1 block text-xs text-zinc-500">{card.note}</span> : null}
              </button>
            ))}
          </div>

          {section ? <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
            {section === "assignment_names" ? (
              <div className="space-y-2" data-testid="position-report-assignment-names">
                <h3 className="mb-3 font-semibold">Занимаемые должности · {report.assignment_names.length}</h3>
                {report.assignment_names.map((group) => (
                  <details key={group.normalized_name} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
                    <summary className="cursor-pointer text-sm font-medium">
                      {group.name} <span className="text-xs font-normal text-zinc-500">· сотрудников: {group.employee_count}</span>
                      {group.possible_duplicate_ids.length > 1 ? (
                        <span className="ml-2 text-xs font-normal text-amber-700 dark:text-amber-300">
                          Возможные дубли: ID {group.possible_duplicate_ids.join(", ")}
                        </span>
                      ) : null}
                    </summary>
                    <div className="mt-2 space-y-2 pl-2">
                      {group.positions.map((position) => (
                        <div key={position.position_id} className="rounded-md bg-zinc-50 p-2 text-xs dark:bg-zinc-900">
                          <div className="font-medium">ID {position.position_id} · {position.name} · сотрудников: {position.employee_count}</div>
                          <EmployeeList employees={position.employees} />
                        </div>
                      ))}
                    </div>
                  </details>
                ))}
              </div>
            ) : null}
            {section === "catalog_positions" ? (
              <div>
                <h3 className="mb-3 font-semibold">Позиции справочника · {report.catalog_positions.length}</h3>
                <PositionList positions={report.catalog_positions} />
              </div>
            ) : null}
            {section === "missing_names" ? (
              <div className="space-y-2 text-sm">
                <h3 className="font-semibold">Названия из назначений, которых нет в справочнике</h3>
                <p>Независимое сравнение названий недоступно: person_assignments хранит position_id, но не название должности.
                  Название берётся из позиции справочника по этому ID.</p>
                <p>Ссылок на отсутствующую позицию: {report.missing_position_references.length}.</p>
                {report.missing_position_references.map((entry) => (
                  <div key={entry.position_id} className="rounded-lg border p-3">
                    ID позиции {entry.position_id} · сотрудников: {entry.employee_count}
                    <EmployeeList employees={entry.employees} />
                  </div>
                ))}
              </div>
            ) : null}
            {section === "unused_positions" ? (
              <div>
                <h3 className="mb-1 font-semibold">Позиции без действующих назначений · {report.catalog_without_active_assignments.length}</h3>
                <p className="mb-3 text-xs text-amber-700 dark:text-amber-300">
                  Отсутствие действующих назначений не означает, что позицию можно удалить: она может использоваться в истории.
                </p>
                <PositionList positions={report.catalog_without_active_assignments} />
              </div>
            ) : null}
          </div> : null}
        </>
      ) : null}
    </section>
  );
}
