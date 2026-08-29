"use client";

import * as React from "react";

import {
  downloadPersonnelRoster,
  getPersonnelReportOptions,
  getPersonnelRoster,
  type PersonnelReportOptions,
  type PersonnelRosterReport,
} from "../_lib/personnelReportsApi.client";

function errorMessage(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) return String(error.message);
  return "Не удалось сформировать отчёт.";
}

export default function PersonnelReportsPageClient() {
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

  React.useEffect(() => {
    const id = Number(departmentId);
    if (!Number.isSafeInteger(id) || id < 1) {
      setReport(null);
      setReportLoading(false);
      return;
    }
    let cancelled = false;
    setReportLoading(true);
    setError(null);
    getPersonnelRoster(id)
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
  }, [departmentId]);

  const departments = React.useMemo(
    () => options.departments.filter((item) => String(item.group_id) === groupId),
    [options.departments, groupId],
  );

  async function handleDownload() {
    const id = Number(departmentId);
    if (!Number.isSafeInteger(id) || id < 1) return;
    setDownloading(true);
    setError(null);
    try {
      await downloadPersonnelRoster(id);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="space-y-5 px-4 py-5">
      <section className="grid gap-3 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800 md:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="font-medium">Группа отделений</span>
          <select
            aria-label="Группа отделений"
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
            value={groupId}
            disabled={optionsLoading}
            onChange={(event) => {
              setGroupId(event.target.value);
              setDepartmentId("");
              setReport(null);
              setError(null);
            }}
          >
            <option value="">Выберите группу</option>
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
            disabled={!groupId || optionsLoading}
            onChange={(event) => setDepartmentId(event.target.value)}
          >
            <option value="">Выберите отделение</option>
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
          disabled={!departmentId || downloading}
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
        {!error && reportLoading ? <div className="px-4 py-8 text-center text-zinc-500">Загрузка…</div> : null}
        {!error && !reportLoading && !departmentId ? (
          <div className="px-4 py-8 text-center text-zinc-500">Выберите отделение для формирования отчёта.</div>
        ) : null}
        {!error && !reportLoading && departmentId && report?.items.length === 0 ? (
          <div className="px-4 py-8 text-center text-zinc-500">Сотрудники не найдены.</div>
        ) : null}
        {!error && !reportLoading && report && report.items.length > 0 ? (
          <div className="overflow-x-auto">
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
                {report.items.map((item) => (
                  <tr key={item.number} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="px-4 py-3 text-right">{item.number}</td>
                    <td className="px-4 py-3">{item.full_name}</td>
                    <td className="px-4 py-3">{item.position}</td>
                    <td className="px-4 py-3 text-right">{item.rate}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </div>
  );
}
