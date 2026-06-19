"use client";

import * as React from "react";

import {
  getPromotionBlockerLabel,
  mapImportApiError,
  NORMALIZED_RECORD_KIND_LABELS,
  promoteNormalizedRecords,
  PROMOTION_BLOCKER_PANEL_GROUPS,
  PROMOTION_SKIP_REASON_LABELS,
  sumBlockersByCodes,
  type NormalizedRecordKind,
  type PromotionItemResult,
  type PromotionResponse,
} from "../_lib/importApi.client";
import {
  buildBlockerReasonLines,
  buildDryRunSummary,
  buildPromotionScopeLabel,
  resolvePromoteDisabledState,
} from "../_lib/normalizedRecordPromotionUx";

function ResultTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: string;
}) {
  return (
    <div className={`rounded-xl border px-3 py-2 ${tone ?? "border-zinc-200 dark:border-zinc-800"}`}>
      <div className="text-xs text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function PromotionItemsTable({ items }: { items: PromotionItemResult[] }) {
  const issueItems = items.filter((item) => item.outcome !== "promoted" && item.outcome !== "would_promote");
  if (!issueItems.length) {
    return (
      <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">
        Нет записей с блокерами или пропусками.
      </p>
    );
  }

  return (
    <div className="mt-3 overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400">
          <tr>
            <th className="px-3 py-2">ID</th>
            <th className="px-3 py-2">Тип</th>
            <th className="px-3 py-2">Сотрудник</th>
            <th className="px-3 py-2">Результат</th>
            <th className="px-3 py-2">Причина / блокеры</th>
          </tr>
        </thead>
        <tbody>
          {issueItems.map((item) => (
            <tr key={item.record_id} className="border-t border-zinc-200 dark:border-zinc-800">
              <td className="px-3 py-2 font-mono text-xs">{item.record_id}</td>
              <td className="px-3 py-2">
                {NORMALIZED_RECORD_KIND_LABELS[item.record_kind as NormalizedRecordKind] || item.record_kind}
              </td>
              <td className="px-3 py-2">{item.employee_id ?? "—"}</td>
              <td className="px-3 py-2">{item.outcome}</td>
              <td className="px-3 py-2">
                {item.reason ? (
                  <span>{PROMOTION_SKIP_REASON_LABELS[item.reason] ?? item.reason}</span>
                ) : null}
                {item.blockers?.length ? (
                  <ul className="mt-1 list-disc pl-4 text-xs text-red-700 dark:text-red-300">
                    {item.blockers.map((blocker) => (
                      <li key={`${item.record_id}-${blocker.code}`}>
                        {getPromotionBlockerLabel(blocker.code)}
                        {blocker.message ? `: ${blocker.message}` : ""}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BlockersPanel({ summary }: { summary: Record<string, number> }) {
  const groups = PROMOTION_BLOCKER_PANEL_GROUPS.map((group) => ({
    ...group,
    count: sumBlockersByCodes(summary, group.codes),
  }));
  const total = groups.reduce((acc, group) => acc + group.count, 0);

  if (total === 0) {
    return (
      <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">
        Блокеров не обнаружено.
      </p>
    );
  }

  return (
    <div className="mt-3 grid gap-2 sm:grid-cols-2">
      {groups.map((group) => (
        <div
          key={group.key}
          className={`rounded-lg border px-3 py-2 ${
            group.count > 0
              ? "border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30"
              : "border-zinc-200 dark:border-zinc-800"
          }`}
        >
          <div className="text-xs text-zinc-500 dark:text-zinc-400">{group.label}</div>
          <div className="text-lg font-semibold tabular-nums">{group.count}</div>
        </div>
      ))}
    </div>
  );
}

export type NormalizedRecordsPromotionPanelProps = {
  batchId: string;
  recordKind: string;
  tableUnavailable: boolean;
  approvedInBatch?: number;
  pendingInBatch?: number;
  normalizedInBatch?: number;
  promotionScope?: "batch" | "employee";
  employeeScopeLabel?: string | null;
  onCompleted: () => void;
  onToast: (message: string, kind?: "success" | "error") => void;
};

export default function NormalizedRecordsPromotionPanel({
  batchId,
  recordKind,
  tableUnavailable,
  approvedInBatch = 0,
  pendingInBatch = 0,
  normalizedInBatch,
  promotionScope = "batch",
  employeeScopeLabel = null,
  onCompleted,
  onToast,
}: NormalizedRecordsPromotionPanelProps) {
  const [dryRunning, setDryRunning] = React.useState(false);
  const [promoting, setPromoting] = React.useState(false);
  const [promotionError, setPromotionError] = React.useState<string | null>(null);
  const [promotionResult, setPromotionResult] = React.useState<PromotionResponse | null>(null);
  const [showItems, setShowItems] = React.useState(false);

  const batchSelected = Boolean(batchId);
  const canRun = batchSelected && !tableUnavailable && !dryRunning && !promoting;

  const recordKindLabel = recordKind
    ? (NORMALIZED_RECORD_KIND_LABELS[recordKind as NormalizedRecordKind] || recordKind)
    : null;

  const scopeLabel = buildPromotionScopeLabel({
    scope: promotionScope,
    batchId: batchSelected ? batchId : null,
    employeeLabel: employeeScopeLabel,
    recordKindLabel,
  });

  React.useEffect(() => {
    setPromotionResult(null);
    setPromotionError(null);
    setShowItems(false);
  }, [batchId, recordKind, promotionScope, employeeScopeLabel]);

  function buildRequest(dryRun: boolean) {
    return {
      batch_id: Number(batchId),
      filters: {
        review_status: "approved",
        ...(recordKind ? { record_kind: recordKind } : {}),
      },
      dry_run: dryRun,
    };
  }

  async function runDryRun() {
    if (!batchSelected) {
      setPromotionError("Выберите импорт (batch) для запуска promotion.");
      return;
    }
    setDryRunning(true);
    setPromotionError(null);
    try {
      const result = await promoteNormalizedRecords(buildRequest(true));
      setPromotionResult(result);
      setShowItems(false);
    } catch (e) {
      setPromotionError(mapImportApiError(e, "Не удалось выполнить dry-run."));
    } finally {
      setDryRunning(false);
    }
  }

  async function runPromote() {
    if (!batchSelected) {
      setPromotionError("Выберите импорт (batch) для запуска promotion.");
      return;
    }
    const preview = promotionResult?.dry_run ? promotionResult : null;
    const wouldPromote = preview?.would_promote ?? 0;
    const requested = preview?.requested ?? 0;

    if (
      !window.confirm(
        `Вы собираетесь записать утверждённые записи в кадровые карточки сотрудников.\n\n` +
          `Запрошено: ${requested}\n` +
          `Будет промотировано: ${wouldPromote > 0 ? wouldPromote : "неизвестно (dry-run не выполнялся)"}\n\n` +
          `Это действие необратимо. Записи получат статус «Промотировано».\n\n` +
          `Продолжить?`
      )
    ) {
      return;
    }

    setPromoting(true);
    setPromotionError(null);
    try {
      const result = await promoteNormalizedRecords(buildRequest(false));
      setPromotionResult(result);
      setShowItems(false);
      onCompleted();
      onToast(
        `Promotion завершён: ${result.promoted} записано, ${result.skipped} пропущено, ${result.failed} ошибок.`,
        result.failed > 0 ? "error" : "success"
      );
    } catch (e) {
      setPromotionError(mapImportApiError(e, "Не удалось выполнить promotion."));
    } finally {
      setPromoting(false);
    }
  }

  const promoteState = resolvePromoteDisabledState({
    batchSelected,
    tableUnavailable,
    dryRunning,
    promoting,
    promotionResult,
    approvedInBatch,
    normalizedInBatch,
  });

  const isDryRunResult = promotionResult?.dry_run === true;
  const dryRunSummary = isDryRunResult && promotionResult ? buildDryRunSummary(promotionResult) : null;
  const blockerReasonLines =
    isDryRunResult && promotionResult
      ? buildBlockerReasonLines(promotionResult.summary_by_blocker)
      : [];

  return (
    <section
      className="mb-4 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800"
      data-promotion-panel="normalized-records"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Promotion (ADR-039 Phase 3F)
          </h2>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Запись утверждённых нормализованных записей в кадровые карточки сотрудников.
            Сначала выполните dry-run, затем подтвердите реальный promote.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!canRun}
            onClick={runDryRun}
            className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-50 disabled:opacity-60 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            {dryRunning ? "Dry-run…" : "Dry Run"}
          </button>
          <button
            type="button"
            disabled={!promoteState.canPromote}
            onClick={runPromote}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
            aria-describedby={promoteState.message ? "promote-disabled-reason" : undefined}
          >
            {promoting ? "Promote…" : "Promote"}
          </button>
        </div>
      </div>

      <div
        className="mt-3 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-800 dark:bg-zinc-900/40"
        data-testid="promotion-scope-label"
      >
        <span className="font-medium text-zinc-700 dark:text-zinc-300">Promotion scope: </span>
        <span className="text-zinc-900 dark:text-zinc-100">{scopeLabel}</span>
      </div>

      {batchSelected && pendingInBatch > 0 ? (
        <p
          className="mt-2 text-sm text-zinc-600 dark:text-zinc-400"
          data-testid="promotion-pending-note"
        >
          Pending records: {pendingInBatch.toLocaleString("ru-RU")}. Они не участвуют в promotion и не
          блокируют его.
        </p>
      ) : null}

      {!promoteState.canPromote && promoteState.message ? (
        <p
          id="promote-disabled-reason"
          className="mt-2 text-sm text-amber-800 dark:text-amber-200"
          data-testid="promote-disabled-reason"
          data-reason-code={promoteState.reasonCode ?? undefined}
        >
          {promoteState.message}
        </p>
      ) : null}

      {!batchSelected ? (
        <p className="mt-3 text-sm text-amber-700 dark:text-amber-300">
          Выберите импорт в фильтре выше — promotion выполняется в рамках одного batch.
        </p>
      ) : null}
      {tableUnavailable ? (
        <p className="mt-3 text-sm text-amber-700 dark:text-amber-300">
          Таблица нормализованных записей недоступна — promotion отключён.
        </p>
      ) : null}
      {promotionError ? (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {promotionError}
        </div>
      ) : null}

      {dryRunSummary ? (
        <div
          className="mt-4 rounded-xl border border-sky-200 bg-sky-50 p-4 text-sm dark:border-sky-900 dark:bg-sky-950/40"
          data-testid="promotion-dry-run-summary"
        >
          <div className="font-medium">Dry-run выполнен (БД не изменена)</div>
          <div className="mt-3 grid gap-2 grid-cols-2 sm:grid-cols-3">
            <ResultTile label="Approved" value={dryRunSummary.approved} />
            <ResultTile label="Would promote" value={dryRunSummary.wouldPromote} />
            <ResultTile
              label="Blocked"
              value={dryRunSummary.blocked}
              tone="border-red-300 dark:border-red-800"
            />
          </div>
          {blockerReasonLines.length > 0 ? (
            <div className="mt-4">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Причины блокировки
              </h3>
              <ul className="mt-2 space-y-1 text-sm">
                {blockerReasonLines.map((line) => (
                  <li key={line.key}>
                    {line.label}: {line.count.toLocaleString("ru-RU")}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      {promotionResult && !isDryRunResult ? (
        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm dark:border-emerald-900 dark:bg-emerald-950/40">
          <div className="font-medium">Promotion выполнен — данные записаны в кадровые карточки</div>
          <div className="mt-3 grid gap-2 grid-cols-2 sm:grid-cols-4">
            <ResultTile label="Запрошено" value={promotionResult.requested} />
            <ResultTile label="Промотировано" value={promotionResult.promoted} />
            <ResultTile label="Пропущено" value={promotionResult.skipped} />
            <ResultTile
              label="Ошибок"
              value={promotionResult.failed}
              tone="border-red-300 dark:border-red-800"
            />
          </div>
          <div className="mt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Блокеры</h3>
            <BlockersPanel summary={promotionResult.summary_by_blocker} />
          </div>
          <button
            type="button"
            onClick={() => setShowItems((v) => !v)}
            className="mt-4 text-xs text-blue-700 underline dark:text-blue-300"
          >
            {showItems ? "Скрыть детали записей" : "Показать детали записей с проблемами"}
          </button>
          {showItems ? <PromotionItemsTable items={promotionResult.items} /> : null}
        </div>
      ) : null}

      {isDryRunResult && promotionResult ? (
        <>
          <div className="mt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Блокеры (детализация)
            </h3>
            <BlockersPanel summary={promotionResult.summary_by_blocker} />
          </div>
          <button
            type="button"
            onClick={() => setShowItems((v) => !v)}
            className="mt-4 text-xs text-blue-700 underline dark:text-blue-300"
          >
            {showItems ? "Скрыть детали записей" : "Показать детали записей с проблемами"}
          </button>
          {showItems ? <PromotionItemsTable items={promotionResult.items} /> : null}
        </>
      ) : null}
    </section>
  );
}
