"use client";

import * as React from "react";

import PersonnelOrdersSummaryReportPanel from "./PersonnelOrdersSummaryReport";
import {
  downloadPersonnelRoster,
  getPersonnelReportOptions,
  getPersonnelRoster,
  type PersonnelReportOptions,
  type PersonnelRosterFilters,
  type PersonnelRosterReport,
} from "../_lib/personnelReportsApi.client";

function errorMessage(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) return String(error.message);
  return "Не удалось сформировать отчёт.";
}

function parseFilter(value: string): number | undefined {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : undefined;
}

function formatRate(value: number): string {
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(value);
}

function PersonnelRosterReportPanel() {
  const [options, setOptions] = React.useState<PersonnelReportOptions>({ groups: [], departments: [] });
  const [groupId, setGroupId] = React.useState("");
  const [departmentId, setDepartmentId] = React.useState("");
  const [report, setReport] = React.useState<PersonnelRosterReport | null>(null);
  const [optionsLoading, setOptionsLoading] = React.useState(true);
  const [reportLoading, setReportLoading] = React.useState(false);
  const [downloading, setDownloading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    getPersonnelReportOptions()
      .then((data) => {
        if (!cancelled) setOptions(data);
      })
      .catch((reason) => {
        if (!cancelled) setError(errorMessage(reason));
      })
      .finally(() => {
        if (!cancelled) setOptionsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filters = React.useMemo<PersonnelRosterFilters>(
    () => ({ groupId: parseFilter(groupId), orgUnitId: parseFilter(departmentId) }),
    [departmentId, groupId],
  );

  React.useEffect(() => {
    if (optionsLoading || options.departments.length === 0) {
      setReport(null);
      setReportLoading(false);
      return;
    }
    let cancelled = false;
    setReportLoading(true);
    setError(null);
    getPersonnelRoster(filters)
      .then((data) => {
        if (!cancelled) setReport(data);
      })
      .catch((reason) => {
        if (!cancelled) {
          setReport(null);
          setError(errorMessage(reason));
        }
      })
      .finally(() => {
        if (!cancelled) setReportLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filters, options.departments.length, optionsLoading]);

  const departments = React.useMemo(
    () => options.departments.filter((item) => !groupId || String(item.group_id) === groupId),
    [options.departments, groupId],
  );

  function handleGroupChange(nextGroupId: string) {
    const currentDepartment = options.departments.find(
      (department) => String(department.unit_id) === departmentId,
    );
    const isCompatible =
      !nextGroupId || !currentDepartment || String(currentDepartment.group_id) === nextGroupId;
    setGroupId(nextGroupId);
    if (!isCompatible) setDepartmentId("");
    setError(null);
  }

  async function handleDownload() {
    if (options.departments.length === 0) return;
    setDownloading(true);
    setError(null);
    try {
      await downloadPersonnelRoster(filters);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setDownloading(false);
    }
  }

  const hasOptions = options.groups.length > 0 && options.departments.length > 0;

  return (
    <div className="space-y-5 px-4 py-5">
      <section className="grid gap-3 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800 md:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="font-medium">Группа отделений</span>
          <select
            aria-label="Группа отделений"
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
            value={groupId}
            disabled={optionsLoading || !hasOptions}
            onChange={(event) => handleGroupChange(event.target.value)}
          >
            <option value="">Все группы</option>
            {options.groups.map((group) => (
              <option key={group.group_id} value={group.group_id}>
                {group.group_name}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span className="font-medium">Отделение</span>
          <select
            aria-label="Отделение"
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 disabled:cursor-not-allowed disabled:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-950"
            value={departmentId}
            disabled={optionsLoading || !hasOptions}
            onChange={(event) => setDepartmentId(event.target.value)}
          >
            <option value="">Все отделения</option>
            {departments.map((department) => (
              <option key={department.unit_id} value={department.unit_id}>
                {department.unit_name}
              </option>
            ))}
          </select>
        </label>
      </section>

      <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">Отчёт</div>
          <div className="font-semibold">Личный состав</div>
        </div>
        <button
          type="button"
          disabled={!hasOptions || reportLoading || downloading}
          onClick={handleDownload}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {downloading ? "Формирование…" : "Скачать Excel"}
        </button>
      </section>

      <section className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
        <div className="border-b border-zinc-200 px-4 py-3 font-semibold dark:border-zinc-800">
          Предварительный просмотр
        </div>
        {error ? <div role="alert" className="px-4 py-8 text-center text-red-600">{error}</div> : null}
        {!error && (optionsLoading || reportLoading) ? (
          <div className="px-4 py-8 text-center text-zinc-500">Загрузка…</div>
        ) : null}
        {!error && !optionsLoading && !hasOptions ? (
          <div className="px-4 py-8 text-center text-zinc-500">
            Нет доступных групп или отделений.
          </div>
        ) : null}
        {!error && !optionsLoading && !reportLoading && hasOptions && report?.total === 0 ? (
          <div className="px-4 py-8 text-center text-zinc-500">
            Действующие сотрудники не найдены.
          </div>
        ) : null}
        {!error && !optionsLoading && !reportLoading && report && report.total > 0 ? (
          <div className="space-y-8 p-4">
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">Сводный состав по отделениям</h2>
              <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
                <table className="min-w-full text-sm">
                  <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
                    <tr>
                      <th className="w-16 px-4 py-3 text-right">№</th>
                      <th className="px-4 py-3">Группа отделений</th>
                      <th className="px-4 py-3">Отделение</th>
                      <th className="w-40 px-4 py-3 text-right">Количество человек</th>
                      <th className="w-40 px-4 py-3 text-right">Количество ставок</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.summary.map((item) => (
                      <tr key={item.department.id} className="border-t border-zinc-100 dark:border-zinc-800">
                        <td className="px-4 py-3 text-right">{item.number}</td>
                        <td className="px-4 py-3">{item.group.name}</td>
                        <td className="px-4 py-3">{item.department.name}</td>
                        <td className="px-4 py-3 text-right">{item.employee_count}</td>
                        <td className="px-4 py-3 text-right">{formatRate(item.rate_total)}</td>
                      </tr>
                    ))}
                    <tr className="border-t-2 border-zinc-300 font-semibold dark:border-zinc-700">
                      <td className="px-4 py-3" colSpan={3}>ВСЕГО</td>
                      <td className="px-4 py-3 text-right">{report.total}</td>
                      <td className="px-4 py-3 text-right">{formatRate(report.total_rate)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              {report.missing_rate_count > 0 ? (
                <p className="text-sm text-amber-700 dark:text-amber-300">
                  Ставка не указана у {report.missing_rate_count} сотрудников
                </p>
              ) : null}
            </div>

            <div className="space-y-5">
              <h2 className="text-lg font-semibold">Личный состав</h2>
              {report.groups.map((group) => (
                <section key={group.id} className="space-y-4">
                  <h3 className="rounded-lg bg-slate-700 px-4 py-2 text-base font-semibold text-white">
                    {group.name}
                  </h3>
                  {group.departments.map((department) => (
                    <div key={department.id} className="space-y-2">
                      <h4 className="rounded-md bg-blue-50 px-4 py-2 font-semibold text-blue-950 dark:bg-blue-950 dark:text-blue-100">
                        {department.name}
                      </h4>
                      <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
                        <table className="min-w-full text-sm">
                          <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
                            <tr>
                              <th className="w-16 px-4 py-3 text-right">№</th>
                              <th className="px-4 py-3">ФИО</th>
                              <th className="px-4 py-3">Должность</th>
                              <th className="w-28 px-4 py-3 text-right">Ставка</th>
                            </tr>
                          </thead>
                          <tbody>
                            {department.items.map((item) => (
                              <tr key={item.employee_id} className="border-t border-zinc-100 dark:border-zinc-800">
                                <td className="px-4 py-3 text-right">{item.number}</td>
                                <td className="px-4 py-3">{item.full_name}</td>
                                <td className="px-4 py-3">{item.position}</td>
                                <td className="px-4 py-3 text-right">{item.rate}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </section>
              ))}
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

type PersonnelReportDefinition = {
  id: string;
  label: string;
  Component: React.ComponentType;
};

type PersonnelReportSection = {
  id: string;
  label: string;
  reports: readonly PersonnelReportDefinition[];
};

const PERSONNEL_REPORT_SECTIONS = [
  {
    id: "personnel",
    label: "Персонал",
    reports: [
      {
        id: "personnel-roster",
        label: "Личный состав",
        Component: PersonnelRosterReportPanel,
      },
    ],
  },
  {
    id: "orders",
    label: "Приказы",
    reports: [
      {
        id: "orders-summary",
        label: "Общая сводка по приказам",
        Component: PersonnelOrdersSummaryReportPanel,
      },
    ],
  },
] as const satisfies readonly PersonnelReportSection[];

export default function PersonnelReportsPageClient() {
  const defaultSection = PERSONNEL_REPORT_SECTIONS[0];
  const [activeSectionId, setActiveSectionId] = React.useState<string>(defaultSection.id);
  const [activeReportId, setActiveReportId] = React.useState<string>(defaultSection.reports[0].id);
  const activeSection =
    PERSONNEL_REPORT_SECTIONS.find((section) => section.id === activeSectionId) ?? defaultSection;
  const activeReport =
    activeSection.reports.find((reportDefinition) => reportDefinition.id === activeReportId) ??
    activeSection.reports[0];
  const ActiveReportComponent = activeReport.Component;

  function selectSection(section: (typeof PERSONNEL_REPORT_SECTIONS)[number]) {
    setActiveSectionId(section.id);
    setActiveReportId(section.reports[0].id);
  }

  return (
    <div>
      <div className="space-y-3 px-4 pt-5">
        <section
          aria-labelledby="personnel-report-sections-heading"
          className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/60"
        >
          <h2
            id="personnel-report-sections-heading"
            className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500"
          >
            Раздел отчётов
          </h2>
          <div role="group" aria-labelledby="personnel-report-sections-heading" className="flex flex-wrap gap-3">
            {PERSONNEL_REPORT_SECTIONS.map((section) => {
              const isActive = section.id === activeSection.id;
              return (
                <button
                  key={section.id}
                  type="button"
                  aria-pressed={isActive}
                  onClick={() => selectSection(section)}
                  className="inline-flex min-w-36 items-center justify-between gap-3 rounded-lg border-2 border-zinc-300 bg-white px-4 py-2.5 font-semibold hover:border-zinc-400 aria-pressed:border-blue-700 aria-pressed:shadow-sm dark:border-zinc-700 dark:bg-zinc-950 dark:aria-pressed:border-blue-400"
                >
                  <span>{section.label}</span>
                  {isActive ? <span aria-hidden="true">✓</span> : null}
                </button>
              );
            })}
          </div>
        </section>

        <section
          aria-labelledby="personnel-section-reports-heading"
          className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800"
        >
          <h2 id="personnel-section-reports-heading" className="mb-3 text-sm font-medium text-zinc-600 dark:text-zinc-300">
            Отчёты раздела «{activeSection.label}»
          </h2>
          <div role="group" aria-labelledby="personnel-section-reports-heading" className="flex flex-wrap gap-2">
            {activeSection.reports.map((reportDefinition) => {
              const isActive = reportDefinition.id === activeReport.id;
              return (
                <button
                  key={reportDefinition.id}
                  type="button"
                  aria-pressed={isActive}
                  onClick={() => setActiveReportId(reportDefinition.id)}
                  className="inline-flex items-center gap-2 rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-50 aria-pressed:border-blue-600 aria-pressed:font-semibold aria-pressed:outline aria-pressed:outline-1 aria-pressed:outline-blue-600 dark:border-zinc-700 dark:hover:bg-zinc-900"
                >
                  {isActive ? <span aria-hidden="true">✓</span> : null}
                  <span>{reportDefinition.label}</span>
                </button>
              );
            })}
          </div>
        </section>
      </div>
      <ActiveReportComponent />
    </div>
  );
}
