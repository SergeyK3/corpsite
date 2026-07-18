"use client";

import * as React from "react";

import {
  mapImportApiError,
  promoteImportRosterBatch,
  type RosterPromotionItem,
  type RosterPromotionOutcome,
} from "../_lib/importApi.client";
import {
  buildReasonSummary,
  buildReasonTypeSummary,
  buildRosterPromotionOverview,
  collectDepartmentOptions,
  EMPTY_ROSTER_PROMOTION_FILTERS,
  filterRosterPromotionItems,
  hasActiveRosterPromotionFilters,
  normalizeReasonLabel,
  ROSTER_PROMOTION_OUTCOME_LABELS,
  shouldShowReasonDetails,
  type RosterPromotionFilters,
} from "../_lib/importRosterPromotionAnalysis";
import { HR_DOSSIER_PLURAL, HR_DOSSIER_PLURAL_TITLE } from "@/lib/personnelCardTerminology";

const FILTER_OUTCOMES: RosterPromotionOutcome[] = [
  "would_create",
  "would_update",
  "already_linked",
  "blocked",
  "conflict",
];

function outcomeBadgeClass(outcome: RosterPromotionOutcome): string {
  switch (outcome) {
    case "would_create":
      return "border-blue-200 bg-blue-50 text-blue-900";
    case "would_update":
      return "border-indigo-200 bg-indigo-50 text-indigo-900";
    case "already_linked":
      return "border-green-200 bg-green-50 text-green-900";
    case "conflict":
      return "border-orange-200 bg-orange-50 text-orange-900";
    case "blocked":
      return "border-red-200 bg-red-50 text-red-900";
    default:
      return "border-zinc-200 bg-zinc-50 text-zinc-800";
  }
}

function OverviewMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2 dark:border-zinc-800">
      <div className="text-[11px] uppercase tracking-[0.08em] text-zinc-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-zinc-900 dark:text-zinc-100">{value}</div>
    </div>
  );
}

type Props = {
  batchId: number;
};

export default function ImportRosterPromotionPanel({ batchId }: Props) {
  const [loading, setLoading] = React.useState(false);
  const [preview, setPreview] = React.useState<RosterPromotionItem[]>([]);
  const [summary, setSummary] = React.useState<Record<string, number>>({});
  const [error, setError] = React.useState<string | null>(null);
  const [applied, setApplied] = React.useState(false);
  const [filters, setFilters] = React.useState<RosterPromotionFilters>(EMPTY_ROSTER_PROMOTION_FILTERS);

  const loadPreview = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await promoteImportRosterBatch(batchId, { dry_run: true });
      setPreview(data.items);
      setSummary(data.summary || {});
      setApplied(false);
    } catch (e) {
      setError(mapImportApiError(e));
      setPreview([]);
      setSummary({});
    } finally {
      setLoading(false);
    }
  }, [batchId]);

  React.useEffect(() => {
    if (batchId > 0) {
      loadPreview();
    }
  }, [batchId, loadPreview]);

  React.useEffect(() => {
    setFilters(EMPTY_ROSTER_PROMOTION_FILTERS);
  }, [batchId]);

  async function applyPromotion() {
    setLoading(true);
    setError(null);
    try {
      const data = await promoteImportRosterBatch(batchId, { dry_run: false });
      setPreview(data.items);
      setSummary(data.summary || {});
      setApplied(true);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setLoading(false);
    }
  }

  const actionable = preview.filter((item) =>
    ["would_create", "would_update"].includes(item.outcome)
  ).length;

  const reasonTypeSummary = React.useMemo(() => buildReasonTypeSummary(preview), [preview]);
  const reasonSummary = React.useMemo(() => buildReasonSummary(preview), [preview]);
  const overview = React.useMemo(
    () => buildRosterPromotionOverview(preview, summary as Partial<Record<RosterPromotionOutcome, number>>),
    [preview, summary]
  );
  const departmentOptions = React.useMemo(() => collectDepartmentOptions(preview), [preview]);
  const filteredItems = React.useMemo(() => filterRosterPromotionItems(preview, filters), [preview, filters]);
  const filtersActive = hasActiveRosterPromotionFilters(filters);

  function updateFilter<K extends keyof RosterPromotionFilters>(key: K, value: RosterPromotionFilters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  function resetFilters() {
    setFilters(EMPTY_ROSTER_PROMOTION_FILTERS);
  }

  function selectReasonType(typeKey: string) {
    setFilters((prev) => {
      const nextTypeKey = prev.reasonTypeKey === typeKey && !prev.reasonKey ? "" : typeKey;
      return {
        ...prev,
        reasonTypeKey: nextTypeKey,
        reasonKey: "",
      };
    });
  }

  function selectReasonDetail(reasonKey: string) {
    setFilters((prev) => ({
      ...prev,
      reasonTypeKey: "",
      reasonKey: prev.reasonKey === reasonKey ? "" : reasonKey,
    }));
  }

  function selectionClass(selected: boolean): string {
    return selected
      ? "border border-blue-300 bg-blue-50 text-blue-950 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-100"
      : "border border-transparent hover:border-zinc-200 hover:bg-zinc-50 dark:hover:border-zinc-700 dark:hover:bg-zinc-900";
  }

  return (
    <section className="mb-6 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            Сотрудники из импорта
          </h2>
          <p className="mt-1 text-sm text-zinc-500">
            Создание карточек сотрудников в справочнике по строкам roster batch #{batchId}. Выполните
            перед promotion документов.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={loading}
            onClick={loadPreview}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm disabled:opacity-50 dark:border-zinc-700"
          >
            Dry Run
          </button>
          <button
            type="button"
            disabled={loading || actionable === 0}
            onClick={applyPromotion}
            className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Создать/обновить {HR_DOSSIER_PLURAL}
          </button>
        </div>
      </div>

      {error ? (
        <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      {applied ? (
        <div className="mb-3 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900">
          {HR_DOSSIER_PLURAL_TITLE} обновлены. Можно переходить к promotion документов.
        </div>
      ) : null}

      {loading ? (
        <div className="py-6 text-center text-sm text-zinc-500">Загрузка…</div>
      ) : preview.length === 0 ? (
        <div className="py-6 text-center text-sm text-zinc-500">Нет roster-строк для promotion</div>
      ) : (
        <>
          <section
            className="mb-4 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800"
            data-testid="roster-promotion-overview"
          >
            <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Итоги анализа</h3>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
              <OverviewMetric label="Всего сотрудников" value={overview.total} />
              <OverviewMetric label="Будет создано" value={overview.wouldCreate} />
              <OverviewMetric label="Будет обновлено" value={overview.wouldUpdate} />
              <OverviewMetric label="Уже привязано" value={overview.alreadyLinked} />
              <OverviewMetric label="Ошибок" value={overview.errors} />
              <OverviewMetric label="Конфликтов" value={overview.conflicts} />
              <OverviewMetric
                label="Частая проблема"
                value={
                  overview.topProblem
                    ? `${overview.topProblem.label} (${overview.topProblem.count})`
                    : "—"
                }
              />
            </div>
          </section>

          {reasonTypeSummary.length > 0 ? (
            <section
              className="mb-4 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800"
              data-testid="roster-reason-summary"
            >
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Сводка причин</h3>
                {filtersActive ? (
                  <button
                    type="button"
                    onClick={resetFilters}
                    className="text-xs text-blue-600 hover:underline dark:text-blue-400"
                  >
                    Сбросить фильтры
                  </button>
                ) : null}
              </div>
              <div className="max-h-72 space-y-2 overflow-y-auto">
                {reasonTypeSummary.map((typeRow) => {
                  const typeSelected =
                    filters.reasonTypeKey === typeRow.typeKey && !filters.reasonKey;
                  return (
                    <div key={typeRow.typeKey} className="space-y-1">
                      <button
                        type="button"
                        data-testid={`roster-reason-type-${typeRow.typeKey}`}
                        onClick={() => selectReasonType(typeRow.typeKey)}
                        className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm font-medium transition ${selectionClass(typeSelected)}`}
                      >
                        <span>{typeRow.typeLabel}</span>
                        <span className="ml-3 shrink-0 font-mono text-xs">{typeRow.count}</span>
                      </button>
                      {shouldShowReasonDetails(typeRow)
                        ? typeRow.details.map((detail) => {
                            const detailSelected = filters.reasonKey === detail.reasonKey;
                            return (
                              <button
                                key={detail.detailKey}
                                type="button"
                                data-testid={`roster-reason-detail-${detail.reasonKey}`}
                                onClick={() => selectReasonDetail(detail.reasonKey)}
                                className={`ml-4 flex w-[calc(100%-1rem)] items-center justify-between rounded-lg px-3 py-1.5 text-left text-sm transition ${selectionClass(detailSelected)}`}
                              >
                                <span className="truncate">{detail.detailLabel}</span>
                                <span className="ml-3 shrink-0 font-mono text-xs">{detail.count}</span>
                              </button>
                            );
                          })
                        : null}
                    </div>
                  );
                })}
              </div>
            </section>
          ) : null}

          <div
            className="mb-4 grid gap-2 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800 md:grid-cols-6"
            data-testid="roster-promotion-filters"
          >
            <select
              className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={filters.outcome}
              onChange={(e) => updateFilter("outcome", e.target.value as RosterPromotionOutcome | "")}
            >
              <option value="">Все статусы</option>
              {FILTER_OUTCOMES.map((outcome) => (
                <option key={outcome} value={outcome}>
                  {ROSTER_PROMOTION_OUTCOME_LABELS[outcome]}
                </option>
              ))}
            </select>
            <select
              className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={filters.reasonKey}
              onChange={(e) =>
                setFilters((prev) => ({
                  ...prev,
                  reasonTypeKey: "",
                  reasonKey: e.target.value,
                }))
              }
            >
              <option value="">Все причины</option>
              {reasonSummary.map((row) => (
                <option key={row.reasonKey} value={row.reasonKey}>
                  {row.label} ({row.count})
                </option>
              ))}
            </select>
            <select
              className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              value={filters.department}
              onChange={(e) => updateFilter("department", e.target.value)}
            >
              <option value="">Все подразделения</option>
              {departmentOptions.map((department) => (
                <option key={department} value={department}>
                  {department}
                </option>
              ))}
            </select>
            <input
              type="search"
              placeholder="Поиск по ФИО"
              value={filters.qName}
              onChange={(e) => updateFilter("qName", e.target.value)}
              className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            />
            <input
              type="search"
              inputMode="numeric"
              placeholder="Поиск по ИИН"
              value={filters.qIin}
              onChange={(e) => updateFilter("qIin", e.target.value)}
              className="rounded border border-zinc-300 px-3 py-2 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-950"
            />
            <button
              type="button"
              disabled={!filtersActive}
              onClick={resetFilters}
              className="rounded border border-zinc-300 px-3 py-2 text-sm disabled:opacity-50 dark:border-zinc-700"
            >
              Сбросить
            </button>
          </div>

          <div className="mb-2 text-xs text-zinc-500" data-testid="roster-promotion-filter-count">
            Показано {filteredItems.length} из {preview.length}
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-zinc-50 text-left text-[11px] uppercase text-zinc-500 dark:bg-zinc-900">
                <tr>
                  <th className="px-2 py-2">Статус</th>
                  <th className="px-2 py-2">ФИО</th>
                  <th className="px-2 py-2">ИИН</th>
                  <th className="px-2 py-2">Отделение</th>
                  <th className="px-2 py-2">Должность</th>
                  <th className="px-2 py-2">Причина</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-2 py-6 text-center text-zinc-500">
                      Нет записей по выбранным фильтрам
                    </td>
                  </tr>
                ) : (
                  filteredItems.map((item) => (
                    <tr key={item.row_id} className="border-t border-zinc-100 dark:border-zinc-800">
                      <td className="px-2 py-2">
                        <span
                          className={`inline-flex rounded-full border px-2 py-0.5 text-xs ${outcomeBadgeClass(item.outcome)}`}
                        >
                          {ROSTER_PROMOTION_OUTCOME_LABELS[item.outcome]}
                        </span>
                      </td>
                      <td className="px-2 py-2">{item.full_name || "—"}</td>
                      <td className="px-2 py-2 font-mono text-xs">{item.iin || "—"}</td>
                      <td className="px-2 py-2">{item.org_unit_name || "—"}</td>
                      <td className="px-2 py-2">{item.position_name || "—"}</td>
                      <td className="px-2 py-2 text-xs text-zinc-500">
                        {normalizeReasonLabel(item.reason) || item.reason || "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
