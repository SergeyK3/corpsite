"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { apiAuthMe } from "@/lib/api";
import { canSeeHrProcessesNav } from "@/lib/personnelNav";
import type { MeInfo } from "@/lib/types";

import {
  departmentFilterOptionValue,
  getDepartmentRecodingOptions,
  getImportSummary,
  getRowReviewDetail,
  getSheetDiagnostics,
  getInitialBaselineSourceSelection,
  listImportBatches,
  listStagingRows,
  mapImportApiError,
  parseDepartmentFilterValue,
  parseGroupFilterValue,
  resolveGroupIdFromOptions,
  type DepartmentRecodingOptions,
  type ImportBatchRow,
  type ImportSummary,
  type RowReviewDetail,
  type SheetDiagnostics,
  type StagingRow,
} from "../_lib/importApi.client";
import {
  buildCreateInitialMrdPayload,
  buildImportDataIssueSummary,
  buildInitialBaselineFieldRows,
  collectRowIssues,
  describeImportBatchOption,
  evaluateRowReadiness,
  personMatchSummary,
  selectSuitableControlListImports,
  summarizeInitialBaselineRows,
  normalizeImportBatchPeriod,
} from "../_lib/importInitialBaseline";
import { buildNormalizedRecordsReviewHref } from "../_lib/importInitialBaselineNavigation";
import {
  INITIAL_BASELINE_UI,
  PERSON_MATCH_LABELS,
  READINESS_STATUS_LABELS,
  importRowIssueLabel,
} from "../_lib/importInitialBaselineLabels";
import { createMrdCommandId } from "../_lib/mrdApi.client";
import { formatEtalonPeriodTitle, formatMrdReportPeriod } from "../_lib/mrdDisplay";
import NormalizedRecordsSummaryPanel from "./NormalizedRecordsSummaryPanel";

function actionButtonClassName(): string {
  return "inline-flex rounded-lg border border-blue-200 px-3 py-1.5 text-sm font-medium text-blue-700 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-blue-900 dark:text-blue-300 dark:hover:bg-blue-950";
}

function SummaryCard({ label, value, testId }: { label: string; value: number; testId: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 px-3 py-2 dark:border-zinc-800" data-testid={testId}>
      <div className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-zinc-900 dark:text-zinc-100">{value}</div>
    </div>
  );
}

function readinessClassName(status: string): string {
  if (status === "ready") {
    return "border-green-200 bg-green-100 text-green-900 dark:border-green-800 dark:bg-green-950/50 dark:text-green-200";
  }
  if (status === "blocked") {
    return "border-red-200 bg-red-100 text-red-900 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200";
  }
  return "border-amber-200 bg-amber-100 text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200";
}

export default function ImportInitialBaselinePageClient() {
  const searchParams = useSearchParams();
  const reportPeriod = (searchParams.get("report_period") || "2026-06-01").slice(0, 10);
  const blockedPeriod = searchParams.get("blocked_period");
  const initialBatchId = searchParams.get("batch_id");

  const [me, setMe] = React.useState<MeInfo | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [imports, setImports] = React.useState<ImportBatchRow[]>([]);
  const [pendingReviewBatchId, setPendingReviewBatchId] = React.useState<number | null>(null);
  const [selectedBatchId, setSelectedBatchId] = React.useState<string>("");
  const [summary, setSummary] = React.useState<ImportSummary | null>(null);
  const [diagnostics, setDiagnostics] = React.useState<SheetDiagnostics | null>(null);
  const [issueRows, setIssueRows] = React.useState<StagingRow[]>([]);
  const [rows, setRows] = React.useState<StagingRow[]>([]);
  const [totalRows, setTotalRows] = React.useState(0);
  const [options, setOptions] = React.useState<DepartmentRecodingOptions | null>(null);
  const [orgGroupValue, setOrgGroupValue] = React.useState("");
  const [departmentValue, setDepartmentValue] = React.useState("");
  const [searchInput, setSearchInput] = React.useState("");
  const [expandedRowId, setExpandedRowId] = React.useState<number | null>(null);
  const [rowDetails, setRowDetails] = React.useState<Record<number, RowReviewDetail | null>>({});
  const [manualValues, setManualValues] = React.useState<Record<string, string>>({});

  const completeReviewBatchId = React.useMemo(() => {
    if (initialBatchId && /^\d+$/.test(initialBatchId)) {
      return Number(initialBatchId);
    }
    return pendingReviewBatchId;
  }, [initialBatchId, pendingReviewBatchId]);

  const completeReviewHref = buildNormalizedRecordsReviewHref(completeReviewBatchId);

  const batchId = selectedBatchId ? Number(selectedBatchId) : null;
  const selectedBatch = React.useMemo(
    () => imports.find((item) => item.batch_id === batchId) ?? null,
    [batchId, imports],
  );
  const departmentFilter = React.useMemo(() => parseDepartmentFilterValue(departmentValue), [departmentValue]);
  const groupFilter = React.useMemo(() => parseGroupFilterValue(orgGroupValue), [orgGroupValue]);

  const visibleDepartments = React.useMemo(() => {
    if (!options) return [];
    if (!orgGroupValue) return options.departments;
    const groupId = resolveGroupIdFromOptions(options, orgGroupValue);
    if (!groupId) return options.departments;
    return options.departments.filter((item) => item.org_group_id === groupId);
  }, [options, orgGroupValue]);

  const readinessSummary = React.useMemo(
    () => summarizeInitialBaselineRows(rows, rowDetails),
    [rowDetails, rows],
  );

  const issueSummary = React.useMemo(() => {
    if (!selectedBatch || !summary || !diagnostics) return null;
    return buildImportDataIssueSummary({
      batch: selectedBatch,
      summary,
      diagnostics,
      issueRows,
    });
  }, [diagnostics, issueRows, selectedBatch, summary]);

  const createDisabled = readinessSummary.blockedRows > 0 || readinessSummary.needsReviewRows > 0 || rows.length === 0;
  const createActionLabel = `Создать эталон ${formatMrdReportPeriod(reportPeriod)}`;

  React.useEffect(() => {
    void apiAuthMe()
      .then(setMe)
      .catch(() => setMe(null));
  }, []);

  React.useEffect(() => {
    getDepartmentRecodingOptions()
      .then(setOptions)
      .catch(() => setOptions(null));
  }, []);

  React.useEffect(() => {
    if (!canSeeHrProcessesNav(me)) return;
    setLoading(true);
    Promise.all([listImportBatches(), getInitialBaselineSourceSelection(reportPeriod)])
      .then(([data, selectionData]) => {
        const suitable = selectSuitableControlListImports(data.items, reportPeriod);
        const targetMonth = reportPeriod.slice(0, 7);
        const awaitingReview = data.items.find((item) => {
          if (item.status !== "IN_REVIEW") return false;
          return normalizeImportBatchPeriod(item) === targetMonth;
        });
        setPendingReviewBatchId(awaitingReview?.batch_id ?? null);
        setImports(suitable);
        const savedBatchId = selectionData.item?.source_batch_id;
        const savedBatchIdString =
          savedBatchId != null &&
          selectionData.item?.mutable !== false &&
          suitable.some((item) => item.batch_id === savedBatchId)
            ? String(savedBatchId)
            : null;
        if (initialBatchId && suitable.some((item) => String(item.batch_id) === initialBatchId)) {
          setSelectedBatchId(initialBatchId);
        } else if (savedBatchIdString) {
          setSelectedBatchId(savedBatchIdString);
        } else if (suitable.length === 1) {
          setSelectedBatchId(String(suitable[0].batch_id));
        } else {
          setSelectedBatchId("");
        }
        setError(suitable.length === 0 ? INITIAL_BASELINE_UI.noImportsHint : null);
      })
      .catch((e) => setError(mapImportApiError(e)))
      .finally(() => setLoading(false));
  }, [initialBatchId, me, reportPeriod]);

  React.useEffect(() => {
    if (!batchId) {
      setSummary(null);
      setDiagnostics(null);
      setIssueRows([]);
      setRows([]);
      setTotalRows(0);
      return;
    }

    setLoading(true);
    Promise.all([
      getImportSummary(batchId),
      getSheetDiagnostics(batchId),
      listStagingRows(batchId, {
        roster_scope: "personnel",
        staff_types: "doctors,nurses",
        hide_unchanged: false,
        limit: 500,
        offset: 0,
      }),
    ])
      .then(([importSummary, sheetDiagnostics, issueListData]) => {
        setSummary(importSummary);
        setDiagnostics(sheetDiagnostics);
        setIssueRows(issueListData.items);
        setError(null);
      })
      .catch((e) => setError(mapImportApiError(e)))
      .finally(() => setLoading(false));
  }, [batchId]);

  React.useEffect(() => {
    if (!batchId) return;

    setLoading(true);
    listStagingRows(batchId, {
      roster_scope: "personnel",
      staff_types: "doctors,nurses",
      org_group_id: groupFilter.org_group_id,
      effective_log_group: groupFilter.effective_log_group,
      org_unit_id: departmentFilter.org_unit_id,
      q_name: searchInput.trim() || undefined,
      hide_unchanged: false,
      limit: 200,
      offset: 0,
    })
      .then((listData) => {
        setRows(listData.items);
        setTotalRows(listData.total);
        setError(null);
      })
      .catch((e) => setError(mapImportApiError(e)))
      .finally(() => setLoading(false));
  }, [batchId, departmentFilter.org_unit_id, groupFilter.effective_log_group, groupFilter.org_group_id, searchInput]);

  React.useEffect(() => {
    if (!batchId || expandedRowId == null) return;
    if (rowDetails[expandedRowId]) return;
    getRowReviewDetail(batchId, expandedRowId)
      .then((detail) => {
        setRowDetails((current) => ({ ...current, [expandedRowId]: detail }));
      })
      .catch((e) => setError(mapImportApiError(e)));
  }, [batchId, expandedRowId, rowDetails]);

  if (me && !canSeeHrProcessesNav(me)) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        Недостаточно прав для формирования эталона.
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="import-initial-baseline-page">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{INITIAL_BASELINE_UI.pageTitle}</h1>
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">{INITIAL_BASELINE_UI.pageLead}</p>
        <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">
          Период: <span className="font-medium">{formatEtalonPeriodTitle(reportPeriod)}</span>
        </p>
      </div>

      {blockedPeriod ? (
        <div
          className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100"
          data-testid="initial-baseline-blocked-notice"
        >
          {INITIAL_BASELINE_UI.blockedJulyNotice}
        </div>
      ) : null}

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          <p>{error}</p>
          {error === INITIAL_BASELINE_UI.noImportsHint ? (
            <Link
              href={completeReviewHref}
              className="mt-2 inline-flex font-medium text-blue-700 underline dark:text-blue-300"
              data-testid="initial-baseline-complete-review-link"
            >
              {completeReviewBatchId ? "Завершить проверку выбранного импорта" : "Открыть проверку нормализованных записей"}
            </Link>
          ) : null}
        </div>
      ) : null}

      <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
        <label className="block text-sm text-zinc-700 dark:text-zinc-300">
          <span className="mb-1 block">{INITIAL_BASELINE_UI.importPickerLabel}</span>
          {imports.length === 0 ? (
            loading ? (
              <p className="text-sm text-zinc-500">Загрузка…</p>
            ) : (
              <div className="space-y-2">
                <p className="text-sm text-zinc-500">{INITIAL_BASELINE_UI.noImportsHint}</p>
                <Link
                  href={completeReviewHref}
                  className="inline-flex text-sm font-medium text-blue-700 underline dark:text-blue-300"
                  data-testid="initial-baseline-complete-review-link-picker"
                >
                  {completeReviewBatchId ? "Завершить проверку выбранного импорта" : "Открыть проверку нормализованных записей"}
                </Link>
              </div>
            )
          ) : (
            <select
              value={selectedBatchId}
              onChange={(event) => {
                setSelectedBatchId(event.target.value);
                setExpandedRowId(null);
              }}
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              data-testid="initial-baseline-import-picker"
            >
              <option value="">{INITIAL_BASELINE_UI.importPickerHint}</option>
              {imports.map((item) => (
                <option key={item.batch_id} value={String(item.batch_id)}>
                  {describeImportBatchOption(item)}
                </option>
              ))}
            </select>
          )}
        </label>
      </section>

      {batchId ? (
        <>
          <NormalizedRecordsSummaryPanel batchId={batchId} />

          <section className="space-y-4" data-testid="import-data-issue-summary">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
              {INITIAL_BASELINE_UI.summaryTitle}
            </h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              <SummaryCard
                label={INITIAL_BASELINE_UI.summaryTotalRows}
                value={issueSummary?.totalRows ?? 0}
                testId="summary-total-rows"
              />
              <SummaryCard
                label={INITIAL_BASELINE_UI.summaryRowsWithoutErrors}
                value={issueSummary?.rowsWithoutErrors ?? 0}
                testId="summary-rows-without-errors"
              />
              <SummaryCard
                label={INITIAL_BASELINE_UI.summaryRowsWithErrors}
                value={issueSummary?.rowsWithErrors ?? 0}
                testId="summary-rows-with-errors"
              />
              <SummaryCard
                label={INITIAL_BASELINE_UI.summaryTotalIssues}
                value={issueSummary?.totalIssueCount ?? 0}
                testId="summary-total-issues"
              />
              <SummaryCard
                label={INITIAL_BASELINE_UI.summaryEmployeesWithErrors}
                value={issueSummary?.employeesWithErrors ?? 0}
                testId="summary-employees-with-errors"
              />
            </div>
            {issueSummary && issueSummary.issueCountsByCode.length > 0 ? (
              <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                  {INITIAL_BASELINE_UI.summaryIssuesByCodeTitle}
                </h3>
                <dl className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {issueSummary.issueCountsByCode.map((item) => (
                    <div
                      key={item.code}
                      className="flex items-center justify-between rounded-lg border border-zinc-100 px-3 py-2 text-sm dark:border-zinc-800"
                      data-testid={`summary-issue-${item.code}`}
                    >
                      <dt className="text-zinc-700 dark:text-zinc-300">{importRowIssueLabel(item.code)}</dt>
                      <dd className="font-semibold text-zinc-900 dark:text-zinc-100">{item.count}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ) : null}
          </section>

          <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <div className="grid gap-3 lg:grid-cols-4">
              <label className="text-sm text-zinc-700 dark:text-zinc-300">
                <span className="mb-1 block">Группа отделений</span>
                <select
                  value={orgGroupValue}
                  onChange={(event) => {
                    setOrgGroupValue(event.target.value);
                    setDepartmentValue("");
                  }}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
                  data-testid="initial-baseline-org-group"
                >
                  <option value="">Все группы</option>
                  {options?.groups.map((group) => (
                    <option key={group.value} value={group.value}>
                      {group.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm text-zinc-700 dark:text-zinc-300">
                <span className="mb-1 block">Отделение</span>
                <select
                  value={departmentValue}
                  onChange={(event) => setDepartmentValue(event.target.value)}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
                  data-testid="initial-baseline-department"
                >
                  <option value="">Все отделения</option>
                  {visibleDepartments.map((department) => (
                    <option key={departmentFilterOptionValue(department)} value={departmentFilterOptionValue(department)}>
                      {department.org_unit_name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm text-zinc-700 dark:text-zinc-300 lg:col-span-2">
                <span className="mb-1 block">Поиск по ФИО</span>
                <input
                  type="search"
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
                  data-testid="initial-baseline-search"
                />
              </label>
            </div>
          </section>

          <section className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
            <div className="border-b border-zinc-100 bg-zinc-50 px-4 py-3 text-sm font-medium dark:border-zinc-800 dark:bg-zinc-900">
              {INITIAL_BASELINE_UI.peopleTitle} ({totalRows})
            </div>
            {loading ? (
              <div className="px-4 py-8 text-center text-sm text-zinc-500">Загрузка…</div>
            ) : rows.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-zinc-500">Люди не найдены по выбранным фильтрам.</div>
            ) : (
              <div data-testid="initial-baseline-people-list">
                {rows.map((row) => {
                  const detail = rowDetails[row.row_id] ?? null;
                  const readiness = evaluateRowReadiness(row, detail);
                  const issues = collectRowIssues(row);
                  const match = detail ? personMatchSummary(detail) : { code: "unknown" as const, label: "unknown" };
                  const expanded = expandedRowId === row.row_id;
                  const fieldRows = buildInitialBaselineFieldRows(row, detail);

                  return (
                    <div key={row.row_id} className="border-t border-zinc-100 dark:border-zinc-800" data-testid={`initial-person-row-${row.row_id}`}>
                      <div className="flex flex-wrap items-start gap-3 px-4 py-3">
                        <div className="min-w-0 flex-1">
                          <div className="font-medium text-zinc-900 dark:text-zinc-100">{row.full_name || "—"}</div>
                          <div className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                            {row.org_unit_name || row.department || "—"} · {row.position_raw || "—"}
                          </div>
                          {issues.length > 0 ? (
                            <ul className="mt-2 flex flex-wrap gap-2 text-xs">
                              {issues.map((issue) => (
                                <li key={`${row.row_id}-${issue}`} className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-amber-900">
                                  {importRowIssueLabel(issue)}
                                </li>
                              ))}
                            </ul>
                          ) : null}
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-2">
                          <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${readinessClassName(readiness)}`}>
                            {READINESS_STATUS_LABELS[readiness]}
                          </span>
                          <button
                            type="button"
                            className={actionButtonClassName()}
                            onClick={() => setExpandedRowId((current) => (current === row.row_id ? null : row.row_id))}
                            data-testid={`initial-fix-data-${row.row_id}`}
                          >
                            {INITIAL_BASELINE_UI.fixDataAction}
                          </button>
                        </div>
                      </div>

                      {expanded ? (
                        <div className="border-t border-zinc-100 bg-zinc-50 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-900/30">
                          <div className="mb-4 grid gap-2 text-sm sm:grid-cols-2">
                            <div>
                              <div className="text-xs uppercase tracking-wide text-zinc-500">{INITIAL_BASELINE_UI.personMatchLabel}</div>
                              <div className="mt-1">{PERSON_MATCH_LABELS[match.code]}</div>
                            </div>
                            <div>
                              <div className="text-xs uppercase tracking-wide text-zinc-500">{INITIAL_BASELINE_UI.readinessLabel}</div>
                              <div className="mt-1">{READINESS_STATUS_LABELS[readiness]}</div>
                            </div>
                          </div>
                          <div className="space-y-4">
                            {fieldRows.map((field) => {
                              const manualKey = `${row.row_id}:${field.key}`;
                              return (
                                <article key={manualKey} className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-950">
                                  <div className="text-xs uppercase tracking-wide text-zinc-500">{field.section}</div>
                                  <h4 className="font-medium text-zinc-900 dark:text-zinc-100">{field.label}</h4>
                                  <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                                    <div>
                                      <dt className="text-xs uppercase tracking-wide text-zinc-500">{INITIAL_BASELINE_UI.sourceValueLabel}</dt>
                                      <dd className="mt-1">{field.sourceValue}</dd>
                                    </div>
                                    <div>
                                      <dt className="text-xs uppercase tracking-wide text-zinc-500">{INITIAL_BASELINE_UI.normalizedValueLabel}</dt>
                                      <dd className="mt-1">{field.normalizedValue}</dd>
                                    </div>
                                    <div className="sm:col-span-2">
                                      <dt className="text-xs uppercase tracking-wide text-zinc-500">{INITIAL_BASELINE_UI.manualValueLabel}</dt>
                                      <dd className="mt-1">
                                        <input
                                          type="text"
                                          value={manualValues[manualKey] ?? (field.needsManualInput ? "" : field.normalizedValue === "—" ? "" : field.normalizedValue)}
                                          onChange={(event) =>
                                            setManualValues((current) => ({ ...current, [manualKey]: event.target.value }))
                                          }
                                          className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
                                          data-testid={`initial-manual-${row.row_id}-${field.key}`}
                                        />
                                      </dd>
                                    </div>
                                  </dl>
                                </article>
                              );
                            })}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <button
              type="button"
              className={actionButtonClassName()}
              disabled
              title={INITIAL_BASELINE_UI.createBaselineDisabledNote}
              data-testid="initial-baseline-create-action"
              onClick={() => {
                void buildCreateInitialMrdPayload({
                  commandId: createMrdCommandId("create-initial-mrd"),
                  batchId,
                  reportPeriod,
                  reviewedRowIds: rows.map((row) => row.row_id),
                  fieldCorrections: Object.entries(manualValues).map(([key, correctedValue]) => {
                    const [rowId, fieldPath] = key.split(":");
                    return { row_id: Number(rowId), field_path: fieldPath, corrected_value: correctedValue };
                  }),
                });
              }}
            >
              {createActionLabel}
            </button>
            <p className="mt-2 text-xs text-zinc-500">{INITIAL_BASELINE_UI.createBaselineDisabledNote}</p>
            <p className="mt-1 text-xs text-zinc-500">{INITIAL_BASELINE_UI.createBaselineFoundationNote}</p>
          </section>
        </>
      ) : null}

      <div className="text-sm">
        <Link href="/directory/personnel/import#baselines" className="text-blue-700 hover:underline dark:text-blue-300">
          Вернуться к журналу эталонов
        </Link>
      </div>
    </div>
  );
}
