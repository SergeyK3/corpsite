"use client";

import * as React from "react";

import ImportDiffStatusBadge from "./ImportDiffStatusBadge";
import {
  acceptImportReviewException,
  correctImportReviewException,
  getImportReviewExceptionDetail,
  isReviewExceptionAlreadyResolvedError,
  keepBaselineImportReviewException,
  mapImportApiError,
  postImportReviewRemovalExceptionDecision,
  type ReviewExceptionDetail,
  type ReviewExceptionFieldRow,
} from "../_lib/importApi.client";
import {
  formatReviewExceptionDiffValue,
  formatReviewExceptionFieldValue,
} from "../_lib/monthlyDiffLabels";
import { getNormalizedRecordKindLabel } from "../_lib/normalizedRecordLabels";

type Props = {
  batchId: number;
  exceptionKey: string | null;
  open: boolean;
  onClose: () => void;
  onResolved: () => void;
  onCorrected?: () => void;
};

function draftFromImportFields(
  fields: ReviewExceptionFieldRow[],
  editableKeys: string[],
): Record<string, string> {
  const draft: Record<string, string> = {};
  for (const key of editableKeys) {
    const field = fields.find((item) => item.key === key);
    draft[key] = field?.value ?? "";
  }
  return draft;
}

function BaselineImportBlock({
  title,
  sourceLabel,
  fields,
  variant,
  editing,
  editableKeys,
  draft,
  onDraftChange,
}: {
  title: string;
  sourceLabel: string;
  fields: ReviewExceptionDetail["baseline"]["fields"];
  variant: "baseline" | "import";
  editing?: boolean;
  editableKeys?: string[];
  draft?: Record<string, string>;
  onDraftChange?: (key: string, value: string) => void;
}) {
  const isEditableImport = variant === "import" && editing;

  return (
    <section
      className={`rounded-xl border p-4 ${
        variant === "baseline"
          ? "border-zinc-200 bg-zinc-50/70 dark:border-zinc-700 dark:bg-zinc-900/40"
          : "border-blue-200 bg-blue-50/50 dark:border-blue-900 dark:bg-blue-950/20"
      }`}
      data-testid={`review-exception-${variant}-block`}
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-800 dark:text-zinc-100">
          {title}
        </h3>
        <span className="text-xs text-zinc-500">{sourceLabel}</span>
      </div>
      <dl className="space-y-2">
        {fields.map((field) => {
          const canEdit = isEditableImport && editableKeys?.includes(field.key);
          return (
            <div
              key={field.key}
              className="grid gap-1 border-t border-zinc-100 pt-2 first:border-t-0 first:pt-0 dark:border-zinc-800"
            >
              <dt className="text-xs uppercase tracking-wide text-zinc-500">{field.label}</dt>
              <dd className="text-sm text-zinc-900 dark:text-zinc-100">
                {canEdit ? (
                  field.key.includes("_raw") || field.key === "note_raw" ? (
                    <textarea
                      value={draft?.[field.key] ?? ""}
                      onChange={(e) => onDraftChange?.(field.key, e.target.value)}
                      rows={3}
                      className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                    />
                  ) : (
                    <input
                      type="text"
                      value={draft?.[field.key] ?? ""}
                      onChange={(e) => onDraftChange?.(field.key, e.target.value)}
                      className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                    />
                  )
                ) : (
                  formatReviewExceptionFieldValue(field)
                )}
              </dd>
            </div>
          );
        })}
      </dl>
    </section>
  );
}

function DiffBlock({
  fields,
}: {
  fields: ReviewExceptionDetail["diff"]["fields"];
}) {
  return (
    <section
      className="rounded-xl border border-amber-200 bg-amber-50/40 p-4 dark:border-amber-900/50 dark:bg-amber-950/20"
      data-testid="review-exception-diff-block"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-800 dark:text-zinc-100">
          Diff
        </h3>
        <span className="text-xs text-zinc-500">Подсветка расхождений</span>
      </div>
      <div className="overflow-x-auto rounded-lg border border-amber-200/80 bg-white dark:border-amber-900/40 dark:bg-zinc-950">
        <table className="min-w-full text-sm">
          <thead className="bg-amber-100/60 text-left text-[11px] uppercase tracking-wide text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
            <tr>
              <th className="px-3 py-2">Поле</th>
              <th className="px-3 py-2">Эталон</th>
              <th className="px-3 py-2">Импорт</th>
            </tr>
          </thead>
          <tbody>
            {fields.map((row) => (
              <tr
                key={row.key}
                className={`border-t border-amber-100 dark:border-amber-900/30 ${
                  row.changed ? "bg-amber-50/80 dark:bg-amber-950/30" : ""
                }`}
                data-changed={row.changed ? "true" : "false"}
              >
                <td className="px-3 py-2 font-medium text-zinc-800 dark:text-zinc-200">{row.label}</td>
                <td
                  className={`px-3 py-2 ${
                    row.changed
                      ? "font-medium text-red-700 dark:text-red-300"
                      : "text-zinc-700 dark:text-zinc-300"
                  }`}
                >
                  {formatReviewExceptionDiffValue("baseline", row)}
                </td>
                <td
                  className={`px-3 py-2 ${
                    row.changed
                      ? "font-medium text-emerald-700 dark:text-emerald-300"
                      : "text-zinc-900 dark:text-zinc-100"
                  }`}
                >
                  {formatReviewExceptionDiffValue("import", row)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function ImportReviewExceptionDrawer({
  batchId,
  exceptionKey,
  open,
  onClose,
  onResolved,
  onCorrected,
}: Props) {
  const [detail, setDetail] = React.useState<ReviewExceptionDetail | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [acting, setActing] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState<Record<string, string>>({});

  const loadDetail = React.useCallback(async () => {
    if (!exceptionKey) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getImportReviewExceptionDetail(batchId, exceptionKey);
      setDetail(data);
      setEditing(false);
      setDraft(
        draftFromImportFields(data.import_data.fields, data.editable_import_fields ?? []),
      );
    } catch (e) {
      setDetail(null);
      if (isReviewExceptionAlreadyResolvedError(e)) {
        onResolved();
        onClose();
        return;
      }
      setError(mapImportApiError(e));
    } finally {
      setLoading(false);
    }
  }, [batchId, exceptionKey, onClose, onResolved]);

  React.useEffect(() => {
    if (!open || !exceptionKey) {
      setDetail(null);
      setError(null);
      setEditing(false);
      return;
    }
    void loadDetail();
  }, [open, exceptionKey, loadDetail]);

  async function runAction(action: string, fn: () => Promise<unknown>) {
    setActing(action);
    setError(null);
    try {
      await fn();
      onResolved();
      onClose();
    } catch (e) {
      if (isReviewExceptionAlreadyResolvedError(e)) {
        onResolved();
        onClose();
        return;
      }
      setError(mapImportApiError(e));
    } finally {
      setActing(null);
    }
  }

  async function saveCorrections() {
    if (!detail || !exceptionKey) return;
    setActing("correct_import");
    setError(null);
    try {
      const editableKeys = detail.editable_import_fields ?? [];
      const corrections: Record<string, unknown> = {};
      for (const key of editableKeys) {
        if (!(key in draft)) continue;
        const raw = draft[key].trim();
        corrections[key] = raw || null;
      }
      const result = await correctImportReviewException(batchId, exceptionKey, corrections);
      setDetail(result.detail);
      setEditing(false);
      setDraft(
        draftFromImportFields(
          result.detail.import_data.fields,
          result.detail.editable_import_fields ?? [],
        ),
      );
      (onCorrected ?? onResolved)();
    } catch (e) {
      if (isReviewExceptionAlreadyResolvedError(e)) {
        onResolved();
        onClose();
        return;
      }
      setError(mapImportApiError(e));
    } finally {
      setActing(null);
    }
  }

  if (!open) return null;

  const editableKeys = detail?.editable_import_fields ?? [];
  const canCorrect = Boolean(detail?.correct_action_available && editableKeys.length > 0);
  const subtitle =
    detail?.record_kind && detail.record_kind !== "roster"
      ? getNormalizedRecordKindLabel(detail.record_kind, detail.subtitle ?? undefined)
      : detail?.subtitle;

  return (
    <div className="fixed inset-0 z-[70] flex justify-end" data-testid="import-review-exception-drawer">
      <button
        type="button"
        className="absolute inset-0 bg-black/40"
        aria-label="Закрыть"
        onClick={onClose}
      />
      <aside className="relative flex h-full w-full max-w-3xl flex-col bg-white shadow-xl dark:bg-zinc-950">
        <header className="flex items-start justify-between gap-3 border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
          <div>
            <p className="text-xs uppercase tracking-wide text-zinc-500">Разрешение конфликта Import Review</p>
            <h2 className="mt-1 text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              {detail?.title ?? "Загрузка…"}
            </h2>
            {detail ? (
              <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
                <ImportDiffStatusBadge status={detail.diff_status} />
                {subtitle ? <span>{subtitle}</span> : null}
                {detail.department ? <span>{detail.department}</span> : null}
              </div>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
          >
            Закрыть
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? (
            <div className="py-12 text-center text-sm text-zinc-500">Загрузка сравнения…</div>
          ) : error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
              {error}
            </div>
          ) : detail ? (
            <div className="space-y-4">
              {detail.resolved_by_correction ? (
                <div
                  className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100"
                  data-testid="review-exception-resolved-by-correction"
                >
                  Исключение снято, diff совпадает. Сохранённые корректировки в staging остаются до Apply.
                </div>
              ) : null}

              {detail.quality_remarks && detail.quality_remarks.length > 0 ? (
                <div
                  className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100"
                  data-testid="review-exception-quality-remarks"
                >
                  <p className="font-medium">Замечания по качеству данных</p>
                  <ul className="mt-1 list-disc pl-5">
                    {detail.quality_remarks.map((remark) => (
                      <li key={remark}>{remark}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {Object.keys(detail.import_review_override ?? {}).length > 0 && !editing ? (
                <div
                  className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-100"
                  data-testid="review-exception-import-override-banner"
                >
                  Применены ручные корректировки импортированных данных
                </div>
              ) : null}

              <BaselineImportBlock
                title="Канонический эталон"
                sourceLabel={detail.baseline.source_label}
                fields={detail.baseline.fields}
                variant="baseline"
              />
              <BaselineImportBlock
                title={editing ? "Редактируемые импортные данные" : "Импортируемые данные"}
                sourceLabel={detail.import_data.source_label}
                fields={detail.import_data.fields}
                variant="import"
                editing={editing}
                editableKeys={editableKeys}
                draft={draft}
                onDraftChange={(key, value) => setDraft((prev) => ({ ...prev, [key]: value }))}
              />
              {!editing ? <DiffBlock fields={detail.diff.fields} /> : null}
            </div>
          ) : null}
        </div>

        {detail && !loading ? (
          <footer className="border-t border-zinc-200 px-5 py-4 dark:border-zinc-800">
            {detail.removal_actions_available ? (
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={acting != null}
                  onClick={() =>
                    runAction("restore", () =>
                      postImportReviewRemovalExceptionDecision(batchId, detail.entity_id, {
                        decision: "restore",
                      }),
                    )
                  }
                  className="rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-900 hover:bg-emerald-100 disabled:opacity-60 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"
                  data-testid="review-exception-restore"
                >
                  {acting === "restore" ? "Сохранение…" : "Восстановить запись"}
                </button>
                <button
                  type="button"
                  disabled={acting != null}
                  onClick={() =>
                    runAction("confirm_removal", () =>
                      postImportReviewRemovalExceptionDecision(batchId, detail.entity_id, {
                        decision: "confirm_removal",
                      }),
                    )
                  }
                  className="rounded-lg border border-red-300 bg-red-50 px-4 py-2 text-sm font-medium text-red-900 hover:bg-red-100 disabled:opacity-60 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
                  data-testid="review-exception-confirm-removal"
                >
                  {acting === "confirm_removal" ? "Сохранение…" : "Подтвердить удаление"}
                </button>
              </div>
            ) : editing ? (
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={acting != null}
                  onClick={() => void saveCorrections()}
                  className="rounded-lg border border-blue-300 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-900 hover:bg-blue-100 disabled:opacity-60 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-200"
                  data-testid="review-exception-save-corrections"
                >
                  {acting === "correct_import" ? "Сохранение…" : "Сохранить"}
                </button>
                <button
                  type="button"
                  disabled={acting != null}
                  onClick={() => {
                    setEditing(false);
                    setDraft(draftFromImportFields(detail.import_data.fields, editableKeys));
                  }}
                  className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-50 disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                >
                  Отмена
                </button>
              </div>
            ) : detail.actions_available ? (
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={acting != null}
                  onClick={() =>
                    runAction("accept_import", () =>
                      acceptImportReviewException(batchId, detail.exception_key),
                    )
                  }
                  className="rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-900 hover:bg-emerald-100 disabled:opacity-60 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200"
                  data-testid="review-exception-accept-import"
                >
                  {acting === "accept_import" ? "Сохранение…" : "Принять импорт"}
                </button>
                {canCorrect ? (
                  <button
                    type="button"
                    disabled={acting != null}
                    onClick={() => setEditing(true)}
                    className="rounded-lg border border-blue-300 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-900 hover:bg-blue-100 disabled:opacity-60 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-200"
                    data-testid="review-exception-correct-import"
                  >
                    Исправить
                  </button>
                ) : null}
                <button
                  type="button"
                  disabled={acting != null}
                  onClick={() =>
                    runAction("keep_baseline", () =>
                      keepBaselineImportReviewException(batchId, detail.exception_key),
                    )
                  }
                  className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-50 disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:hover:bg-zinc-900"
                  data-testid="review-exception-keep-baseline"
                >
                  {acting === "keep_baseline" ? "Сохранение…" : "Оставить эталон"}
                </button>
              </div>
            ) : detail.resolved_by_correction ? (
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
              >
                Закрыть
              </button>
            ) : null}
          </footer>
        ) : null}
      </aside>
    </div>
  );
}
