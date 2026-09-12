"use client";

import * as React from "react";

import TrainingSummaryBlocks from "@/components/TrainingSummaryBlocks";
import { useCurrentUser } from "@/lib/currentUser";
import { trainingSummaryRecordFromPprRecord } from "@/lib/trainingSummary";
import type { PprTrainingRecordResponse } from "../_lib/pprQueryTypes";
import { formatPersonnelDate, formatPersonnelDateRange } from "@/lib/personnelDateFormat";
import {
  listTrainingReviewRecords,
  getTrainingSplitPreview,
  patchTrainingReviewRecord,
  splitTrainingReviewRecord,
  submitOwnTrainingReviewProposal,
  undoTrainingReviewSplit,
  type TrainingReviewHoursSummary,
  type TrainingReviewRecord,
  type TrainingSplitPreview,
} from "../_lib/importApi.client";

type Props = {
  active: PprTrainingRecordResponse[];
  superseded: PprTrainingRecordResponse[];
  voided: PprTrainingRecordResponse[];
  employeeId?: string | null;
};

function trainingTitleForDisplay(value: string | null): string {
  return String(value ?? "").replace(/^\s*\d+[.)]\s*/, "").trim() || "Обучение без наименования";
}

export function ImportedTrainingReviewBlock({ employeeId }: { employeeId?: string | null }) {
  const [records, setRecords] = React.useState<TrainingReviewRecord[]>([]);
  const [summary, setSummary] = React.useState<TrainingReviewHoursSummary | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [editingId, setEditingId] = React.useState<number | null>(null);
  const [editingMode, setEditingMode] = React.useState<"hr" | "proposal">("hr");
  const [draft, setDraft] = React.useState<Record<string, string>>({});
  const [savingId, setSavingId] = React.useState<number | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [splitRecord, setSplitRecord] = React.useState<TrainingReviewRecord | null>(null);
  const [splitPreview, setSplitPreview] = React.useState<TrainingSplitPreview | null>(null);
  const [splitBoundary, setSplitBoundary] = React.useState(0);
  const currentUser = useCurrentUser();
  const canManageReview = currentUser?.has_personnel_admin === true || currentUser?.is_privileged === true;
  const isOwnTraining = Number.isInteger(Number(employeeId))
    && Number(employeeId) > 0
    && currentUser?.employee_id === Number(employeeId);

  const replaceRecord = React.useCallback((updated: TrainingReviewRecord) => {
    setRecords((current) => current.map((record) => (
      record.normalized_record_id === updated.normalized_record_id ? updated : record
    )));
  }, []);

  React.useEffect(() => {
    const parsedEmployeeId = Number(employeeId);
    if (!Number.isInteger(parsedEmployeeId) || parsedEmployeeId <= 0) {
      setRecords([]);
      setSummary(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    void listTrainingReviewRecords(parsedEmployeeId)
      .then((response) => {
        if (!cancelled) {
          setRecords(response.items ?? []);
          setSummary(response.summary ?? null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setRecords([]);
          setSummary(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [employeeId]);

  if (!loading && records.length === 0) return null;

  const startEdit = (record: TrainingReviewRecord, mode: "hr" | "proposal" = "hr") => {
    setError(null);
    setEditingId(record.normalized_record_id);
    setEditingMode(mode);
    setDraft({
      title: record.title ?? "",
      provider: record.provider ?? "",
      hours: record.hours == null ? "" : String(record.hours),
      start_date: record.training_review.dates.start_date ?? "",
      end_date: record.training_review.dates.end_date ?? "",
    });
  };

  const changedDraftValues = (record: TrainingReviewRecord) => Object.fromEntries(
    [
      ["title", [draft.title, record.title ?? ""]],
      ["provider", [draft.provider, record.provider ?? ""]],
      ["hours", [draft.hours, record.hours == null ? "" : String(record.hours)]],
      ["start_date", [draft.start_date, record.training_review.dates.start_date ?? ""]],
      ["end_date", [draft.end_date, record.training_review.dates.end_date ?? ""]],
    ].flatMap(([field, values]) => {
      const [next, prior] = values as [string, string];
      if (next === prior) return [];
      return [[field, field === "hours" ? (next === "" ? null : Number(next)) : (next || null)]];
    }),
  );

  const perform = async (
    record: TrainingReviewRecord,
    action: "edit" | "approve" | "reject" | "restore" | "accept_proposal" | "reject_proposal",
  ) => {
    setSavingId(record.normalized_record_id);
    setError(null);
    try {
      const values = action === "edit" ? changedDraftValues(record) : undefined;
      const updated = await patchTrainingReviewRecord(record.normalized_record_id, {
        action,
        expected_version: record.training_review.version,
        values,
      });
      replaceRecord(updated);
      if (action === "edit" || action === "restore") setEditingId(null);
      const parsedEmployeeId = Number(employeeId);
      if (Number.isInteger(parsedEmployeeId) && parsedEmployeeId > 0) {
        const refreshed = await listTrainingReviewRecords(parsedEmployeeId);
        setRecords(refreshed.items ?? []);
        setSummary(refreshed.summary ?? null);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить изменение.");
    } finally {
      setSavingId(null);
    }
  };

  const submitProposal = async (record: TrainingReviewRecord) => {
    setSavingId(record.normalized_record_id);
    setError(null);
    try {
      const updated = await submitOwnTrainingReviewProposal(record.normalized_record_id, {
        expected_version: record.training_review.version,
        values: changedDraftValues(record),
      });
      replaceRecord(updated);
      setEditingId(null);
      const parsedEmployeeId = Number(employeeId);
      if (Number.isInteger(parsedEmployeeId) && parsedEmployeeId > 0) {
        const refreshed = await listTrainingReviewRecords(parsedEmployeeId);
        setRecords(refreshed.items ?? []);
        setSummary(refreshed.summary ?? null);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось отправить предложение.");
    } finally {
      setSavingId(null);
    }
  };

  const refreshTrainingReview = async () => {
    const id = Number(employeeId);
    if (!Number.isInteger(id) || id <= 0) return;
    const response = await listTrainingReviewRecords(id);
    setRecords(response.items ?? []); setSummary(response.summary ?? null);
  };

  const openSplit = async (record: TrainingReviewRecord) => {
    setSavingId(record.normalized_record_id); setError(null);
    try { const preview = await getTrainingSplitPreview(record.normalized_record_id); setSplitRecord(record); setSplitPreview(preview); setSplitBoundary(preview.suggested_boundary); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось предложить границу разделения."); }
    finally { setSavingId(null); }
  };

  const confirmSplit = async () => {
    if (!splitRecord || !splitPreview) return;
    setSavingId(splitRecord.normalized_record_id); setError(null);
    try {
      const left = splitPreview.source_text.slice(0, splitBoundary).replace(/^\s*\d+[.)]\s*/, "").trim();
      const right = splitPreview.source_text.slice(splitBoundary).replace(/^\s*\d+[.)]\s*/, "").trim();
      await splitTrainingReviewRecord(splitRecord.normalized_record_id, { expected_version: splitRecord.training_review.version, boundary: splitBoundary, children: [{ title: left }, { title: right }] });
      setSplitRecord(null); setSplitPreview(null); await refreshTrainingReview();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось разделить запись."); }
    finally { setSavingId(null); }
  };

  const undoSplit = async (record: TrainingReviewRecord) => {
    const split = record.training_review.split;
    if (!split?.parent_record_id || !split.parent_version) return;
    setSavingId(record.normalized_record_id); setError(null);
    try { await undoTrainingReviewSplit(split.parent_record_id, split.parent_version); await refreshTrainingReview(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Не удалось отменить разделение."); }
    finally { setSavingId(null); }
  };

  const statusLabel = (status: TrainingReviewRecord["training_review"]["status"]) => ({
    REQUIRES_REVIEW: "Требуется проверка",
    CHECKED: "Проверено",
    REJECTED: "Отклонено",
    EMPLOYEE_PROPOSED: "Предложено сотрудником",
  }[status]);

  const qualityLabel = (quality: "EXACT" | "CALCULATED" | "UNKNOWN") => ({
    EXACT: "Точная",
    CALCULATED: "Расчётная",
    UNKNOWN: "—",
  }[quality]);

  const formatReviewMoment = (value: string | null) => value
    ? new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "short" }).format(new Date(value))
    : "";

  return (
    <section
      className="space-y-3 rounded-lg border border-amber-300 bg-amber-50/60 p-3 dark:border-amber-900 dark:bg-amber-950/20"
      aria-label="Из контрольного списка — требуется проверка"
      data-testid="control-list-training-review"
    >
      <div>
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
          Из контрольного списка — требуется проверка
        </h3>
        <p className="mt-1 text-xs text-zinc-700 dark:text-zinc-300">
          Эти сведения импортированы в staging и ещё не являются записями карточки сотрудника.
        </p>
      </div>
      {loading ? <p className="text-sm text-zinc-600 dark:text-zinc-400">Загрузка импортированных записей…</p> : null}
      {summary ? (
        <div className="grid gap-1 rounded-md bg-white/70 p-2 text-xs text-zinc-800 dark:bg-zinc-950/50 dark:text-zinc-200 sm:grid-cols-2">
          <p>Подтверждено за последние 5 лет: <strong>{summary.confirmed_hours_last_5y} часов</strong></p>
          <p>Предварительно с учётом непроверенных записей: <strong>{summary.preliminary_hours_last_5y} часов</strong></p>
          <p>Норматив: <strong>{summary.required_hours} часа</strong></p>
          {summary.confirmed_hours_last_5y < summary.required_hours ? (
            <p>Не хватает подтверждённых часов: <strong>{summary.hours_missing}</strong></p>
          ) : summary.norm_valid_through ? (
            <p>Норматив {summary.required_hours} часа сохраняется до: <strong>{formatPersonnelDate(summary.norm_valid_through)}</strong></p>
          ) : null}
          {summary.nearest_exclusion_date ? (
            <p className="sm:col-span-2">Ближайшее исключение часов: {formatPersonnelDate(summary.nearest_exclusion_date)}; останется {summary.hours_after_nearest_exclusion} часов.</p>
          ) : null}
          <p className="sm:col-span-2 text-zinc-500 dark:text-zinc-400">Расчёт на {formatPersonnelDate(summary.as_of)} ({summary.timezone}).</p>
        </div>
      ) : null}
      {error ? <p role="alert" className="text-sm text-red-700 dark:text-red-300">{error}</p> : null}
      {!loading && records.length > 0 ? (
        <div className="overflow-x-auto rounded-xl border border-amber-200 bg-white dark:border-amber-900 dark:bg-zinc-950">
          <table
            className="min-w-full divide-y divide-zinc-200 dark:divide-zinc-800"
            data-testid="control-list-training-review-table"
          >
            <thead className="bg-amber-100/70 dark:bg-amber-950/40">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-300">
                  Название курса
                </th>
                <th className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-300">
                  Дата начала
                </th>
                <th className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-300">
                  Дата окончания
                </th>
                <th className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-300">
                  Количество часов
                </th>
                <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-300">
                  Организация
                </th>
                <th className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-300">
                  Качество даты
                </th>
                <th className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-300">
                  Статус
                </th>
                <th className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-600 dark:text-zinc-300">
                  Действия
                </th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <React.Fragment key={record.normalized_record_id}>
                  <tr
                    className="border-t border-zinc-100 align-top dark:border-zinc-800"
                    data-testid={`control-list-training-review-row-${record.normalized_record_id}`}
                  >
                    <td className="px-3 py-2 text-sm font-medium text-zinc-900 dark:text-zinc-50">
                      {trainingTitleForDisplay(record.title)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-sm">
                      {formatPersonnelDate(record.training_review.dates.start_date, { precision: "day" })}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-sm">
                      {formatPersonnelDate(record.training_review.dates.end_date, { precision: "day" })}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-sm">{record.hours ?? "—"}</td>
                    <td className="px-3 py-2 text-sm">{record.provider || "—"}</td>
                    <td className="whitespace-nowrap px-3 py-2 text-sm">
                      {qualityLabel(record.training_review.dates.end_date_quality)}
                    </td>
                    <td className="px-3 py-2 text-sm text-amber-900 dark:text-amber-200">
                      <div>{statusLabel(record.training_review.status)}</div>
                      {record.training_review.status === "CHECKED" && record.training_review.reviewer ? (
                        <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
                          Проверено: {record.training_review.reviewer.full_name} ({record.training_review.reviewer.login})<br />
                          {formatReviewMoment(record.training_review.reviewed_at)}
                        </div>
                      ) : null}
                    </td>
                    <td className="px-3 py-2 text-sm">
                      <div className="flex flex-wrap gap-1.5">
                        {canManageReview ? <>
                          <button type="button" className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700" onClick={() => startEdit(record)} disabled={savingId === record.normalized_record_id}>Редактировать</button>
                          <button type="button" className="rounded border border-emerald-600 px-2 py-1 text-xs text-emerald-800 dark:text-emerald-200" onClick={() => void perform(record, "approve")} disabled={savingId === record.normalized_record_id}>Проверить и подтвердить</button>
                          <button type="button" className="rounded border border-red-500 px-2 py-1 text-xs text-red-700 dark:text-red-300" onClick={() => void perform(record, "reject")} disabled={savingId === record.normalized_record_id}>Отклонить</button>
                          <button type="button" className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700" onClick={() => void openSplit(record)} disabled={savingId === record.normalized_record_id}>Разделить</button>
                          {record.training_review.split?.parent_record_id ? <button type="button" className="rounded border border-zinc-300 px-2 py-1 text-xs dark:border-zinc-700" onClick={() => void undoSplit(record)} disabled={savingId === record.normalized_record_id}>Отменить разделение</button> : null}
                        </> : null}
                        {isOwnTraining ? <button type="button" className="rounded border border-blue-600 px-2 py-1 text-xs text-blue-800 dark:text-blue-200" onClick={() => startEdit(record, "proposal")} disabled={savingId === record.normalized_record_id}>Предложить исправление</button> : null}
                      </div>
                    </td>
                  </tr>
                  {splitRecord?.normalized_record_id === record.normalized_record_id && splitPreview ? (
                    <tr className="border-t border-zinc-100 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/30"><td colSpan={8} className="px-3 py-3">
                      <p className="font-medium">Разделение записи</p>
                      <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">Подтвердите предложенную границу или укажите позицию вручную.</p>
                      <input aria-label="Позиция границы разделения" type="number" min={1} max={Math.max(1, splitPreview.source_text.length - 1)} value={splitBoundary} onChange={(event) => setSplitBoundary(Number(event.target.value))} className="mt-2 rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700" />
                      <div className="mt-2 grid gap-2 sm:grid-cols-2"><div className="rounded border p-2 text-sm">{trainingTitleForDisplay(splitPreview.source_text.slice(0, splitBoundary))}</div><div className="rounded border p-2 text-sm">{trainingTitleForDisplay(splitPreview.source_text.slice(splitBoundary))}</div></div>
                      <div className="mt-3 flex gap-2"><button type="button" className="rounded bg-blue-700 px-3 py-1.5 text-sm text-white" onClick={() => void confirmSplit()} disabled={savingId === record.normalized_record_id}>Создать две записи</button><button type="button" className="rounded border border-zinc-300 px-3 py-1.5 text-sm" onClick={() => { setSplitRecord(null); setSplitPreview(null); }}>Отмена</button></div>
                    </td></tr>
                  ) : null}
                  {editingId === record.normalized_record_id ? (
                    <tr className="border-t border-zinc-100 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/30">
                      <td className="px-3 py-3" colSpan={8}>
                        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
                          {[
                            ["Название курса", "title", "text"],
                            ["Организация", "provider", "text"],
                            ["Дата начала", "start_date", "date"],
                            ["Дата окончания", "end_date", "date"],
                            ["Количество часов", "hours", "number"],
                          ].map(([label, field, type]) => (
                            <label key={field} className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                              {label}
                              <input type={type} value={draft[field] ?? ""} onChange={(event) => setDraft((current) => ({ ...current, [field]: event.target.value }))} className="mt-1 block w-full rounded border border-zinc-300 bg-white px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-950" />
                            </label>
                          ))}
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <button type="button" className="rounded bg-blue-700 px-3 py-1.5 text-sm font-medium text-white" onClick={() => editingMode === "proposal" ? void submitProposal(record) : void perform(record, "edit")} disabled={savingId === record.normalized_record_id}>{editingMode === "proposal" ? "Отправить предложение" : "Сохранить изменения"}</button>
                          <button type="button" className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700" onClick={() => setEditingId(null)}>Отмена</button>
                          {editingMode === "hr" ? <button type="button" className="rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700" onClick={() => void perform(record, "restore")} disabled={savingId === record.normalized_record_id}>Вернуть импортированные значения</button> : null}
                        </div>
                      </td>
                    </tr>
                  ) : null}
                  {record.training_review.proposal?.status === "PENDING" ? (
                    <tr className="border-t border-zinc-100 bg-amber-100/40 dark:border-zinc-800 dark:bg-amber-950/20">
                      <td className="px-3 py-3 text-xs text-zinc-700 dark:text-zinc-300" colSpan={8}>
                        <p className="font-medium">Предложение сотрудника: сравните текущие и предложенные значения перед решением.</p>
                        <dl className="mt-2 grid gap-x-4 gap-y-1 sm:grid-cols-2">
                          {[
                            ["Название", record.title, record.training_review.proposal.values.title],
                            ["Организация", record.provider, record.training_review.proposal.values.provider],
                            ["Дата начала", record.training_review.dates.start_date, record.training_review.proposal.values.start_date],
                            ["Дата окончания", record.training_review.dates.end_date, record.training_review.proposal.values.end_date],
                            ["Часы", record.hours, record.training_review.proposal.values.hours],
                          ].filter(([, , proposed]) => proposed !== undefined).map(([label, current, proposed]) => (
                            <div key={String(label)}>
                              <dt className="font-medium">{label}</dt>
                              <dd>Было: {String(current ?? "—")} · Предложено: {String(proposed ?? "—")}</dd>
                            </div>
                          ))}
                        </dl>
                        <div className="mt-2 flex gap-2"><button type="button" className="rounded border border-emerald-600 px-2 py-1" onClick={() => void perform(record, "accept_proposal")}>Подтвердить предложение</button><button type="button" className="rounded border border-red-500 px-2 py-1" onClick={() => void perform(record, "reject_proposal")}>Отклонить предложение</button></div>
                      </td>
                    </tr>
                  ) : null}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function TrainingRecordCard({ record }: { record: PprTrainingRecordResponse }) {
  return (
    <div className="rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800">
      <div className="font-medium text-zinc-900 dark:text-zinc-50">
        {record.title || "Обучение без названия"}
      </div>
      <dl className="mt-2 grid gap-1 text-xs text-zinc-600 dark:text-zinc-400 sm:grid-cols-2">
        <div>
          <dt className="inline">Вид: </dt>
          <dd className="inline">{record.training_kind}</dd>
        </div>
        {record.organization_name ? (
          <div>
            <dt className="inline">Организация: </dt>
            <dd className="inline">{record.organization_name}</dd>
          </div>
        ) : null}
        <div>
          <dt className="inline">Период: </dt>
          <dd className="inline">
            {formatPersonnelDateRange(record.started_at, record.completed_at, { precision: "year" })}
          </dd>
        </div>
        <div>
          <dt className="inline">Статус: </dt>
          <dd className="inline">{record.lifecycle_status}</dd>
        </div>
      </dl>
    </div>
  );
}

function CollapsibleGroup({
  title,
  records,
}: {
  title: string;
  records: PprTrainingRecordResponse[];
}) {
  const [open, setOpen] = React.useState(false);
  if (records.length === 0) return null;
  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-sm font-medium text-zinc-700 underline-offset-2 hover:underline dark:text-zinc-300"
        aria-expanded={open}
      >
        {title} ({records.length})
      </button>
      {open ? (
        <div className="space-y-2">
          {records.map((record) => (
            <TrainingRecordCard key={record.record_id ?? record.title} record={record} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function PprCardTrainingSection({ active, superseded, voided, employeeId }: Props) {
  const summaryRecords = React.useMemo(
    () => active.map((record) => trainingSummaryRecordFromPprRecord(record)),
    [active],
  );

  return (
    <div className="space-y-4" data-testid="ppr-training-section">
      <TrainingSummaryBlocks records={summaryRecords} testIdPrefix="ppr-training-summary" />

      <div className="space-y-2">
        <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Действующие записи</h3>
        {active.length === 0 ? (
          <p className="text-sm text-zinc-500">Нет действующих записей.</p>
        ) : (
          active.map((record) => <TrainingRecordCard key={record.record_id ?? record.title} record={record} />)
        )}
      </div>
      <CollapsibleGroup title="Заменённые записи" records={superseded} />
      <CollapsibleGroup title="Аннулированные записи" records={voided} />
      <ImportedTrainingReviewBlock employeeId={employeeId} />
    </div>
  );
}
