"use client";

import * as React from "react";

import {
  getPersonnelTypeHeadcountReport,
  type PersonnelTypeHeadcountReport as HeadcountData,
} from "../_lib/personnelReportsApi.client";

export default function PersonnelTypeHeadcountReport() {
  const [report, setReport] = React.useState<HeadcountData | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [unknownExpanded, setUnknownExpanded] = React.useState(false);

  React.useEffect(() => {
    let active = true;
    getPersonnelTypeHeadcountReport()
      .then((value) => { if (active) setReport(value); })
      .catch(() => { if (active) setError("Не удалось загрузить численность работников."); });
    return () => { active = false; };
  }, []);

  return <section className="space-y-4 px-4 py-5" aria-label="Численность работников по типу персонала">
    <h1 className="text-xl font-semibold">Численность работников по типу персонала</h1>
    {error ? <p role="alert">{error}</p> : null}
    {!report && !error ? <p role="status">Загрузка…</p> : null}
    {report ? <div className="max-w-2xl overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-sm" data-testid="personnel-type-headcount-table">
        <thead className="bg-zinc-50 text-left dark:bg-zinc-900"><tr>
          <th className="px-4 py-3 font-semibold">Тип персонала</th>
          <th className="px-4 py-3 text-right font-semibold">Количество работников</th>
        </tr></thead>
        <tbody>{report.groups.map((group) => <React.Fragment key={group.code ?? "unknown"}>
          <tr className="border-t border-zinc-200 dark:border-zinc-800">
            <th scope="row" className="px-4 py-3 text-left font-medium">{group.name}</th>
            <td className="px-4 py-3 text-right" data-testid={`personnel-type-headcount-${group.code ?? "unknown"}`}>
              {group.code === null && group.count > 0
                ? <button type="button" className="font-medium text-blue-700 underline underline-offset-2 hover:text-blue-900 dark:text-blue-300" aria-label="Показать сотрудников без типа" aria-expanded={unknownExpanded} aria-controls="personnel-type-headcount-unknown-details" onClick={() => setUnknownExpanded((value) => !value)}>{group.count}</button>
                : group.count}
            </td>
          </tr>
          {group.code === null && group.count > 0 && unknownExpanded ? <tr className="border-t border-zinc-200 dark:border-zinc-800">
            <td colSpan={2} className="px-4 py-3">
              <div className="overflow-x-auto">
                <table id="personnel-type-headcount-unknown-details" data-testid="personnel-type-headcount-unknown-details" className="w-full text-sm">
                  <thead className="bg-zinc-50 text-left dark:bg-zinc-900"><tr>
                    <th className="px-3 py-2 font-semibold">ФИО</th>
                    <th className="px-3 py-2 font-semibold">Отделение</th>
                    <th className="px-3 py-2 font-semibold">Должность</th>
                    <th className="px-3 py-2 font-semibold">Тип</th>
                  </tr></thead>
                  <tbody>{report.unknown_employees.map((employee) => <tr key={employee.employee_id} data-testid="personnel-type-headcount-unknown-employee" className="border-t border-zinc-200 dark:border-zinc-800">
                    <td className="px-3 py-2">{employee.full_name || "—"}</td>
                    <td className="px-3 py-2">{employee.org_unit_name || "—"}</td>
                    <td className="px-3 py-2">{employee.position_name || "—"}</td>
                    <td className="px-3 py-2">Не указан</td>
                  </tr>)}</tbody>
                </table>
              </div>
            </td>
          </tr> : null}
        </React.Fragment>)}
          <tr className="border-t-2 border-zinc-300 font-bold dark:border-zinc-700">
            <th scope="row" className="px-4 py-3 text-left">Всего</th>
            <td className="px-4 py-3 text-right" data-testid="personnel-type-headcount-total">{report.total}</td>
          </tr>
        </tbody>
      </table>
    </div> : null}
  </section>;
}
