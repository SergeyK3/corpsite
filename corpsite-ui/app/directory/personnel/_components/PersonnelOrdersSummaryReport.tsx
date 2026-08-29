"use client";

import * as React from "react";

import {
  getPersonnelOrdersSummary,
  type PersonnelOrdersSummaryCategory,
  type PersonnelOrdersSummaryReport,
} from "../_lib/personnelReportsApi.client";
import { formatPersonnelOrderDate } from "../_lib/personnelOrderLabels";

function errorMessage(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) return String(error.message);
  return "Не удалось сформировать сводку по приказам.";
}

function displayList(values: string[]): string {
  return values.length > 0 ? values.join(", ") : "—";
}

function CategoryDetails({ category }: { category: PersonnelOrdersSummaryCategory }) {
  if (category.orders.length === 0) {
    return <div className="px-4 py-5 text-center text-zinc-500">Приказы отсутствуют</div>;
  }
  return (
    <div className="overflow-x-auto bg-zinc-50/60 p-3 dark:bg-zinc-950/40">
      <table className="min-w-[920px] w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-zinc-500">
          <tr>
            <th className="px-3 py-2">Номер</th>
            <th className="px-3 py-2">Дата</th>
            <th className="px-3 py-2">Тип или подтип</th>
            <th className="px-3 py-2">Сотрудники</th>
            <th className="px-3 py-2">Подразделение</th>
            <th className="px-3 py-2">Статус</th>
          </tr>
        </thead>
        <tbody>
          {category.orders.map((order) => (
            <tr key={order.order_id} className="border-t border-zinc-200 dark:border-zinc-800">
              <td className="px-3 py-2">{order.order_number || "—"}</td>
              <td className="px-3 py-2">{formatPersonnelOrderDate(order.order_date)}</td>
              <td className="px-3 py-2">{order.type_label}</td>
              <td className="px-3 py-2">{displayList(order.employee_names)}</td>
              <td className="px-3 py-2">{displayList(order.department_names)}</td>
              <td className="px-3 py-2">{order.status_label}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PersonnelOrdersSummaryReportPanel() {
  const [dateFrom, setDateFrom] = React.useState("");
  const [dateTo, setDateTo] = React.useState("");
  const [report, setReport] = React.useState<PersonnelOrdersSummaryReport | null>(null);
  const [expanded, setExpanded] = React.useState<Set<string>>(() => new Set());
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getPersonnelOrdersSummary({ dateFrom: dateFrom || undefined, dateTo: dateTo || undefined })
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
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dateFrom, dateTo]);

  function toggleCategory(code: string) {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  return (
    <div className="space-y-5 px-4 py-5">
      <section className="space-y-3 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">Отчёт</div>
          <h2 className="font-semibold">Общая сводка по приказам</h2>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="space-y-1 text-sm">
            <span className="font-medium">Дата с</span>
            <input
              aria-label="Дата с"
              type="date"
              value={dateFrom}
              max={dateTo || undefined}
              onChange={(event) => setDateFrom(event.target.value)}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="font-medium">Дата по</span>
            <input
              aria-label="Дата по"
              type="date"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={(event) => setDateTo(event.target.value)}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
            />
          </label>
        </div>
        <p className="text-sm text-zinc-500">
          Пустой период включает все доступные приказы. При заданном периоде приказы без официальной даты не включаются.
        </p>
      </section>

      <section className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
        <div className="border-b border-zinc-200 px-4 py-3 font-semibold dark:border-zinc-800">
          Общая сводка по приказам
        </div>
        {error ? <div role="alert" className="px-4 py-8 text-center text-red-600">{error}</div> : null}
        {!error && loading ? <div className="px-4 py-8 text-center text-zinc-500">Загрузка…</div> : null}
        {!error && !loading && report ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
                <tr>
                  <th className="px-4 py-3">Категория</th>
                  <th className="w-36 px-4 py-3 text-right">Количество</th>
                  <th className="w-64 px-4 py-3 text-right">В том числе без номера или даты</th>
                </tr>
              </thead>
              <tbody>
                {report.categories.map((category) => {
                  const isExpanded = expanded.has(category.code);
                  const detailsId = `orders-category-${category.code}`;
                  return (
                    <React.Fragment key={category.code}>
                      <tr className="border-t border-zinc-100 dark:border-zinc-800">
                        <th scope="row" className="px-4 py-3 text-left font-medium">
                          <button
                            type="button"
                            aria-label={`${isExpanded ? "Свернуть" : "Раскрыть"} категорию ${category.name}`}
                            aria-expanded={isExpanded}
                            aria-controls={detailsId}
                            onClick={() => toggleCategory(category.code)}
                            className="inline-flex items-center gap-2 rounded px-1 py-0.5 hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:hover:bg-zinc-800"
                          >
                            <span aria-hidden="true" className="w-5 text-lg">{isExpanded ? "−" : "＋"}</span>
                            <span>{category.name}</span>
                          </button>
                        </th>
                        <td className="px-4 py-3 text-right">{category.count}</td>
                        <td className="px-4 py-3 text-right">{category.incomplete_count}</td>
                      </tr>
                      {isExpanded ? (
                        <tr id={detailsId} className="border-t border-zinc-100 dark:border-zinc-800">
                          <td colSpan={3} className="p-0"><CategoryDetails category={category} /></td>
                        </tr>
                      ) : null}
                    </React.Fragment>
                  );
                })}
                <tr className="border-t-2 border-zinc-300 font-bold dark:border-zinc-700">
                  <th scope="row" className="px-4 py-3 text-left">Всего</th>
                  <td className="px-4 py-3 text-right">{report.total_count}</td>
                  <td className="px-4 py-3 text-right">{report.total_incomplete_count}</td>
                </tr>
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </div>
  );
}
