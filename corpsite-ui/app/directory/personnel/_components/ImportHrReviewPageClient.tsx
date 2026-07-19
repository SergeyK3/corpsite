"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { apiAuthMe } from "@/lib/api";
import { canSeeHrProcessesNav } from "@/lib/personnelNav";
import type { MeInfo } from "@/lib/types";

import {
  departmentFilterOptionValue,
  parseDepartmentFilterValue,
  parseGroupFilterValue,
  resolveGroupIdFromOptions,
} from "../_lib/importApi.client";
import {
  computeImportHrReviewSummary,
  filterEmployeesByStatusFilter,
  getDifferenceSectionLabel,
  isDifferenceAwaiting,
  isDifferenceResolved,
  mapStatusFilterToApiParams,
  resolveImportHrReviewContext,
  summarizeEmployeeProblems,
} from "../_lib/importHrReview";
import {
  IMPORT_HR_REVIEW_STATUS_FILTER_OPTIONS,
  IMPORT_HR_REVIEW_UI,
  importHrReviewEmployeeStatusClassName,
  importHrReviewEmployeeStatusLabel,
  type ImportHrReviewStatusFilter,
} from "../_lib/importHrReviewLabels";
import { DIFFERENCE_ACTIONS_FOUNDATION_NOTE } from "../_lib/mrdDifferenceActions";
import {
  getMrdHrReview,
  mapMrdApiError,
  type HrReviewDifference,
  type HrReviewEmployee,
  type HrReviewResponse,
} from "../_lib/mrdApi.client";
import { formatEtalonPeriodTitle } from "../_lib/mrdDisplay";
import { formatMonthlyDiffValue } from "../_lib/monthlyDiffLabels";
import { hrDecisionStatusLabel } from "../_lib/mrdHrReviewLabels";

const DEFAULT_STATUS_FILTER: ImportHrReviewStatusFilter = "needs_fix";

function actionButtonClassName(variant: "default" | "muted" = "default"): string {
  const base =
    "inline-flex rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60";
  if (variant === "muted") {
    return `${base} border border-zinc-200 text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900`;
  }
  return `${base} border border-blue-200 text-blue-700 hover:bg-blue-50 dark:border-blue-900 dark:text-blue-300 dark:hover:bg-blue-950`;
}

function SummaryCard({ label, value, testId }: { label: string; value: number; testId: string }) {
  return (
    <div
      className="rounded-xl border border-zinc-200 px-3 py-2 dark:border-zinc-800"
      data-testid={testId}
    >
      <div className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-zinc-900 dark:text-zinc-100">{value}</div>
    </div>
  );
}

function DifferenceFieldPanel({
  diff,
  correctedValue,
  onCorrectedValueChange,
}: {
  diff: HrReviewDifference;
  correctedValue: string;
  onCorrectedValueChange: (value: string) => void;
}) {
  const resolved = isDifferenceResolved(diff);
  const sectionLabel = getDifferenceSectionLabel(diff.record_kind);
  const borderClass = resolved
    ? "border-green-200 bg-green-50/60 dark:border-green-900 dark:bg-green-950/20"
    : "border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-950";

  return (
    <article
      className={`rounded-lg border p-4 ${borderClass}`}
      data-testid={`difference-${diff.difference_id}`}
      data-decision-status={diff.decision_status}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          {sectionLabel ? <div className="text-xs uppercase tracking-wide text-zinc-500">{sectionLabel}</div> : null}
          <h4 className="font-medium text-zinc-900 dark:text-zinc-100">{diff.field_label}</h4>
        </div>
        <span
          className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${
            resolved
              ? "border-green-200 bg-green-100 text-green-900 dark:border-green-800 dark:bg-green-950/50 dark:text-green-200"
              : "border-zinc-200 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300"
          }`}
        >
          {hrDecisionStatusLabel(diff.decision_status)}
        </span>
      </div>

      <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs uppercase tracking-wide text-zinc-500">{IMPORT_HR_REVIEW_UI.baselineLabel}</dt>
          <dd className="mt-1">{formatMonthlyDiffValue(diff.old_value)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-zinc-500">{IMPORT_HR_REVIEW_UI.controlListLabel}</dt>
          <dd className="mt-1">{formatMonthlyDiffValue(diff.detected_value ?? diff.new_value)}</dd>
        </div>
        {diff.source_label ? (
          <div className="sm:col-span-2">
            <dt className="text-xs uppercase tracking-wide text-zinc-500">{IMPORT_HR_REVIEW_UI.sourceLabel}</dt>
            <dd className="mt-1">{diff.source_label}</dd>
          </div>
        ) : null}
        <div className="sm:col-span-2">
          <dt className="text-xs uppercase tracking-wide text-zinc-500">{IMPORT_HR_REVIEW_UI.correctedValueLabel}</dt>
          <dd className="mt-1">
            <input
              type="text"
              value={correctedValue}
              onChange={(event) => onCorrectedValueChange(event.target.value)}
              disabled={resolved}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950 disabled:opacity-60"
              data-testid={`corrected-value-${diff.difference_id}`}
            />
          </dd>
        </div>
      </dl>
    </article>
  );
}

function EmployeeRow({
  employee,
  departmentName,
  expanded,
  correctedValues,
  onCorrectedValueChange,
  onToggle,
}: {
  employee: HrReviewEmployee;
  departmentName: string;
  expanded: boolean;
  correctedValues: Record<number, string>;
  onCorrectedValueChange: (differenceId: number, value: string) => void;
  onToggle: () => void;
}) {
  const problems = summarizeEmployeeProblems(employee);
  const awaitingCount = employee.differences.filter(isDifferenceAwaiting).length;

  return (
    <div className="border-t border-zinc-100 dark:border-zinc-800" data-testid={`employee-row-${employee.match_key}`}>
      <div className="flex flex-wrap items-start gap-3 px-4 py-3">
        <div className="min-w-0 flex-1">
          <div className="font-medium text-zinc-900 dark:text-zinc-100">{employee.full_name}</div>
          <div className="mt-1 grid gap-1 text-sm text-zinc-600 dark:text-zinc-400 sm:grid-cols-3">
            <span>{departmentName || "—"}</span>
            <span>{employee.position_raw || "—"}</span>
            <span>
              {awaitingCount > 0 ? awaitingCount : employee.difference_count}{" "}
              {IMPORT_HR_REVIEW_UI.discrepanciesColumn.toLowerCase()}
            </span>
          </div>
          {problems.length > 0 ? (
            <ul className="mt-2 flex flex-wrap gap-2 text-xs text-amber-800 dark:text-amber-200">
              {problems.map((problem) => (
                <li
                  key={`${employee.match_key}-${problem}`}
                  className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 dark:border-amber-900 dark:bg-amber-950/40"
                >
                  {problem}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <span
            className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${importHrReviewEmployeeStatusClassName(employee.review_status)}`}
          >
            {importHrReviewEmployeeStatusLabel(employee.review_status)}
          </span>
          <button
            type="button"
            className={actionButtonClassName()}
            onClick={onToggle}
            aria-expanded={expanded}
            data-testid={`fix-data-${employee.match_key}`}
          >
            {IMPORT_HR_REVIEW_UI.fixDataAction}
          </button>
        </div>
      </div>

      {expanded ? (
        <div className="border-t border-zinc-100 bg-zinc-50 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-900/30">
          {employee.differences.length === 0 ? (
            <p className="text-sm text-zinc-500">Несоответствий не обнаружено.</p>
          ) : (
            <div className="space-y-4">
              {employee.differences.map((diff) => (
                <DifferenceFieldPanel
                  key={diff.difference_id}
                  diff={diff}
                  correctedValue={correctedValues[diff.difference_id] ?? ""}
                  onCorrectedValueChange={(value) => onCorrectedValueChange(diff.difference_id, value)}
                />
              ))}
              <div className="space-y-2">
                <button
                  type="button"
                  className={actionButtonClassName()}
                  disabled
                  title={IMPORT_HR_REVIEW_UI.saveDisabledNote}
                  data-testid={`save-corrections-${employee.match_key}`}
                >
                  {IMPORT_HR_REVIEW_UI.saveAction}
                </button>
                <p className="text-xs text-zinc-500">{IMPORT_HR_REVIEW_UI.saveDisabledNote}</p>
                <p className="sr-only">{DIFFERENCE_ACTIONS_FOUNDATION_NOTE}</p>
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

export default function ImportHrReviewPageClient() {
  const searchParams = useSearchParams();

  const [me, setMe] = React.useState<MeInfo | null>(null);
  const [context, setContext] = React.useState<{ mrdId: number; reportPeriod: string } | null>(null);
  const [contextResolved, setContextResolved] = React.useState(false);
  const [review, setReview] = React.useState<HrReviewResponse | null>(null);
  const [summaryEmployees, setSummaryEmployees] = React.useState<HrReviewEmployee[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [orgGroupValue, setOrgGroupValue] = React.useState("");
  const [departmentValue, setDepartmentValue] = React.useState("");
  const [searchInput, setSearchInput] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState<ImportHrReviewStatusFilter>(DEFAULT_STATUS_FILTER);
  const [expandedMatchKey, setExpandedMatchKey] = React.useState<string | null>(null);
  const [correctedValues, setCorrectedValues] = React.useState<Record<number, string>>({});

  const departmentFilter = React.useMemo(() => parseDepartmentFilterValue(departmentValue), [departmentValue]);
  const groupFilter = React.useMemo(() => parseGroupFilterValue(orgGroupValue), [orgGroupValue]);

  const selectedDepartmentName = React.useMemo(() => {
    if (!review || !departmentFilter.org_unit_id) return "";
    return (
      review.departments.find((item) => item.org_unit_id === departmentFilter.org_unit_id)?.org_unit_name ?? ""
    );
  }, [departmentFilter.org_unit_id, review]);

  const visibleDepartments = React.useMemo(() => {
    if (!review) return [];
    if (!orgGroupValue) return review.departments;
    const groupId = resolveGroupIdFromOptions(
      {
        groups: review.org_groups.map(({ value, label, group_id }) => ({
          value,
          label,
          group_id: group_id ?? undefined,
        })),
        departments: review.departments,
      },
      orgGroupValue,
    );
    if (groupId) {
      return review.departments.filter((item) => item.org_group_id === groupId);
    }
    return review.departments;
  }, [orgGroupValue, review]);

  const mrdIdParam = searchParams.get("mrd_id");
  const reportPeriodParam = searchParams.get("report_period");

  const resolveContext = React.useCallback(async () => {
    const resolved = await resolveImportHrReviewContext({
      mrdIdParam,
      reportPeriodParam,
    });
    setContext(resolved);
    if (!resolved) {
      setError(IMPORT_HR_REVIEW_UI.noMrdHint);
    }
    return resolved;
  }, [mrdIdParam, reportPeriodParam]);

  React.useEffect(() => {
    if (me === null) return;
    if (!canSeeHrProcessesNav(me)) return;

    let cancelled = false;
    setContextResolved(false);

    void (async () => {
      try {
        await resolveContext();
      } finally {
        if (!cancelled) setContextResolved(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [me, resolveContext]);

  const loadReview = React.useCallback(async () => {
    if (!context?.mrdId) {
      setReview(null);
      setSummaryEmployees([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      if (!departmentFilter.org_unit_id) {
        const structure = await getMrdHrReview(context.mrdId, { changed_only: false });
        setReview(structure);
        setSummaryEmployees([]);
        setError(null);
        return;
      }

      const apiParams = mapStatusFilterToApiParams(statusFilter);
      const [listData, summaryData] = await Promise.all([
        getMrdHrReview(context.mrdId, {
          org_group_id: groupFilter.org_group_id,
          effective_log_group: groupFilter.effective_log_group,
          org_unit_id: departmentFilter.org_unit_id,
          changed_only: apiParams.changed_only,
          review_status: apiParams.review_status,
          search: searchInput.trim() || null,
          limit: 200,
        }),
        getMrdHrReview(context.mrdId, {
          org_unit_id: departmentFilter.org_unit_id,
          changed_only: false,
          search: searchInput.trim() || null,
          limit: 200,
        }),
      ]);

      setReview(listData);
      setSummaryEmployees(summaryData.employees.items);
      setError(null);
    } catch (e) {
      setReview(null);
      setSummaryEmployees([]);
      setError(mapMrdApiError(e));
    } finally {
      setLoading(false);
    }
  }, [
    context?.mrdId,
    departmentFilter.org_unit_id,
    groupFilter.effective_log_group,
    groupFilter.org_group_id,
    searchInput,
    statusFilter,
  ]);

  React.useEffect(() => {
    void apiAuthMe()
      .then((data) => setMe(data))
      .catch(() => setMe(null));
  }, []);

  React.useEffect(() => {
    if (!canSeeHrProcessesNav(me)) return;
    void loadReview();
  }, [loadReview, me]);

  const filteredEmployees = React.useMemo(() => {
    if (!review) return [];
    return filterEmployeesByStatusFilter(review.employees.items, statusFilter);
  }, [review, statusFilter]);

  const summary = React.useMemo(() => {
    if (!review) {
      return {
        totalChecked: 0,
        withDiscrepancies: 0,
        totalDiscrepancies: 0,
        fixed: 0,
        remaining: 0,
      };
    }
    return computeImportHrReviewSummary(review, summaryEmployees);
  }, [review, summaryEmployees]);

  const pageTitle = formatEtalonPeriodTitle(context?.reportPeriod || review?.summary.report_period);

  if (me && !canSeeHrProcessesNav(me)) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100">
        Недостаточно прав для проверки несоответствий контрольного списка.
      </div>
    );
  }

  if (me === null || !contextResolved) {
    return (
      <div className="py-8 text-center text-sm text-zinc-500" data-testid="import-hr-review-loading">
        Загрузка…
      </div>
    );
  }

  if (!context && !loading) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100">
          {error ?? IMPORT_HR_REVIEW_UI.noMrdHint}
        </div>
        <Link href="/directory/personnel/import#baselines" className="text-sm text-blue-700 hover:underline dark:text-blue-300">
          Перейти к журналу эталонов
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="import-hr-review-page">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{IMPORT_HR_REVIEW_UI.pageTitle}</h1>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">{IMPORT_HR_REVIEW_UI.pageLead}</p>
        {context?.reportPeriod || review?.summary.report_period ? (
          <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">
            {IMPORT_HR_REVIEW_UI.periodLabel}: <span className="font-medium">{pageTitle}</span>
          </p>
        ) : null}
      </div>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          {error}
        </div>
      ) : null}

      <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
        <div className="grid gap-3 lg:grid-cols-5">
          <label className="text-sm text-zinc-700 dark:text-zinc-300">
            <span className="mb-1 block">{IMPORT_HR_REVIEW_UI.groupFilterLabel}</span>
            <select
              value={orgGroupValue}
              onChange={(event) => {
                setOrgGroupValue(event.target.value);
                setDepartmentValue("");
                setExpandedMatchKey(null);
              }}
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              data-testid="import-review-org-group"
            >
              <option value="">Все группы</option>
              {review?.org_groups.map((group) => (
                <option key={group.value} value={group.value}>
                  {group.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm text-zinc-700 dark:text-zinc-300">
            <span className="mb-1 block">{IMPORT_HR_REVIEW_UI.departmentFilterLabel}</span>
            <select
              value={departmentValue}
              onChange={(event) => {
                setDepartmentValue(event.target.value);
                setExpandedMatchKey(null);
              }}
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              data-testid="import-review-department"
            >
              <option value="">Выберите отделение</option>
              {visibleDepartments.map((department) => (
                <option key={department.org_unit_id} value={departmentFilterOptionValue(department)}>
                  {department.org_unit_name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm text-zinc-700 dark:text-zinc-300 lg:col-span-2">
            <span className="mb-1 block">{IMPORT_HR_REVIEW_UI.searchLabel}</span>
            <input
              type="search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder={IMPORT_HR_REVIEW_UI.searchPlaceholder}
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              data-testid="import-review-search"
            />
          </label>
          <label className="text-sm text-zinc-700 dark:text-zinc-300">
            <span className="mb-1 block">{IMPORT_HR_REVIEW_UI.statusFilterLabel}</span>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as ImportHrReviewStatusFilter)}
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              data-testid="import-review-status"
            >
              {IMPORT_HR_REVIEW_STATUS_FILTER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      {!departmentFilter.org_unit_id ? (
        <div className="rounded-xl border border-zinc-200 px-4 py-8 text-center text-sm text-zinc-500 dark:border-zinc-800">
          {IMPORT_HR_REVIEW_UI.selectDepartmentHint}
        </div>
      ) : loading && !review ? (
        <div className="rounded-xl border border-zinc-200 px-4 py-8 text-center text-sm text-zinc-500 dark:border-zinc-800">
          Загрузка…
        </div>
      ) : (
        <>
          <section className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5" data-testid="import-review-summary">
            <SummaryCard
              label={IMPORT_HR_REVIEW_UI.summaryTotalChecked}
              value={summary.totalChecked}
              testId="summary-total-checked"
            />
            <SummaryCard
              label={IMPORT_HR_REVIEW_UI.summaryWithDiscrepancies}
              value={summary.withDiscrepancies}
              testId="summary-with-discrepancies"
            />
            <SummaryCard
              label={IMPORT_HR_REVIEW_UI.summaryTotalDiscrepancies}
              value={summary.totalDiscrepancies}
              testId="summary-total-discrepancies"
            />
            <SummaryCard label={IMPORT_HR_REVIEW_UI.summaryFixed} value={summary.fixed} testId="summary-fixed" />
            <SummaryCard
              label={IMPORT_HR_REVIEW_UI.summaryRemaining}
              value={summary.remaining}
              testId="summary-remaining"
            />
          </section>

          <section className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
            <div className="border-b border-zinc-100 bg-zinc-50 px-4 py-3 text-sm font-medium dark:border-zinc-800 dark:bg-zinc-900">
              {IMPORT_HR_REVIEW_UI.employeesSection} ({filteredEmployees.length})
            </div>
            {filteredEmployees.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-zinc-500">{IMPORT_HR_REVIEW_UI.employeesEmpty}</div>
            ) : (
              <div data-testid="import-review-employees-list">
                {filteredEmployees.map((employee) => (
                  <EmployeeRow
                    key={employee.match_key}
                    employee={employee}
                    departmentName={selectedDepartmentName}
                    expanded={expandedMatchKey === employee.match_key}
                    correctedValues={correctedValues}
                    onCorrectedValueChange={(differenceId, value) => {
                      setCorrectedValues((current) => ({ ...current, [differenceId]: value }));
                    }}
                    onToggle={() =>
                      setExpandedMatchKey((current) => (current === employee.match_key ? null : employee.match_key))
                    }
                  />
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
