"use client";

import * as React from "react";

import { getArchiveReviewRow, mapOoApiError, saveArchiveReviewRow } from "../_lib/api";
import type {
  ArchiveInitialReviewState,
  ArchiveReviewDetail,
  ArchiveReviewOutcome,
} from "../_lib/types";

const OUTCOMES: Array<{ value: ArchiveReviewOutcome; label: string }> = [
  { value: "CONFIRMED", label: "Реквизиты приказа подтверждены" },
  { value: "NEEDS_CLARIFICATION", label: "Требуется дополнительное уточнение" },
  { value: "DRAFT_ORDER", label: "Проект или предварительная версия приказа" },
  { value: "ORDER_ANNEX", label: "Приложение к приказу" },
  { value: "SUPPORTING_DOCUMENT", label: "Документ-основание или сопроводительный документ" },
  { value: "DUPLICATE", label: "Дубль" },
  { value: "NOT_AN_ORDER", label: "Документ не относится к приказам" },
];

const OUTCOME_HINTS: Partial<Record<ArchiveReviewOutcome, string>> = {
  DRAFT_ORDER: "Укажите, почему файл признан проектом или предварительной версией.",
  ORDER_ANNEX: "По возможности укажите приказ, к которому относится приложение.",
  SUPPORTING_DOCUMENT: "Укажите вид основания или сопроводительного документа.",
  DUPLICATE: "Укажите дублирующую запись.",
  NOT_AN_ORDER: "Объясните, почему документ не относится к приказам.",
};

const INITIAL_REVIEW_STATE_LABELS: Record<ArchiveInitialReviewState, string> = {
  NEEDS_REQUISITES: "Требуется уточнить номер или дату",
  REQUISITES_PRECONFIRMED: "Реквизиты предварительно подтверждены",
  NEEDS_DOCUMENT_TYPE: "Требуется проверить тип документа",
  POSSIBLE_NON_ORDER: "Возможно, не является приказом",
};

type FormState = {
  outcome: "" | ArchiveReviewOutcome;
  documentType: string;
  orderNumber: string;
  orderDate: string;
  subject: string;
  comment: string;
};

export default function ArchiveReviewDialog({
  rowId,
  canReview,
  reviewerName = "Текущий пользователь",
  onClose,
  onSaved,
}: {
  rowId: number;
  canReview: boolean;
  reviewerName?: string;
  onClose: () => void;
  onSaved: (detail: ArchiveReviewDetail) => void;
}) {
  const [detail, setDetail] = React.useState<ArchiveReviewDetail | null>(null);
  const [form, setForm] = React.useState<FormState | null>(null);
  const [initialForm, setInitialForm] = React.useState<FormState | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [validation, setValidation] = React.useState<string | null>(null);
  const [discardConfirmationOpen, setDiscardConfirmationOpen] = React.useState(false);

  React.useEffect(() => {
    let active = true;
    setDetail(null);
    setForm(null);
    setInitialForm(null);
    setLoading(true);
    setError(null);
    setValidation(null);
    setDiscardConfirmationOpen(false);
    getArchiveReviewRow(rowId)
      .then((value) => {
        if (!active) return;
        const next: FormState = {
          outcome: value.review_outcome === "NEEDS_CLARIFICATION" ? "" : value.review_outcome ?? "",
          documentType: value.confirmed_document_type ?? "",
          orderNumber: value.confirmed_order_number ?? "",
          orderDate: value.confirmed_order_date ?? "",
          subject: value.confirmed_subject ?? "",
          comment: value.review_comment ?? "",
        };
        setDetail(value);
        setForm(next);
        setInitialForm(next);
      })
      .catch((reason) => {
        if (active) setError(errorMessage(reason, "Не удалось загрузить запись архива"));
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [rowId]);

  const dirty = hasUnsavedReviewChanges(form, initialForm);
  const completed = detail?.review_outcome != null && detail.review_outcome !== "NEEDS_CLARIFICATION";
  const availableOutcomes = detail?.review_outcome === "NEEDS_CLARIFICATION"
    ? OUTCOMES.filter((item) => item.value !== "NEEDS_CLARIFICATION")
    : OUTCOMES;
  const showConfirmedFields = form?.outcome === "CONFIRMED";
  const showComment = Boolean(form?.outcome);

  React.useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);

  function requestClose() {
    if (canReview && dirty) {
      setDiscardConfirmationOpen(true);
      return;
    }
    onClose();
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!canReview || !detail || !form || !form.outcome || completed) return;
    if (
      form.outcome === "CONFIRMED" &&
      (!form.documentType.trim() || !form.orderNumber.trim() || !form.orderDate || !form.subject.trim())
    ) {
      setValidation("Для подтверждения обязательны тип документа, номер, дата и предмет.");
      return;
    }
    if (form.outcome !== "CONFIRMED" && !form.comment.trim()) {
      setValidation("Для выбранного решения обязателен комментарий проверяющего.");
      return;
    }
    setValidation(null);
    setError(null);
    setSaving(true);
    try {
      const saved = await saveArchiveReviewRow(rowId, {
        expected_version: detail.version,
        review_outcome: form.outcome,
        confirmed_document_type: showConfirmedFields ? form.documentType.trim() || null : null,
        confirmed_order_number: showConfirmedFields ? form.orderNumber.trim() || null : null,
        confirmed_order_date: showConfirmedFields ? form.orderDate || null : null,
        confirmed_subject: showConfirmedFields ? form.subject.trim() || null : null,
        review_comment: form.comment.trim() || null,
      });
      setInitialForm(form);
      onSaved(saved);
    } catch (reason) {
      setError(errorMessage(reason, "Не удалось сохранить результат проверки"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && requestClose()}>
      <div className="max-h-[92vh] w-full max-w-4xl overflow-y-auto rounded-xl bg-white p-5 shadow-xl dark:bg-zinc-950" role="dialog" aria-modal="true" aria-labelledby="archive-review-dialog-title">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="archive-review-dialog-title" className="text-lg font-semibold">
              {canReview ? "Проверка записи архива" : "Просмотр записи архива"}
            </h2>
            {detail ? <p className="text-sm text-zinc-500">Excel-строка {detail.excel_row} · версия {detail.version}</p> : null}
          </div>
          <button type="button" autoFocus aria-label="Закрыть карточку" className="rounded-md border px-3 py-1" onClick={requestClose}>Закрыть</button>
        </div>

        {loading ? <p className="py-8 text-center text-sm text-zinc-500">Загрузка карточки…</p> : null}
        {error ? <p className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">{error}</p> : null}
        {detail && form ? (
          <form className="mt-4 space-y-5" onSubmit={submit}>
            <fieldset className="grid gap-3 rounded-lg border p-4 sm:grid-cols-2" disabled>
              <legend className="px-1 font-medium">Исходные данные</legend>
              <ReadOnly label="Раздел архива" value={detail.archive_section} />
              <ReadOnly label="Имя файла" value={detail.file_name} />
              <ReadOnly label="Исходный статус" value={detail.source_status} />
              <ReadOnly label="Тип документа" value={detail.source_document_type} />
              <ReadOnly label="Номер" value={detail.order_number} />
              <ReadOnly label="Дата" value={detail.order_date} />
              <ReadOnly label="Предмет/заголовок" value={detail.subject} />
              <ReadOnly label="Относительный путь" value={detail.relative_path} />
              <ReadOnly label="Исходное состояние проверки" value={initialReviewStateLabel(detail.initial_review_state)} />
              <ReadOnly label="Дубликат файла" value={detail.duplicate_sha ? "Да" : "Нет"} />
              <ReadOnly label="Официальный документ" value={detail.official_document_id ? `Документ #${detail.official_document_id}` : "Не связан"} />
            </fieldset>

            {canReview ? (
            <fieldset className="grid gap-3 rounded-lg border p-4 sm:grid-cols-2" disabled={completed || saving}>
              <legend className="px-1 font-medium">Результат проверки</legend>
              {completed ? <p className="sm:col-span-2 rounded-md bg-zinc-100 p-2 text-sm">Завершённое решение доступно только для чтения.</p> : null}
              {completed && detail.reviewer_display_name && detail.reviewed_at ? (
                <p className="sm:col-span-2 text-sm">Проверил: {detail.reviewer_display_name}, {formatReviewedAt(detail.reviewed_at)}</p>
              ) : (
                <p className="sm:col-span-2 text-sm">Проверку сохранит: {reviewerName}</p>
              )}
              <label className="sm:col-span-2 flex flex-col gap-1 text-sm">Решение
                <select aria-label="Решение проверки" className="rounded-md border px-2 py-2 dark:bg-zinc-900" value={form.outcome} onChange={(e) => { setForm({ ...form, outcome: e.target.value as FormState["outcome"] }); setValidation(null); }}>
                  <option value="">Выберите решение</option>
                  {availableOutcomes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>
              {!form.outcome ? <p className="sm:col-span-2 text-sm text-zinc-500">Выберите решение, чтобы заполнить необходимые поля.</p> : null}
              {form.outcome && OUTCOME_HINTS[form.outcome] ? <p className="sm:col-span-2 text-sm text-zinc-500">{OUTCOME_HINTS[form.outcome]}</p> : null}
              {showConfirmedFields ? (
                <>
                  <p className="sm:col-span-2 text-sm text-zinc-500">Введите подтверждённые тип документа, номер, дату и название приказа.</p>
                  <TextField label="Подтверждённый тип документа" value={form.documentType} maxLength={200} onChange={(documentType) => setForm({ ...form, documentType })} />
                  <TextField label="Подтверждённый номер" value={form.orderNumber} maxLength={100} onChange={(orderNumber) => setForm({ ...form, orderNumber })} />
                  <label className="flex flex-col gap-1 text-sm">Подтверждённая дата
                    <input aria-label="Подтверждённая дата" type="date" className="rounded-md border px-2 py-2 dark:bg-zinc-900" value={form.orderDate} onChange={(e) => setForm({ ...form, orderDate: e.target.value })} />
                  </label>
                  <TextField label="Подтверждённое название приказа" value={form.subject} maxLength={1000} onChange={(subject) => setForm({ ...form, subject })} />
                </>
              ) : null}
              {showComment ? (
                <label className="sm:col-span-2 flex flex-col gap-1 text-sm">Комментарий проверяющего
                  <textarea aria-label="Комментарий проверяющего" aria-required={form.outcome !== "CONFIRMED"} className="min-h-24 rounded-md border px-2 py-2 dark:bg-zinc-900" maxLength={2000} value={form.comment} onChange={(e) => { const comment = e.target.value; setForm({ ...form, comment }); if (comment.trim()) setValidation(null); }} />
                </label>
              ) : null}
            </fieldset>
            ) : (
              <fieldset className="grid gap-3 rounded-lg border p-4 sm:grid-cols-2" disabled>
                <legend className="px-1 font-medium">Результат проверки</legend>
                <p className="sm:col-span-2 rounded-md bg-zinc-100 p-2 text-sm">Просмотр без права проверки записи</p>
                <ReadOnly label="Результат проверки" value={detail.review_outcome ? outcomeLabel(detail.review_outcome) : "Не проверено"} />
                {detail.review_outcome === "CONFIRMED" ? (
                  <>
                    <ReadOnly label="Подтверждённый тип документа" value={detail.confirmed_document_type} />
                    <ReadOnly label="Подтверждённый номер" value={detail.confirmed_order_number} />
                    <ReadOnly label="Подтверждённая дата" value={detail.confirmed_order_date} />
                    <ReadOnly label="Подтверждённое название приказа" value={detail.confirmed_subject} />
                  </>
                ) : null}
                {detail.review_comment ? <ReadOnly label="Комментарий проверяющего" value={detail.review_comment} /> : null}
                {detail.reviewer_display_name && detail.reviewed_at ? (
                  <p className="sm:col-span-2 text-sm">Проверил: {detail.reviewer_display_name}, {formatReviewedAt(detail.reviewed_at)}</p>
                ) : null}
              </fieldset>
            )}
            {validation ? <p className="text-sm text-red-700" role="alert">{validation}</p> : null}
            <div className="flex justify-end gap-2">
              <button type="button" className="rounded-md border px-4 py-2" onClick={requestClose}>{canReview ? "Отмена" : "Закрыть"}</button>
              {canReview ? (
                <button type="submit" className="rounded-md bg-blue-600 px-4 py-2 text-white disabled:opacity-50" disabled={saving || completed || !form.outcome}>{saving ? "Сохранение…" : "Сохранить"}</button>
              ) : null}
            </div>
          </form>
        ) : null}
      </div>
      {discardConfirmationOpen ? (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4" role="presentation">
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl dark:bg-zinc-950" role="alertdialog" aria-modal="true" aria-labelledby="archive-review-discard-title" aria-describedby="archive-review-discard-description">
            <h3 id="archive-review-discard-title" className="font-semibold">Несохранённые изменения</h3>
            <p id="archive-review-discard-description" className="mt-2 text-sm">Есть несохранённые изменения. Закрыть карточку без сохранения?</p>
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" autoFocus className="rounded-md border px-3 py-2" onClick={() => setDiscardConfirmationOpen(false)}>Остаться в карточке</button>
              <button type="button" className="rounded-md bg-red-600 px-3 py-2 text-white" onClick={onClose}>Закрыть без сохранения</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ReadOnly({ label, value }: { label: string; value: string | number | null }) {
  return <label className="flex flex-col gap-1 text-sm">{label}<input aria-label={label} readOnly className="rounded-md border bg-zinc-50 px-2 py-2 disabled:opacity-100 dark:bg-zinc-900" value={value ?? "—"} /></label>;
}

function TextField({ label, value, maxLength, onChange }: { label: string; value: string; maxLength: number; onChange: (value: string) => void }) {
  return <label className="flex flex-col gap-1 text-sm">{label}<input aria-label={label} className="rounded-md border px-2 py-2 dark:bg-zinc-900" maxLength={maxLength} value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

function initialReviewStateLabel(state: ArchiveInitialReviewState): string {
  return INITIAL_REVIEW_STATE_LABELS[state];
}

function outcomeLabel(outcome: ArchiveReviewOutcome): string {
  return OUTCOMES.find((item) => item.value === outcome)?.label ?? outcome;
}

function hasUnsavedReviewChanges(current: FormState | null, initial: FormState | null): boolean {
  if (!current || !initial) return false;
  return (
    current.outcome !== initial.outcome ||
    current.documentType !== initial.documentType ||
    current.orderNumber !== initial.orderNumber ||
    current.orderDate !== initial.orderDate ||
    current.subject !== initial.subject ||
    current.comment !== initial.comment
  );
}

function errorMessage(reason: unknown, fallback: string): string {
  const status = typeof reason === "object" && reason !== null && "status" in reason ? Number((reason as { status: unknown }).status) : 0;
  if (status === 403) return "Недостаточно прав для сохранения проверки.";
  if (status === 409) return "Запись уже изменена или проверка завершена. Закройте карточку и откройте её снова.";
  if (status === 422) return "Проверьте обязательные поля и допустимую длину значений.";
  return mapOoApiError(reason, fallback);
}

function formatReviewedAt(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("ru-RU");
}
