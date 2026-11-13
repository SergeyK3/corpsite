"use client";

import { useEffect, useState } from "react";

import {
  getPersonnelOrdersMonthlyDashboard,
  type PersonnelOrdersMonthlyDashboard,
  type PersonnelOrdersMonthlyType,
} from "../_lib/personnelReportsApi.client";

const MONTH_NAMES = [
  "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
];

function OrdersMonthlyChart({ report }: { report: PersonnelOrdersMonthlyDashboard }) {
  const width = Math.max(700, report.months.length * 90 + 90);
  const maxCount = Math.max(1, ...report.months.map((item) => item.count));
  const points = report.months.map((item, index) => ({
    ...item,
    x: 70 + index * 90,
    y: 190 - item.count / maxCount * 115,
  }));

  return <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
    <svg viewBox={`0 0 ${width} 270`} width={width} height={270} role="img"
      aria-label={`Количество кадровых приказов по месяцам за ${report.year} год`}
      className="block max-w-none">
      {points.length > 1 ? <polyline points={points.map((point) => `${point.x},${point.y}`).join(" ")}
        fill="none" stroke="currentColor" strokeWidth="2.5" className="text-blue-600 dark:text-blue-400" /> : null}
      {points.map((point) => <g key={point.month}>
        <circle cx={point.x} cy={point.y} r="5" className="fill-blue-600 dark:fill-blue-400" />
        <text x={point.x} y={point.y - 14} textAnchor="middle" fontSize="15" fontWeight="700"
          className="fill-zinc-900 dark:fill-zinc-50" data-testid={`orders-month-count-${point.month}`}>
          {point.count}
        </text>
        <text x={point.x} y="224" textAnchor="middle" fontSize="13" className="fill-zinc-700 dark:fill-zinc-300">
          {MONTH_NAMES[point.month - 1]}
        </text>
        {point.is_current ? <text x={point.x} y="245" textAnchor="middle" fontSize="12" fontWeight="600"
          className="fill-blue-700 dark:fill-blue-300">по сегодня</text> : null}
      </g>)}
    </svg>
  </div>;
}

export default function PersonnelOrdersDashboards() {
  const [orderType, setOrderType] = useState<PersonnelOrdersMonthlyType | "">("");
  const [report, setReport] = useState<PersonnelOrdersMonthlyDashboard | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    getPersonnelOrdersMonthlyDashboard(orderType || null)
      .then((value) => { if (active) setReport(value); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [orderType]);

  return <section className="space-y-4 px-4 py-5" aria-label="Дашборды кадровых приказов">
    <h1 className="text-xl font-semibold">Количество кадровых приказов по месяцам</h1>
    <label className="block max-w-xs text-sm font-medium text-zinc-800 dark:text-zinc-200" htmlFor="orders-dashboard-type">
      Тип приказа
      <select id="orders-dashboard-type" value={orderType}
        onChange={(event) => {
          setReport(null);
          setError(false);
          setOrderType(event.target.value as PersonnelOrdersMonthlyType | "");
        }}
        className="mt-1 block w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
        <option value="">Все типы</option>
        <option value="HIRE">Приём</option>
        <option value="TERMINATION">Увольнение</option>
        <option value="TRANSFER">Перевод</option>
      </select>
    </label>
    {error ? <p role="alert">Не удалось загрузить количество приказов.</p> : null}
    {!report && !error ? <p role="status">Загрузка…</p> : null}
    {report ? <>
      <OrdersMonthlyChart report={report} />
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        По официальной дате приказа. Каждый приказ учитывается один раз; текущий месяц — по {report.as_of} включительно.
      </p>
    </> : null}
  </section>;
}
