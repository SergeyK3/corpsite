"use client";

import * as React from "react";
import Link from "next/link";

import { apiAuthMe } from "@/lib/api";
import { isPrivilegedOperator } from "@/lib/adminNav";
import { canSeeHrProcessesNav } from "@/lib/personnelNav";
import type { MeInfo } from "@/lib/types";

import {
  formatBaselineImportLabel,
  formatBaselineProvenance,
  formatBaselineReportPeriod,
  formatBaselineStatus,
  groupBaselinesByPeriod,
  isBaselineSoftDeleted,
  resolveEffectiveBaselineIdByPeriod,
} from "../_lib/baselineDisplay";
import {
  hardDeleteControlListBaseline,
  listControlListBaselines,
  listInitialBaselineSourceSelections,
  mapImportApiError,
  restoreControlListBaseline,
  softDeleteControlListBaseline,
  type ControlListBaselineRow,
} from "../_lib/importApi.client";
import { buildInitialBaselineSourceByPeriod, resolveSelectedBatchIdForPeriod } from "../_lib/initialBaselineSource";
import {
  listMonthlyReferenceForkSources,
  type MonthlyReferenceSummary,
} from "../_lib/mrdApi.client";
import {
  formatMrdJournalMissingStatusLabel,
  formatMrdJournalStatusLabel,
  formatMrdReportPeriod,
  mrdJournalMissingStatusClassName,
  mrdJournalStatusClassName,
} from "../_lib/mrdDisplay";
import { buildMrdCreateWizardHref } from "../_lib/mrdForkNavigation";
import { resolveJournalPeriodAction } from "../_lib/importInitialBaselineNavigation";
import { buildMrdWorkspaceHref } from "../_lib/mrdWorkspaceNavigation";
import {
  buildWorkingJournalRows,
  collectExistingReportPeriods,
  evaluateCreateBaselineOffer,
} from "../_lib/mrdPeriodWindow";
import { MRD_UI } from "../_lib/mrdUiLabels";

function actionButtonClassName(variant: "default" | "danger" | "muted" = "default"): string {
  const base =
    "rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50";
  if (variant === "danger") {
    return `${base} border border-red-200 text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-300 dark:hover:bg-red-950`;
  }
  if (variant === "muted") {
    return `${base} border border-zinc-200 text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900`;
  }
  return `${base} border border-blue-200 text-blue-700 hover:bg-blue-50 dark:border-blue-900 dark:text-blue-300 dark:hover:bg-blue-950`;
}

type Props = {
  anchorId?: string;
  embedded?: boolean;
  initialBaselineSourceByPeriod?: Map<string, number>;
};

export default function PersonnelBaselinesJournalSection({
  anchorId = "baselines",
  embedded = false,
  initialBaselineSourceByPeriod,
}: Props) {
  const [me, setMe] = React.useState<MeInfo | null>(null);
  const [mrdItems, setMrdItems] = React.useState<MonthlyReferenceSummary[]>([]);
  const [activeByPeriod, setActiveByPeriod] = React.useState<Record<string, number>>({});
  const [legacyItems, setLegacyItems] = React.useState<ControlListBaselineRow[]>([]);
  const [loadedSourceByPeriod, setLoadedSourceByPeriod] = React.useState<Map<string, number>>(new Map());
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [actingBaselineId, setActingBaselineId] = React.useState<number | null>(null);

  const sourceByPeriod = initialBaselineSourceByPeriod ?? loadedSourceByPeriod;

  const canHardDelete = isPrivilegedOperator(me);

  const loadData = React.useCallback(async () => {
    setLoading(true);
    try {
      const requests: [
        ReturnType<typeof listMonthlyReferenceForkSources>,
        ReturnType<typeof listControlListBaselines>,
        ReturnType<typeof listInitialBaselineSourceSelections> | Promise<{ items: [] }>,
      ] = [
        listMonthlyReferenceForkSources(),
        listControlListBaselines({ include_deleted: false }),
        initialBaselineSourceByPeriod
          ? Promise.resolve({ items: [] })
          : listInitialBaselineSourceSelections(),
      ];
      const [mrdData, baselineData, selectionData] = await Promise.all(requests);
      setMrdItems(mrdData.items);
      setActiveByPeriod(mrdData.active_by_period);
      setLegacyItems(baselineData.items);
      if (!initialBaselineSourceByPeriod) {
        setLoadedSourceByPeriod(buildInitialBaselineSourceByPeriod(selectionData.items));
      }
      setError(null);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setLoading(false);
    }
  }, [initialBaselineSourceByPeriod]);

  React.useEffect(() => {
    void apiAuthMe()
      .then((data) => setMe(data))
      .catch(() => setMe(null));
  }, []);

  React.useEffect(() => {
    if (!canSeeHrProcessesNav(me)) return;
    void loadData();
  }, [loadData, me]);

  const workingJournalRows = React.useMemo(
    () => buildWorkingJournalRows(mrdItems, activeByPeriod),
    [activeByPeriod, mrdItems],
  );

  const existingPeriods = React.useMemo(
    () => collectExistingReportPeriods(mrdItems),
    [mrdItems],
  );

  const baselineByPeriod = React.useMemo(() => {
    const map = new Map<string, MonthlyReferenceSummary>();
    for (const row of workingJournalRows) {
      if (row.baseline) map.set(row.reportPeriod, row.baseline);
    }
    return map;
  }, [workingJournalRows]);

  const legacyGrouped = React.useMemo(() => groupBaselinesByPeriod(legacyItems), [legacyItems]);

  const effectiveByPeriod = React.useMemo(
    () => resolveEffectiveBaselineIdByPeriod(legacyItems),
    [legacyItems],
  );

  async function runAction(baselineId: number, action: () => Promise<unknown>) {
    setActingBaselineId(baselineId);
    try {
      await action();
      await loadData();
      setError(null);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setActingBaselineId(null);
    }
  }

  async function handleSoftDelete(row: ControlListBaselineRow) {
    const reason = window.prompt("Причина удаления (необязательно):", "") ?? "";
    const ok = window.confirm(
      `Пометить публикацию #${row.baseline_id} (${formatBaselineReportPeriod(row.report_period)}) как удалённую?`,
    );
    if (!ok) return;
    await runAction(row.baseline_id, () =>
      softDeleteControlListBaseline(row.baseline_id, {
        deletion_reason: reason.trim() || null,
      }),
    );
  }

  async function handleRestore(row: ControlListBaselineRow) {
    const ok = window.confirm(`Восстановить публикацию #${row.baseline_id}?`);
    if (!ok) return;
    await runAction(row.baseline_id, () => restoreControlListBaseline(row.baseline_id));
  }

  async function handleHardDelete(row: ControlListBaselineRow) {
    const reason = window.prompt("Причина безвозвратного удаления (необязательно):", "") ?? "";
    const ok = window.confirm(
      `Безвозвратно удалить публикацию #${row.baseline_id}? Сведения о происхождении будут сохранены.`,
    );
    if (!ok) return;
    await runAction(row.baseline_id, () =>
      hardDeleteControlListBaseline(row.baseline_id, {
        deletion_reason: reason.trim() || null,
      }),
    );
  }

  if (me && !canSeeHrProcessesNav(me)) {
    return (
      <section
        id={anchorId}
        className={embedded ? "mt-8 border-t border-zinc-200 pt-8 dark:border-zinc-800" : "px-4 py-3"}
      >
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100">
          {MRD_UI.journalInsufficientPermissions}
        </div>
      </section>
    );
  }

  const sectionClassName = embedded
    ? "mt-8 border-t border-zinc-200 pt-8 dark:border-zinc-800"
    : "px-4 py-3";

  return (
    <section id={anchorId} className={sectionClassName} data-testid="personnel-baselines-journal">
      <div className="mb-4">
        {embedded ? (
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">{MRD_UI.productTitle}</h2>
        ) : (
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">{MRD_UI.productTitle}</h1>
        )}
        <p className="mt-1 max-w-3xl text-sm text-zinc-600 dark:text-zinc-400">{MRD_UI.journalLead}</p>
      </div>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-xl border border-zinc-200 px-4 py-8 text-center text-sm text-zinc-500 dark:border-zinc-800">
          Загрузка…
        </div>
      ) : (
        <div className="mb-8 overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800" data-testid="mrd-journal-table">
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-white text-left text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-500 dark:bg-zinc-950">
                <tr>
                  <th className="px-4 py-3">{MRD_UI.journalPeriodColumn}</th>
                  <th className="px-4 py-3">{MRD_UI.journalStatusColumn}</th>
                  <th className="px-4 py-3">{MRD_UI.journalEntriesColumn}</th>
                  <th className="px-4 py-3">{MRD_UI.journalActionColumn}</th>
                </tr>
              </thead>
              <tbody>
                {workingJournalRows.map((row) => {
                  const baseline = row.baseline;
                  const createOffer = evaluateCreateBaselineOffer(
                    row.reportPeriod,
                    existingPeriods,
                    baselineByPeriod,
                  );
                  const periodAction = resolveJournalPeriodAction(
                    row.reportPeriod,
                    baseline,
                    baselineByPeriod,
                    {
                      selectedSourceBatchId: resolveSelectedBatchIdForPeriod(
                        row.reportPeriod,
                        sourceByPeriod,
                      ),
                    },
                  );
                  return (
                    <tr key={row.reportPeriod} className="border-t border-zinc-100 dark:border-zinc-800">
                      <td className="px-4 py-3 font-medium">{formatMrdReportPeriod(row.reportPeriod)}</td>
                      <td className="px-4 py-3">
                        {baseline ? (
                          <span className={mrdJournalStatusClassName(baseline)}>
                            {formatMrdJournalStatusLabel(baseline)}
                          </span>
                        ) : (
                          <span className={mrdJournalMissingStatusClassName()}>
                            {formatMrdJournalMissingStatusLabel()}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">{baseline ? baseline.entry_count : "—"}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap justify-end gap-2">
                          {periodAction ? (
                            <Link
                              href={periodAction.href}
                              className={actionButtonClassName()}
                              data-testid={periodAction.testId}
                            >
                              {periodAction.label}
                            </Link>
                          ) : baseline ? (
                            <Link
                              href={buildMrdWorkspaceHref(baseline.mrd_id)}
                              className={actionButtonClassName()}
                              data-testid={`mrd-workspace-link-${baseline.mrd_id}`}
                            >
                              {MRD_UI.workWithBaselineAction}
                            </Link>
                          ) : createOffer.allowed && createOffer.sourceMrdId ? (
                            <Link
                              href={buildMrdCreateWizardHref({
                                sourceMrdId: createOffer.sourceMrdId,
                                targetPeriod: createOffer.targetPeriod,
                              })}
                              className={actionButtonClassName()}
                            >
                              {MRD_UI.createBaselineAction}
                            </Link>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="border-t border-zinc-200 pt-8 dark:border-zinc-800">
        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{MRD_UI.legacyArchiveTitle}</h3>
        <p className="mt-1 max-w-3xl text-sm text-zinc-600 dark:text-zinc-400">{MRD_UI.legacyArchiveLead}</p>

        {legacyGrouped.length === 0 ? (
          <div className="mt-4 rounded-xl border border-zinc-200 px-4 py-8 text-center text-sm text-zinc-500 dark:border-zinc-800">
            {MRD_UI.legacyArchiveEmpty}
          </div>
        ) : (
          <div className="mt-4 space-y-6">
            {legacyGrouped.map((group) => (
              <section
                key={group.reportPeriod}
                className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800"
              >
                <div className="border-b border-zinc-100 bg-zinc-50 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900">
                  <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    Период {formatBaselineReportPeriod(group.reportPeriod)}
                  </h4>
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead className="bg-white text-left text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-500 dark:bg-zinc-950">
                      <tr>
                        <th className="px-4 py-3">{MRD_UI.archiveTableId}</th>
                        <th className="px-4 py-3">Импорт</th>
                        <th className="px-4 py-3">Происхождение</th>
                        <th className="px-4 py-3">Записей</th>
                        <th className="px-4 py-3">Статус</th>
                        <th className="px-4 py-3" />
                      </tr>
                    </thead>
                    <tbody>
                      {group.items.map((row) => {
                        const effectiveId = effectiveByPeriod.get(row.report_period) ?? null;
                        const acting = actingBaselineId === row.baseline_id;
                        const softDeleted = isBaselineSoftDeleted(row);
                        const batchId = row.linked_batch_id ?? row.source_batch_id ?? row.origin_batch_id;
                        return (
                          <tr key={row.baseline_id} className="border-t border-zinc-100 dark:border-zinc-800">
                            <td className="px-4 py-3 font-medium">#{row.baseline_id}</td>
                            <td className="px-4 py-3">
                              {batchId ? (
                                <Link
                                  href={`/directory/personnel/import/${batchId}`}
                                  className="text-blue-700 hover:underline dark:text-blue-300"
                                >
                                  {formatBaselineImportLabel(row)}
                                </Link>
                              ) : (
                                formatBaselineImportLabel(row)
                              )}
                            </td>
                            <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400">
                              {formatBaselineProvenance(row)}
                            </td>
                            <td className="px-4 py-3">{row.entry_count}</td>
                            <td className="px-4 py-3">{formatBaselineStatus(row, effectiveId)}</td>
                            <td className="px-4 py-3">
                              <div className="flex flex-wrap justify-end gap-2">
                                {!softDeleted ? (
                                  <button
                                    type="button"
                                    className={actionButtonClassName("danger")}
                                    disabled={acting}
                                    onClick={() => void handleSoftDelete(row)}
                                  >
                                    Пометить удалённым
                                  </button>
                                ) : (
                                  <button
                                    type="button"
                                    className={actionButtonClassName()}
                                    disabled={acting}
                                    onClick={() => void handleRestore(row)}
                                  >
                                    Восстановить
                                  </button>
                                )}
                                {canHardDelete ? (
                                  <button
                                    type="button"
                                    className={actionButtonClassName("muted")}
                                    disabled={acting}
                                    onClick={() => void handleHardDelete(row)}
                                  >
                                    Удалить безвозвратно
                                  </button>
                                ) : null}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
