"use client";

import Link from "next/link";
import React from "react";

import type { CatchUpRegularTasksResult } from "@/lib/api";
import {
  buildCatchUpReviewRows,
  resolveAggregateOccurrenceDate,
  resolveAggregatePeriodFromItems,
} from "@/lib/catchUpWorkflow";
import { catchUpUiLabel, runTitleLabel, scheduleTypeLabel, uiFieldLabel } from "@/lib/i18n";
import { fmtDate, type RegularTaskRunItemRow } from "@/lib/regularTaskRunJournal";

type CatchUpReviewPanelProps = {
  title: string;
  result: CatchUpRegularTasksResult;
  items: RegularTaskRunItemRow[];
  isDryRunPreview: boolean;
  showJournalLink?: boolean;
};

function StatBlock({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white/60 dark:bg-zinc-950/60 px-3 py-2">
      <div className="text-xs text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className="mt-0.5 text-lg font-semibold text-zinc-900 dark:text-zinc-50">{value}</div>
    </div>
  );
}

export default function CatchUpReviewPanel({
  title,
  result,
  items,
  isDryRunPreview,
  showJournalLink = true,
}: CatchUpReviewPanelProps) {
  const resolved = result.resolved ?? {};
  const stats = result.stats ?? {};
  const periodLabel = resolveAggregatePeriodFromItems(items);
  const occurrenceDate = resolveAggregateOccurrenceDate(items, resolved.run_for_date);
  const reviewRows = buildCatchUpReviewRows(items, { isDryRunPreview });

  const firstItemDates = reviewRows[0];

  return (
    <section
      className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white/50 dark:bg-zinc-900/50 p-4 shadow-sm"
      data-testid="catch-up-review-panel"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{title}</h2>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            {uiFieldLabel("run_id")}: {result.run_id}
            {result.dry_run ? " · пробный прогон" : " · боевой прогон"}
          </p>
        </div>
        {showJournalLink && result.run_id ? (
          <Link
            href={`/regular-task-runs?run_id=${result.run_id}`}
            className="rounded-xl border border-blue-200 dark:border-blue-900/50 bg-blue-50 dark:bg-blue-950/30 px-3 py-2 text-sm font-medium text-blue-700 dark:text-blue-300 transition hover:bg-blue-100 dark:hover:bg-blue-950/50"
            data-testid="catch-up-open-journal"
          >
            {catchUpUiLabel("workflow_journal")} — {runTitleLabel(result.run_id)}
          </Link>
        ) : null}
      </div>

      <div className="mt-4 rounded-xl border border-amber-200 dark:border-amber-900/40 bg-amber-50/80 dark:bg-amber-950/20 px-4 py-3">
        <div className="text-xs font-medium uppercase tracking-wide text-amber-800 dark:text-amber-300">
          Период отчётности
        </div>
        <div
          className="mt-1 text-xl font-semibold text-amber-950 dark:text-amber-100"
          data-testid="catch-up-period-label"
        >
          {periodLabel ?? "—"}
        </div>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm text-amber-900/90 dark:text-amber-200/90">
          <span>
            <span className="text-amber-700/80 dark:text-amber-400/80">
              {catchUpUiLabel("run_for_date")}:
            </span>{" "}
            {resolved.run_for_date ? fmtDate(resolved.run_for_date) : "—"}
          </span>
          <span>
            <span className="text-amber-700/80 dark:text-amber-400/80">
              {catchUpUiLabel("occurrence_date")}:
            </span>{" "}
            {occurrenceDate ? fmtDate(occurrenceDate) : "—"}
          </span>
          {firstItemDates ? (
            <span>
              <span className="text-amber-700/80 dark:text-amber-400/80">
                {catchUpUiLabel("due_date")}:
              </span>{" "}
              {firstItemDates.due_date_label}
            </span>
          ) : null}
          <span>
            <span className="text-amber-700/80 dark:text-amber-400/80">
              {catchUpUiLabel("schedule_type")}:
            </span>{" "}
            {scheduleTypeLabel(resolved.schedule_type) || "—"}
          </span>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatBlock label={catchUpUiLabel("templates_total")} value={stats.templates_total ?? 0} />
        <StatBlock label={catchUpUiLabel("templates_due")} value={stats.templates_due ?? 0} />
        <StatBlock label={catchUpUiLabel("created")} value={stats.created ?? 0} />
        <StatBlock label={catchUpUiLabel("deduped")} value={stats.deduped ?? 0} />
        <StatBlock label={catchUpUiLabel("errors")} value={stats.errors ?? 0} />
      </div>

      {reviewRows.length > 0 ? (
        <div className="mt-4 overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-zinc-100/80 dark:bg-zinc-950/80 text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              <tr>
                <th className="px-3 py-2 font-medium">{uiFieldLabel("template")}</th>
                <th className="px-3 py-2 font-medium">{catchUpUiLabel("report_code")}</th>
                <th className="px-3 py-2 font-medium">{uiFieldLabel("role")}</th>
                <th className="px-3 py-2 font-medium">{uiFieldLabel("period")}</th>
                <th className="px-3 py-2 font-medium">{catchUpUiLabel("due_date")}</th>
                <th className="px-3 py-2 font-medium">{catchUpUiLabel("reason")}</th>
                <th className="px-3 py-2 font-medium">{catchUpUiLabel("title_final")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
              {reviewRows.map((row) => (
                <tr key={row.item_id} className="align-top text-zinc-800 dark:text-zinc-200">
                  <td className="px-3 py-2">{row.template_label}</td>
                  <td className="px-3 py-2 font-mono text-xs">{row.report_code}</td>
                  <td className="px-3 py-2">{row.executor_label}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{row.period_label}</td>
                  <td className="px-3 py-2 whitespace-nowrap">{row.due_date_label}</td>
                  <td className="px-3 py-2">{row.reason_label}</td>
                  <td className="px-3 py-2 min-w-[16rem]">{row.title_final}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-zinc-600 dark:text-zinc-400">{catchUpUiLabel("no_items")}</p>
      )}
    </section>
  );
}
