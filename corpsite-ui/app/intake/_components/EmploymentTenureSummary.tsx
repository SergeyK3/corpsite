"use client";

import * as React from "react";

import type { IntakeEmploymentBiographyEntry } from "../_lib/intakeEmploymentBiography";
import { ensureEmploymentBiographyRecordId } from "../_lib/intakeEmploymentBiography";
import {
  calculateEmploymentTenure,
  type EmploymentTenureCalculation,
} from "../_lib/employmentTenureApi.client";
import {
  formatTenureDaysCount,
  formatTenureDisplay,
  formatTenureYmd,
} from "../_lib/employmentTenureFormat";
import { formatIntakePeriodForDisplay } from "../_lib/intakePeriodFormat";

type Props = {
  items: readonly IntakeEmploymentBiographyEntry[];
  calculation: EmploymentTenureCalculation | null;
  loading?: boolean;
  error?: string | null;
};

function formatCalculationDate(isoDate: string): string {
  const parts = isoDate.split("-");
  if (parts.length !== 3) return isoDate;
  return `${parts[2]}.${parts[1]}.${parts[0]}`;
}

function findItemByRecordId(
  items: readonly IntakeEmploymentBiographyEntry[],
  recordId: string,
): IntakeEmploymentBiographyEntry | undefined {
  return items.find((item, index) => ensureEmploymentBiographyRecordId(item, index) === recordId);
}

export default function EmploymentTenureSummary({ items, calculation, loading = false, error = null }: Props) {
  const [breakdownExpanded, setBreakdownExpanded] = React.useState(false);
  const [excludedExpanded, setExcludedExpanded] = React.useState(false);

  if (items.length === 0) {
    return null;
  }

  const excludedRecords = calculation?.records.filter((row) => !row.included && row.warning) ?? [];

  return (
    <section
      className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40"
      data-testid="intake-employment-tenure-summary"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
          Общий стаж:{" "}
          {loading ? (
            <span className="text-zinc-500">расчёт…</span>
          ) : calculation ? (
            <span data-testid="intake-employment-total-tenure">{formatTenureDisplay(calculation.total_days)}</span>
          ) : (
            <span className="text-zinc-500">—</span>
          )}
        </p>
        {calculation ? (
          <p className="text-xs text-zinc-500" data-testid="intake-employment-tenure-calc-date">
            Дата расчёта: {formatCalculationDate(calculation.calculation_date)}
          </p>
        ) : null}
      </div>

      {calculation ? (
        <p className="mt-1 text-xs text-zinc-500" data-testid="intake-employment-tenure-ymd">
          {formatTenureYmd(calculation.total_ymd)}
        </p>
      ) : null}

      {error ? (
        <p className="mt-2 text-sm text-red-700 dark:text-red-300" data-testid="intake-employment-tenure-error">
          {error}
        </p>
      ) : null}

      {excludedRecords.length > 0 ? (
        <div className="mt-2">
          <button
            type="button"
            className="text-sm text-amber-700 hover:underline dark:text-amber-300"
            aria-expanded={excludedExpanded}
            data-testid="intake-employment-tenure-excluded-toggle"
            onClick={() => setExcludedExpanded((value) => !value)}
          >
            Не включено записей: {excludedRecords.length}
          </button>
          {excludedExpanded ? (
            <ul
              className="mt-2 space-y-1 text-sm text-amber-700 dark:text-amber-300"
              data-testid="intake-employment-tenure-excluded-details"
            >
              {excludedRecords.map((row) => (
                <li key={row.record_id}>
                  {row.label}: {row.warning}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {calculation ? (
        <div className="mt-3">
          <button
            type="button"
            className="text-sm text-sky-700 hover:underline dark:text-sky-300"
            aria-expanded={breakdownExpanded}
            data-testid="intake-employment-tenure-breakdown-toggle"
            onClick={() => setBreakdownExpanded((value) => !value)}
          >
            Состав расчёта
          </button>
          {breakdownExpanded ? (
            <dl
              className="mt-2 space-y-2 text-sm text-zinc-700 dark:text-zinc-300"
              data-testid="intake-employment-tenure-breakdown"
            >
              {calculation.records
                .filter((row) => row.included && row.days !== null)
                .map((row) => {
                  const item = findItemByRecordId(items, row.record_id);
                  const periodFrom = formatIntakePeriodForDisplay(item?.year_from) || "—";
                  const periodTo = String(item?.year_to ?? "").trim()
                    ? formatIntakePeriodForDisplay(item?.year_to) || "—"
                    : "по настоящее время";
                  return (
                    <div key={row.record_id} className="rounded-lg border border-zinc-200 px-3 py-2 dark:border-zinc-800">
                      <dt className="font-medium text-zinc-900 dark:text-zinc-100">{row.label}</dt>
                      <dd className="mt-1 text-xs text-zinc-500">
                        {periodFrom} — {periodTo}
                      </dd>
                      <dd className="mt-1">{formatTenureDisplay(row.days!)}</dd>
                    </div>
                  );
                })}
              <div className="border-t border-zinc-200 pt-2 dark:border-zinc-800">
                <div className="flex justify-between gap-3">
                  <dt>Сумма записей</dt>
                  <dd>{formatTenureDaysCount(calculation.arithmetic_sum_days)} дней</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt>Исключено пересечений</dt>
                  <dd>{formatTenureDaysCount(calculation.overlap_excluded_days)} дней</dd>
                </div>
                <div className="flex justify-between gap-3 font-medium text-zinc-900 dark:text-zinc-100">
                  <dt>Итого</dt>
                  <dd>{formatTenureDisplay(calculation.total_days)}</dd>
                </div>
              </div>
            </dl>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export function useEmploymentTenureCalculation(items: readonly IntakeEmploymentBiographyEntry[]) {
  const [calculation, setCalculation] = React.useState<EmploymentTenureCalculation | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const requestIdRef = React.useRef(0);

  React.useEffect(() => {
    if (items.length === 0) {
      setCalculation(null);
      setLoading(false);
      setError(null);
      return;
    }

    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setLoading(true);
    setError(null);

    const timer = window.setTimeout(() => {
      void calculateEmploymentTenure(items)
        .then((result) => {
          if (requestIdRef.current !== requestId) return;
          setCalculation(result);
          setLoading(false);
        })
        .catch((cause: unknown) => {
          if (requestIdRef.current !== requestId) return;
          setCalculation(null);
          setLoading(false);
          setError(cause instanceof Error ? cause.message : "Не удалось рассчитать стаж");
        });
    }, 250);

    return () => {
      window.clearTimeout(timer);
    };
  }, [items]);

  return { calculation, loading, error };
}
