"use client";

import * as React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { apiAuthMe } from "@/lib/api";
import { canSeeHrProcessesNav } from "@/lib/personnelNav";
import type { MeInfo } from "@/lib/types";

import {
  departmentFilterOptionValue,
  parseDepartmentFilterValue,
  parseGroupFilterValue,
  resolveGroupIdFromOptions,
} from "../_lib/importApi.client";
import { DIFFERENCE_ACTIONS_FOUNDATION_NOTE } from "../_lib/mrdDifferenceActions";
import {
  getMrdHrReview,
  mapMrdApiError,
  type HrReviewEmployee,
  type HrReviewResponse,
} from "../_lib/mrdApi.client";
import {
  formatEtalonPeriodTitle,
  formatMrdJournalStatusLabel,
  formatMrdReportPeriod,
  mrdJournalStatusClassName,
} from "../_lib/mrdDisplay";
import { buildMrdCreateWizardHref } from "../_lib/mrdForkNavigation";
import { formatMonthlyDiffValue } from "../_lib/monthlyDiffLabels";
import {
  collectExistingReportPeriods,
  evaluateCreateNextPeriodOffer,
} from "../_lib/mrdPeriodWindow";
import { hrDecisionStatusLabel, hrReviewStatusLabel } from "../_lib/mrdHrReviewLabels";
import { MRD_UI } from "../_lib/mrdUiLabels";

const IMPORT_REVIEW_HREF = "/directory/personnel/import/review";
const MIGRATION_HREF = "/directory/personnel/migration";
const BASELINES_JOURNAL_HREF = "/directory/personnel/import#baselines";

function actionButtonClassName(variant: "default" | "muted" | "danger" = "default"): string {
  const base =
    "inline-flex rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60";
  if (variant === "danger") {
    return `${base} border border-red-200 text-red-700 dark:border-red-900 dark:text-red-300`;
  }
  if (variant === "muted") {
    return `${base} border border-zinc-200 text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900`;
  }
  return `${base} border border-blue-200 text-blue-700 hover:bg-blue-50 dark:border-blue-900 dark:text-blue-300 dark:hover:bg-blue-950`;
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-zinc-200 px-3 py-2 dark:border-zinc-800">
      <div className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-zinc-900 dark:text-zinc-100">{value}</div>
    </div>
  );
}

function DifferenceActionBar() {
  return (
    <div className="mt-3 space-y-2">
      <div className="flex flex-wrap gap-2">
        <button type="button" className={actionButtonClassName()} disabled title={DIFFERENCE_ACTIONS_FOUNDATION_NOTE}>
          {MRD_UI.etalonConfirmAction}
        </button>
        <button type="button" className={actionButtonClassName("muted")} disabled title={DIFFERENCE_ACTIONS_FOUNDATION_NOTE}>
          {MRD_UI.etalonModifyConfirmAction}
        </button>
        <button type="button" className={actionButtonClassName("danger")} disabled title={DIFFERENCE_ACTIONS_FOUNDATION_NOTE}>
          {MRD_UI.etalonRejectAction}
        </button>
      </div>
      <p className="text-xs text-zinc-500">{DIFFERENCE_ACTIONS_FOUNDATION_NOTE}</p>
    </div>
  );
}

function EmployeeRow({
  employee,
  expanded,
  onToggle,
}: {
  employee: HrReviewEmployee;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="border-t border-zinc-100 dark:border-zinc-800" data-testid={`employee-row-${employee.match_key}`}>
      <button
        type="button"
        className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-zinc-50 dark:hover:bg-zinc-900/40"
        onClick={onToggle}
        aria-expanded={expanded}
      >
        <div className="min-w-0 flex-1">
          <div className="font-medium text-zinc-900 dark:text-zinc-100">{employee.full_name}</div>
          <div className="mt-0.5 text-sm text-zinc-600 dark:text-zinc-400">
            {employee.position_raw}
            {employee.rate ? ` · ${employee.rate}` : ""}
            {employee.category ? ` · ${employee.category}` : ""}
          </div>
        </div>
        <div className="shrink-0 text-right text-sm">
          <div className="font-medium">{employee.difference_count || "—"}</div>
          <div className="text-xs text-zinc-500">{hrReviewStatusLabel(employee.review_status)}</div>
        </div>
      </button>
      {expanded ? (
        <div className="border-t border-zinc-100 bg-zinc-50 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-900/30">
          {employee.differences.length === 0 ? (
            <p className="text-sm text-zinc-500">Изменений не обнаружено.</p>
          ) : (
            <div className="space-y-4">
              {employee.differences.map((diff) => (
                <article
                  key={diff.difference_id}
                  className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-950"
                  data-testid={`difference-${diff.difference_id}`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <h4 className="font-medium text-zinc-900 dark:text-zinc-100">{diff.field_label}</h4>
                    <span className="text-xs text-zinc-500">{hrDecisionStatusLabel(diff.decision_status)}</span>
                  </div>
                  <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-zinc-500">{MRD_UI.etalonDifferenceWas}</dt>
                      <dd className="mt-1">{formatMonthlyDiffValue(diff.old_value)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs uppercase tracking-wide text-zinc-500">{MRD_UI.etalonDifferenceDetected}</dt>
                      <dd className="mt-1">{formatMonthlyDiffValue(diff.detected_value ?? diff.new_value)}</dd>
                    </div>
                    {diff.source_label ? (
                      <div className="sm:col-span-2">
                        <dt className="text-xs uppercase tracking-wide text-zinc-500">{MRD_UI.etalonDifferenceSource}</dt>
                        <dd className="mt-1">{diff.source_label}</dd>
                      </div>
                    ) : null}
                  </dl>
                  <DifferenceActionBar />
                </article>
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

export default function MrdWorkspacePageClient() {
  const params = useParams<{ mrdId: string }>();
  const mrdId = Number(params.mrdId);

  const [me, setMe] = React.useState<MeInfo | null>(null);
  const [review, setReview] = React.useState<HrReviewResponse | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [orgGroupValue, setOrgGroupValue] = React.useState("");
  const [departmentValue, setDepartmentValue] = React.useState("");
  const [searchInput, setSearchInput] = React.useState("");
  const [changedOnly, setChangedOnly] = React.useState(true);
  const [expandedMatchKey, setExpandedMatchKey] = React.useState<string | null>(null);
  const [showSecondary, setShowSecondary] = React.useState(false);

  const departmentFilter = React.useMemo(() => parseDepartmentFilterValue(departmentValue), [departmentValue]);
  const groupFilter = React.useMemo(() => parseGroupFilterValue(orgGroupValue), [orgGroupValue]);

  const visibleDepartments = React.useMemo(() => {
    if (!review) return [];
    if (!orgGroupValue) return review.departments;
    const groupId = resolveGroupIdFromOptions({ groups: review.org_groups, departments: review.departments }, orgGroupValue);
    if (groupId) {
      return review.departments.filter((item) => item.org_group_id === groupId);
    }
    return review.departments;
  }, [orgGroupValue, review]);

  const loadReview = React.useCallback(async () => {
    if (!Number.isFinite(mrdId) || mrdId <= 0) {
      setError("Некорректный идентификатор эталона.");
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const data = await getMrdHrReview(mrdId, {
        org_group_id: groupFilter.org_group_id,
        effective_log_group: groupFilter.effective_log_group,
        org_unit_id: departmentFilter.org_unit_id,
        changed_only: changedOnly,
        search: searchInput.trim() || null,
      });
      setReview(data);
      setError(null);
    } catch (e) {
      setReview(null);
      setError(mapMrdApiError(e));
    } finally {
      setLoading(false);
    }
  }, [changedOnly, departmentFilter.org_unit_id, groupFilter.effective_log_group, groupFilter.org_group_id, mrdId, searchInput]);

  React.useEffect(() => {
    void apiAuthMe()
      .then((data) => setMe(data))
      .catch(() => setMe(null));
  }, []);

  React.useEffect(() => {
    if (!canSeeHrProcessesNav(me)) return;
    void loadReview();
  }, [loadReview, me]);

  const createOffer = React.useMemo(() => {
    if (!review?.summary) return null;
    const existing = collectExistingReportPeriods([review.summary]);
    return evaluateCreateNextPeriodOffer(review.summary.report_period, existing);
  }, [review]);

  if (me && !canSeeHrProcessesNav(me)) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100">
        {MRD_UI.insufficientPermissions}
      </div>
    );
  }

  if (loading && !review) {
    return (
      <div className="rounded-xl border border-zinc-200 px-4 py-8 text-center text-sm text-zinc-500 dark:border-zinc-800">
        Загрузка…
      </div>
    );
  }

  if (error || !review) {
    return (
      <div className="space-y-4">
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          {error ?? "Эталон не найден."}
        </div>
        <Link href={BASELINES_JOURNAL_HREF} className="text-sm text-blue-700 hover:underline dark:text-blue-300">
          {MRD_UI.journalLink}
        </Link>
      </div>
    );
  }

  const title = formatEtalonPeriodTitle(review.summary.report_period);
  const summary = review.department_summary;

  return (
    <div className="space-y-6" data-testid="mrd-etalon-page">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{title}</h1>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            <span className={mrdJournalStatusClassName(review.summary)}>
              {formatMrdJournalStatusLabel(review.summary)}
            </span>
            <span className="mx-2">·</span>
            Записей в эталоне: {review.summary.entry_count}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {createOffer?.allowed && createOffer.targetPeriod ? (
            <Link
              href={buildMrdCreateWizardHref({
                sourceMrdId: review.summary.mrd_id,
                targetPeriod: createOffer.targetPeriod,
              })}
              className={actionButtonClassName()}
            >
              {MRD_UI.createNextPeriodAction}
            </Link>
          ) : null}
          <Link href={BASELINES_JOURNAL_HREF} className={actionButtonClassName("muted")}>
            {MRD_UI.journalLink}
          </Link>
        </div>
      </div>

      <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
        <div className="grid gap-3 lg:grid-cols-4">
          <label className="text-sm text-zinc-700 dark:text-zinc-300">
            <span className="mb-1 block">{MRD_UI.etalonGroupLabel}</span>
            <select
              value={orgGroupValue}
              onChange={(event) => {
                setOrgGroupValue(event.target.value);
                setDepartmentValue("");
                setExpandedMatchKey(null);
              }}
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              data-testid="etalon-org-group"
            >
              <option value="">Все группы</option>
              {review.org_groups.map((group) => (
                <option key={group.value} value={group.value}>
                  {group.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm text-zinc-700 dark:text-zinc-300">
            <span className="mb-1 block">{MRD_UI.etalonDepartmentLabel}</span>
            <select
              value={departmentValue}
              onChange={(event) => {
                setDepartmentValue(event.target.value);
                setExpandedMatchKey(null);
              }}
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              data-testid="etalon-department"
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
            <span className="mb-1 block">{MRD_UI.etalonSearchLabel}</span>
            <input
              type="search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder={MRD_UI.etalonSearchPlaceholder}
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              data-testid="etalon-search"
            />
          </label>
        </div>
        <div className="mt-3 flex flex-wrap gap-4 text-sm text-zinc-700 dark:text-zinc-300">
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="employee-mode"
              checked={changedOnly}
              onChange={() => setChangedOnly(true)}
              data-testid="etalon-changed-only"
            />
            {MRD_UI.etalonChangedOnly}
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="employee-mode"
              checked={!changedOnly}
              onChange={() => setChangedOnly(false)}
              data-testid="etalon-all-employees"
            />
            {MRD_UI.etalonAllEmployees}
          </label>
        </div>
      </section>

      {!departmentFilter.org_unit_id ? (
        <div className="rounded-xl border border-zinc-200 px-4 py-8 text-center text-sm text-zinc-500 dark:border-zinc-800">
          {MRD_UI.etalonSelectDepartmentHint}
        </div>
      ) : (
        <>
          {summary ? (
            <section className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6" data-testid="etalon-department-summary">
              <SummaryCard label={MRD_UI.etalonSummaryTotal} value={summary.total_employees} />
              <SummaryCard label={MRD_UI.etalonSummaryWithoutChanges} value={summary.without_changes} />
              <SummaryCard label={MRD_UI.etalonSummaryWithChanges} value={summary.with_changes} />
              <SummaryCard label={MRD_UI.etalonSummaryAwaiting} value={summary.awaiting_decision} />
              <SummaryCard label={MRD_UI.etalonSummaryConfirmed} value={summary.confirmed} />
              <SummaryCard label={MRD_UI.etalonSummaryRejected} value={summary.rejected} />
            </section>
          ) : null}

          <section className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
            <div className="border-b border-zinc-100 bg-zinc-50 px-4 py-3 text-sm font-medium dark:border-zinc-800 dark:bg-zinc-900">
              Сотрудники ({review.employees.total})
            </div>
            {review.employees.items.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-zinc-500">{MRD_UI.etalonEmployeesEmpty}</div>
            ) : (
              <div data-testid="etalon-employees-list">
                {review.employees.items.map((employee) => (
                  <EmployeeRow
                    key={employee.match_key}
                    employee={employee}
                    expanded={expandedMatchKey === employee.match_key}
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

      <section className="rounded-xl border border-zinc-200 dark:border-zinc-800">
        <button
          type="button"
          className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium"
          onClick={() => setShowSecondary((value) => !value)}
        >
          {MRD_UI.secondaryLinksTitle}
          <span className="text-zinc-400">{showSecondary ? "▾" : "▸"}</span>
        </button>
        {showSecondary ? (
          <div className="flex flex-wrap gap-2 border-t border-zinc-100 px-4 py-3 dark:border-zinc-800">
            <Link href={IMPORT_REVIEW_HREF} className={actionButtonClassName("muted")}>
              {MRD_UI.secondaryImportReviewLink}
            </Link>
            <Link href={MIGRATION_HREF} className={actionButtonClassName("muted")}>
              {MRD_UI.secondaryMigrationLink}
            </Link>
            <span className={actionButtonClassName("muted")} title="Журнал подтверждённых изменений доступен в дополнительном разделе">
              {MRD_UI.secondaryConfirmedJournalLink}
            </span>
            <span className="text-xs text-zinc-500 self-center">
              {MRD_UI.secondaryTechnicalInfoLink}: период {formatMrdReportPeriod(review.summary.report_period)}, записей{" "}
              {review.summary.entry_count}
            </span>
          </div>
        ) : null}
      </section>
    </div>
  );
}
