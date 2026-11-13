"use client";

import { useEffect, useMemo, useState } from "react";

import {
  getPersonnelHeadcountTrend,
  type PersonnelHeadcountTrend,
} from "../_lib/personnelReportsApi.client";

const MONTH_NAMES = [
  "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
];

function HeadcountChart({ report }: { report: PersonnelHeadcountTrend }) {
  const width = Math.max(700, report.months.length * 90 + 90);
  const points = useMemo(() => {
    const values = report.months.flatMap((item) => item.count === null ? [] : [item.count]);
    const min = Math.min(...values);
    const max = Math.max(...values);
    return report.months.map((item, index) => ({
      ...item,
      x: 70 + index * 90,
      y: item.count === null ? null : max === min ? 122 : 185 - (item.count - min) / (max - min) * 115,
    }));
  }, [report.months]);
  const segments: string[] = [];
  let segment: string[] = [];
  for (const point of points) {
    if (point.y === null) {
      if (segment.length > 1) segments.push(segment.join(" "));
      segment = [];
    } else {
      segment.push(`${point.x},${point.y}`);
    }
  }
  if (segment.length > 1) segments.push(segment.join(" "));

  return <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
    <svg viewBox={`0 0 ${width} 270`} width={width} height={270} role="img"
      aria-label={`Численность персонала с января по ${MONTH_NAMES[report.months.length - 1].toLowerCase()} ${report.year} года`}
      className="block max-w-none">
      {segments.map((coordinates) => <polyline key={coordinates} points={coordinates} fill="none"
        stroke="currentColor" strokeWidth="2.5" className="text-blue-600 dark:text-blue-400" />)}
      {points.map((point) => <g key={point.month}>
        {point.y === null ? <text x={point.x} y="130" textAnchor="middle" fontSize="13"
          className="fill-zinc-500" data-testid={`headcount-no-data-${point.month}`}>Нет данных</text>
          : <>
            <circle cx={point.x} cy={point.y} r="5" className="fill-blue-600 dark:fill-blue-400" />
            <text x={point.x} y={point.y - 14} textAnchor="middle" fontSize="15" fontWeight="700"
              className="fill-zinc-900 dark:fill-zinc-50" data-testid={`headcount-value-${point.month}`}>
              {point.count}
            </text>
          </>}
        <text x={point.x} y="224" textAnchor="middle" fontSize="13" className="fill-zinc-700 dark:fill-zinc-300">
          {MONTH_NAMES[point.month - 1]}
        </text>
        {point.is_current ? <text x={point.x} y="245" textAnchor="middle" fontSize="12" fontWeight="600"
          className="fill-blue-700 dark:fill-blue-300">на сегодня</text> : null}
      </g>)}
    </svg>
  </div>;
}

export default function PersonnelJournalDashboards() {
  const [report, setReport] = useState<PersonnelHeadcountTrend | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    getPersonnelHeadcountTrend()
      .then((value) => { if (active) setReport(value); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, []);

  return <section className="space-y-4 px-4 py-5" aria-label="Дашборды кадрового журнала">
    <h1 className="text-xl font-semibold">Численность персонала с начала года</h1>
    {error ? <p role="alert">Не удалось загрузить численность персонала.</p> : null}
    {!report && !error ? <p role="status">Загрузка…</p> : null}
    {report ? <>
      <HeadcountChart report={report} />
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Текущий месяц: действующие сотрудники регистра на {report.as_of}. Исторические значения: подтверждённые кадровые события приёма и увольнения.
        {!report.history_complete ? " За месяцы без полной истории показано «Нет данных»." : ""}
      </p>
    </> : null}
  </section>;
}
