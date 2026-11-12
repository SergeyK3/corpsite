"use client";

import * as React from "react";

import {
  getPersonnelEmployeeActionsReport,
  type PersonnelEmployeeActionsReport,
  type PersonnelEmployeeActionsRow,
} from "../_lib/personnelReportsApi.client";
import { formatPersonnelOrderDate } from "../_lib/personnelOrderLabels";

function OrderDetails({ employee }: { employee: PersonnelEmployeeActionsRow }) {
  return <div className="overflow-x-auto bg-zinc-50 p-3 dark:bg-zinc-900/50">
    <table className="w-full min-w-[650px] text-sm">
      <thead className="text-left text-zinc-500"><tr>
        <th className="px-3 py-2">Приказ</th>
        <th className="px-3 py-2">Дата</th>
        <th className="px-3 py-2">Статус</th>
        <th className="px-3 py-2">Действия сотрудника</th>
      </tr></thead>
      <tbody>{employee.orders.map((order) => <tr key={order.order_id} className="border-t border-zinc-200 dark:border-zinc-800">
        <td className="px-3 py-2">{order.is_composite ? <span className="mr-2 rounded bg-blue-100 px-2 py-0.5 text-xs text-blue-800 dark:bg-blue-950 dark:text-blue-200">Составной</span> : null}<a className="text-blue-700 underline dark:text-blue-300" href={`/directory/personnel/orders?order_id=${order.order_id}`}>
          № {order.order_number || "—"}
        </a></td>
        <td className="px-3 py-2">{formatPersonnelOrderDate(order.order_date)}</td>
        <td className="px-3 py-2">{order.status_label}</td>
        <td className="px-3 py-2">{order.actions.map((action) => `${action.label}: ${action.count}`).join("; ")}</td>
      </tr>)}</tbody>
    </table>
  </div>;
}

export default function PersonnelEmployeeActionsReport() {
  const [report, setReport] = React.useState<PersonnelEmployeeActionsReport | null>(null);
  const [query, setQuery] = React.useState("");
  const [orgUnitId, setOrgUnitId] = React.useState("");
  const [expandedId, setExpandedId] = React.useState<number | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [refreshNonce, setRefreshNonce] = React.useState(0);

  React.useEffect(() => {
    let active = true;
    let requestNumber = 0;
    let lastRequestAt = 0;
    function load() {
      const now = Date.now();
      if (now - lastRequestAt < 500) return;
      lastRequestAt = now;
      const currentRequest = ++requestNumber;
      getPersonnelEmployeeActionsReport()
        .then((data) => {
          if (active && currentRequest === requestNumber) {
            setReport(data);
            setError(null);
          }
        })
        .catch((reason) => {
          if (active && currentRequest === requestNumber) {
            setError(reason instanceof Error ? reason.message : "Не удалось загрузить отчёт.");
          }
        });
    }
    function onVisibilityChange() {
      if (document.visibilityState === "visible") load();
    }
    load();
    window.addEventListener("focus", load);
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      active = false;
      window.removeEventListener("focus", load);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [refreshNonce]);

  const departments = Array.from(new Map<number, string>(
    report?.employees.flatMap((employee): Array<[number, string]> =>
      employee.org_unit_id === null ? [] :
        [[employee.org_unit_id, employee.org_unit_name || `Подразделение #${employee.org_unit_id}`]]
    ) ?? []
  )).sort((left, right) => left[1].localeCompare(right[1], "ru") || Number(left[0]) - Number(right[0]));
  const visible = report?.employees.filter((employee) =>
    (!orgUnitId || employee.org_unit_id === Number(orgUnitId)) &&
    employee.full_name.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())
  ) ?? [];

  return <section className="mx-4 mt-5 overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800" aria-label="Кадровые действия по сотрудникам">
    <div className="flex flex-wrap items-end justify-between gap-3 border-b border-zinc-200 p-4 dark:border-zinc-800">
      <div><div className="text-xs uppercase tracking-wide text-zinc-500">Отчёт</div>
        <h2 className="font-semibold">Кадровые действия по сотрудникам</h2>
        <button type="button" onClick={() => setRefreshNonce((value) => value + 1)}
          className="mt-2 text-sm text-blue-700 underline dark:text-blue-300">Обновить отчёт</button></div>
      <div className="flex flex-wrap gap-3">
        <label className="space-y-1 text-sm"><span className="block">Подразделение</span>
          <select value={orgUnitId} onChange={(event) => setOrgUnitId(event.target.value)}
            className="w-full min-w-56 rounded-lg border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950">
            <option value="">Все подразделения</option>
            {departments.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
        </label>
        <label className="space-y-1 text-sm"><span className="block">Поиск по ФИО</span>
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)}
            className="w-full min-w-64 rounded-lg border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950" />
        </label>
      </div>
    </div>
    {error ? <p role="alert" className="p-4 text-red-600">{error}</p> : null}
    {!error && !report ? <p className="p-4 text-zinc-500">Загрузка…</p> : null}
    {report ? <div className="overflow-x-auto"><table className="w-full min-w-[680px] text-sm">
      <thead className="bg-zinc-50 text-left text-zinc-500 dark:bg-zinc-900"><tr>
        <th className="px-4 py-3">Сотрудник</th>
        <th className="px-4 py-3">Подразделение</th>
        <th className="px-4 py-3 text-right">Приказов</th>
        <th className="px-4 py-3 text-right">Кадровых действий</th>
      </tr></thead>
      <tbody>{visible.map((employee) => <React.Fragment key={employee.employee_id}>
        <tr className="border-t border-zinc-200 dark:border-zinc-800">
          <th scope="row" className="px-4 py-3 text-left font-medium">{employee.full_name}</th>
          <td className="px-4 py-3">{employee.org_unit_name || "—"}</td>
          <td className="px-4 py-3 text-right"><button type="button" disabled={!employee.order_count}
            aria-label={`Приказы: ${employee.full_name}, ${employee.order_count}`}
            aria-expanded={expandedId === employee.employee_id}
            onClick={() => setExpandedId(expandedId === employee.employee_id ? null : employee.employee_id)}
            className="rounded px-2 py-1 text-blue-700 underline disabled:text-zinc-500 disabled:no-underline dark:text-blue-300">{employee.order_count}</button>
            {employee.order_count > 0 ? <div className="text-xs text-zinc-500">Обычные: {employee.ordinary_order_count} · Составные: {employee.composite_order_count}</div> : null}</td>
          <td className="px-4 py-3 text-right"><button type="button" disabled={!employee.action_count}
            aria-label={`Кадровые действия: ${employee.full_name}, ${employee.action_count}`}
            aria-expanded={expandedId === employee.employee_id}
            onClick={() => setExpandedId(expandedId === employee.employee_id ? null : employee.employee_id)}
            className="rounded px-2 py-1 text-blue-700 underline disabled:text-zinc-500 disabled:no-underline dark:text-blue-300">{employee.action_count}</button>
            {employee.actions_by_type.length ? <div className="text-xs text-zinc-500">{employee.actions_by_type.map((action) => `${action.label}: ${action.count}`).join("; ")}</div> : null}</td>
        </tr>
        {expandedId === employee.employee_id ? <tr className="border-t border-zinc-200 dark:border-zinc-800"><td colSpan={4}><OrderDetails employee={employee} /></td></tr> : null}
      </React.Fragment>)}</tbody>
    </table>{visible.length === 0 ? <p className="p-4 text-center text-zinc-500">Сотрудники не найдены.</p> : null}</div> : null}
  </section>;
}
