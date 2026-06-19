"use client";

import * as React from "react";

import ImportDiffStatusBadge from "./ImportDiffStatusBadge";
import ImportFieldDiffPanel from "./ImportFieldDiffPanel";
import {
  EMPLOYEE_BINDING_METHOD_LABELS,
  EMPLOYEE_BINDING_STATUS_LABELS,
  employeeBindingBadgeClass,
  NORMALIZED_RECORD_KIND_LABELS,
  NORMALIZED_REVIEW_STATUS_LABELS,
  mapImportApiError,
  patchNormalizedRecordEmployeeBinding,
  patchNormalizedRecordReview,
  patchNormalizedRecordReviewOverride,
  type NormalizedRecord,
  type NormalizedRecordKind,
  type NormalizedRecordReviewOverride,
  type NormalizedRecordReviewStatus,
} from "../_lib/importApi.client";

type Props = {
  record: NormalizedRecord | null;
  open: boolean;
  onClose: () => void;
  onReviewed: (record: NormalizedRecord) => void;
  onToast: (message: string, kind?: "success" | "error") => void;
};

type EditDraft = {
  title: string;
  provider: string;
  hours: string;
  issue_date: string;
  expiry_date: string;
  document_number: string;
  specialty_text: string;
};

function reviewStatusBadgeClass(status: NormalizedRecordReviewStatus): string {
  switch (status) {
    case "pending":
      return "border-amber-200 bg-amber-100 text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200";
    case "approved":
      return "border-green-200 bg-green-100 text-green-900 dark:border-green-800 dark:bg-green-950/50 dark:text-green-200";
    case "rejected":
      return "border-red-200 bg-red-100 text-red-900 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200";
    default:
      return "border-zinc-200 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300";
  }
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("ru-RU");
}

function toInputDate(value: string | null | undefined): string {
  if (!value) return "";
  return value.slice(0, 10);
}

function draftFromRecord(record: NormalizedRecord): EditDraft {
  return {
    title: record.title ?? "",
    provider: record.provider ?? "",
    hours: record.hours != null ? String(record.hours) : "",
    issue_date: toInputDate(record.issue_date),
    expiry_date: toInputDate(record.expiry_date),
    document_number: record.document_number ?? "",
    specialty_text: record.specialty_text ?? "",
  };
}

function buildOverridePayload(
  kind: NormalizedRecordKind,
  draft: EditDraft
): NormalizedRecordReviewOverride {
  const payload: NormalizedRecordReviewOverride = {};
  if (kind === "education" || kind === "training" || kind === "certificate") {
    payload.title = draft.title.trim() || null;
  }
  if (kind === "education" || kind === "training") {
    payload.provider = draft.provider.trim() || null;
  }
  if (kind === "training") {
    payload.hours = draft.hours.trim() ? Number(draft.hours) : null;
    payload.issue_date = draft.issue_date || null;
  }
  if (kind === "education") {
    payload.issue_date = draft.issue_date || null;
    payload.document_number = draft.document_number.trim() || null;
  }
  if (kind === "certificate") {
    payload.specialty_text = draft.specialty_text.trim() || null;
    payload.issue_date = draft.issue_date || null;
    payload.expiry_date = draft.expiry_date || null;
    payload.document_number = draft.document_number.trim() || null;
  }
  if (kind === "category") {
    payload.title = draft.title.trim() || null;
    payload.specialty_text = draft.specialty_text.trim() || null;
    payload.issue_date = draft.issue_date || null;
    payload.expiry_date = draft.expiry_date || null;
  }
  return payload;
}

function FieldRow({
  label,
  value,
  parsedHint,
}: {
  label: string;
  value: React.ReactNode;
  parsedHint?: string | null;
}) {
  return (
    <div className="grid gap-1 sm:grid-cols-[140px_1fr] sm:gap-3">
      <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</div>
      <div>
        <div className="text-sm text-zinc-900 dark:text-zinc-100">{value || "—"}</div>
        {parsedHint ? (
          <div className="mt-0.5 text-xs text-zinc-500">Исходный парсинг: {parsedHint}</div>
        ) : null}
      </div>
    </div>
  );
}

function EditField({
  label,
  value,
  onChange,
  type = "text",
  parsedHint,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  parsedHint?: string | null;
}) {
  return (
    <label className="grid gap-1 sm:grid-cols-[140px_1fr] sm:items-center sm:gap-3">
      <span className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</span>
      <span>
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
        />
        {parsedHint ? (
          <span className="mt-0.5 block text-xs text-zinc-500">Исходный парсинг: {parsedHint}</span>
        ) : null}
      </span>
    </label>
  );
}

function parsedHint(
  record: NormalizedRecord,
  field: keyof NormalizedRecordReviewOverride,
  formatter: (v: string | null | undefined) => string = (v) => v || "—"
): string | null {
  const parsed = record.parsed_values?.[field];
  const effective = record[field as keyof NormalizedRecord];
  if (parsed == null && effective == null) return null;
  const parsedText = formatter(parsed as string | null | undefined);
  const effectiveText = formatter(effective as string | null | undefined);
  return parsedText !== effectiveText ? parsedText : null;
}

function PayloadSection({ record }: { record: NormalizedRecord }) {
  const kind = record.record_kind;

  if (kind === "training") {
    return (
      <div className="space-y-3">
        <FieldRow label="Название курса" value={record.title} parsedHint={parsedHint(record, "title")} />
        <FieldRow label="Организация" value={record.provider} parsedHint={parsedHint(record, "provider")} />
        <FieldRow
          label="Часы"
          value={record.hours != null ? String(record.hours) : null}
          parsedHint={parsedHint(record, "hours", (v) => (v != null ? String(v) : "—"))}
        />
        <FieldRow label="Дата выдачи" value={formatDate(record.issue_date)} parsedHint={parsedHint(record, "issue_date", formatDate)} />
      </div>
    );
  }

  if (kind === "certificate") {
    return (
      <div className="space-y-3">
        <FieldRow label="Название" value={record.title} parsedHint={parsedHint(record, "title")} />
        <FieldRow label="Специальность" value={record.specialty_text} parsedHint={parsedHint(record, "specialty_text")} />
        <FieldRow label="Дата выдачи" value={formatDate(record.issue_date)} parsedHint={parsedHint(record, "issue_date", formatDate)} />
        <FieldRow label="Действует до" value={formatDate(record.expiry_date)} parsedHint={parsedHint(record, "expiry_date", formatDate)} />
        <FieldRow label="Номер документа" value={record.document_number} parsedHint={parsedHint(record, "document_number")} />
      </div>
    );
  }

  if (kind === "category") {
    return (
      <div className="space-y-3">
        <FieldRow label="Категория" value={record.title} parsedHint={parsedHint(record, "title")} />
        <FieldRow label="Специальность" value={record.specialty_text} parsedHint={parsedHint(record, "specialty_text")} />
        <FieldRow label="Дата присвоения" value={formatDate(record.issue_date)} parsedHint={parsedHint(record, "issue_date", formatDate)} />
        <FieldRow label="Действует до" value={formatDate(record.expiry_date)} parsedHint={parsedHint(record, "expiry_date", formatDate)} />
      </div>
    );
  }

  if (kind === "education") {
    return (
      <div className="space-y-3">
        <FieldRow label="Название" value={record.title} parsedHint={parsedHint(record, "title")} />
        <FieldRow label="Организация" value={record.provider} parsedHint={parsedHint(record, "provider")} />
        <FieldRow label="Дата выдачи" value={formatDate(record.issue_date)} parsedHint={parsedHint(record, "issue_date", formatDate)} />
        <FieldRow label="Номер документа" value={record.document_number} parsedHint={parsedHint(record, "document_number")} />
      </div>
    );
  }

  return (
    <pre className="overflow-x-auto rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs dark:border-zinc-800 dark:bg-zinc-900">
      {JSON.stringify(record, null, 2)}
    </pre>
  );
}

function EditPayloadSection({
  record,
  draft,
  onChange,
}: {
  record: NormalizedRecord;
  draft: EditDraft;
  onChange: (draft: EditDraft) => void;
}) {
  const kind = record.record_kind;
  const set = (key: keyof EditDraft, value: string) => onChange({ ...draft, [key]: value });

  if (kind === "training") {
    return (
      <div className="space-y-3">
        <EditField label="Название курса" value={draft.title} onChange={(v) => set("title", v)} parsedHint={parsedHint(record, "title")} />
        <EditField label="Организация" value={draft.provider} onChange={(v) => set("provider", v)} parsedHint={parsedHint(record, "provider")} />
        <EditField label="Часы" value={draft.hours} onChange={(v) => set("hours", v)} type="number" parsedHint={parsedHint(record, "hours", (v) => (v != null ? String(v) : "—"))} />
        <EditField label="Дата выдачи" value={draft.issue_date} onChange={(v) => set("issue_date", v)} type="date" parsedHint={parsedHint(record, "issue_date", formatDate)} />
      </div>
    );
  }

  if (kind === "certificate") {
    return (
      <div className="space-y-3">
        <EditField label="Название" value={draft.title} onChange={(v) => set("title", v)} parsedHint={parsedHint(record, "title")} />
        <EditField label="Специальность" value={draft.specialty_text} onChange={(v) => set("specialty_text", v)} parsedHint={parsedHint(record, "specialty_text")} />
        <EditField label="Дата выдачи" value={draft.issue_date} onChange={(v) => set("issue_date", v)} type="date" parsedHint={parsedHint(record, "issue_date", formatDate)} />
        <EditField label="Действует до" value={draft.expiry_date} onChange={(v) => set("expiry_date", v)} type="date" parsedHint={parsedHint(record, "expiry_date", formatDate)} />
        <EditField label="Номер документа" value={draft.document_number} onChange={(v) => set("document_number", v)} parsedHint={parsedHint(record, "document_number")} />
      </div>
    );
  }

  if (kind === "category") {
    return (
      <div className="space-y-3">
        <EditField label="Категория" value={draft.title} onChange={(v) => set("title", v)} parsedHint={parsedHint(record, "title")} />
        <EditField label="Специальность" value={draft.specialty_text} onChange={(v) => set("specialty_text", v)} parsedHint={parsedHint(record, "specialty_text")} />
        <EditField label="Дата присвоения" value={draft.issue_date} onChange={(v) => set("issue_date", v)} type="date" parsedHint={parsedHint(record, "issue_date", formatDate)} />
        <EditField label="Действует до" value={draft.expiry_date} onChange={(v) => set("expiry_date", v)} type="date" parsedHint={parsedHint(record, "expiry_date", formatDate)} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <EditField label="Название" value={draft.title} onChange={(v) => set("title", v)} parsedHint={parsedHint(record, "title")} />
      <EditField label="Организация" value={draft.provider} onChange={(v) => set("provider", v)} parsedHint={parsedHint(record, "provider")} />
      <EditField label="Дата выдачи" value={draft.issue_date} onChange={(v) => set("issue_date", v)} type="date" parsedHint={parsedHint(record, "issue_date", formatDate)} />
      <EditField label="Номер документа" value={draft.document_number} onChange={(v) => set("document_number", v)} parsedHint={parsedHint(record, "document_number")} />
    </div>
  );
}

export default function ImportNormalizedRecordDrawer({ record, open, onClose, onReviewed, onToast }: Props) {
  const [notes, setNotes] = React.useState("");
  const [acting, setActing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState<EditDraft>({
    title: "",
    provider: "",
    hours: "",
    issue_date: "",
    expiry_date: "",
    document_number: "",
    specialty_text: "",
  });
  const [manualEmployeeId, setManualEmployeeId] = React.useState("");

  React.useEffect(() => {
    if (!open) return;
    setNotes(record?.review_notes || "");
    setError(null);
    setEditing(false);
    if (record) {
      setDraft(draftFromRecord(record));
      setManualEmployeeId(record.employee_id ? String(record.employee_id) : "");
    }
  }, [open, record]);

  React.useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && !editing) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose, editing]);

  async function applyStatus(target: NormalizedRecordReviewStatus) {
    if (!record) return;
    setActing(true);
    setError(null);
    try {
      const updated = await patchNormalizedRecordReview(record.record_id, {
        review_status: target,
        review_notes: target === "pending" ? undefined : notes.trim() || undefined,
      });
      onReviewed(updated);
      onToast(
        target === "approved"
          ? "Запись утверждена"
          : target === "rejected"
            ? "Запись отклонена"
            : "Запись возвращена в ожидание",
        "success"
      );
    } catch (e) {
      const message = mapImportApiError(e);
      setError(message);
      onToast(message, "error");
    } finally {
      setActing(false);
    }
  }

  async function saveEmployeeBinding() {
    if (!record) return;
    const employeeId = Number(manualEmployeeId);
    if (!Number.isInteger(employeeId) || employeeId < 1) {
      setError("Укажите корректный ID сотрудника");
      return;
    }
    setActing(true);
    setError(null);
    try {
      const updated = await patchNormalizedRecordEmployeeBinding(record.record_id, employeeId);
      onReviewed(updated);
      onToast("Сотрудник привязан", "success");
    } catch (e) {
      const message = mapImportApiError(e);
      setError(message);
      onToast(message, "error");
    } finally {
      setActing(false);
    }
  }

  async function saveOverride() {
    if (!record) return;
    setActing(true);
    setError(null);
    try {
      const updated = await patchNormalizedRecordReviewOverride(
        record.record_id,
        buildOverridePayload(record.record_kind, draft)
      );
      onReviewed(updated);
      setEditing(false);
      onToast("Исправления сохранены", "success");
    } catch (e) {
      const message = mapImportApiError(e);
      setError(message);
      onToast(message, "error");
    } finally {
      setActing(false);
    }
  }

  if (!open || !record) return null;

  const status = record.review_status;
  const canApprove = status === "pending" && !editing;
  const canReject = status === "pending" && !editing;
  const canEdit = status === "pending";
  const canReturnPending = (status === "approved" || status === "rejected") && !editing;
  const locked = status === "promoted" || status === "superseded";
  const hasOverride = Boolean(record.review_override && Object.keys(record.review_override).length > 0);
  const binding = record.employee_binding;
  const bindingStatus = binding?.status ?? (record.employee_id ? "bound" : "unbound");
  const canBindEmployee = !locked && bindingStatus !== "bound";

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-zinc-600/35 backdrop-blur-sm dark:bg-black/50" onClick={onClose} />

      <div className="relative ml-auto flex h-full w-full max-w-[720px] flex-col border-l border-zinc-200 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between gap-4 border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Нормализованная запись</h2>
            <p className="mt-1 text-sm text-zinc-500">ID {record.record_id} · batch {record.batch_id}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-sm text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-900"
          >
            Закрыть
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
          ) : null}

          {record.diff_status ? (
            <section className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Сравнение с эталоном</h3>
                <ImportDiffStatusBadge status={record.diff_status} />
              </div>
              <ImportFieldDiffPanel
                fieldDiffs={record.field_diffs}
                recordKind={record.record_kind}
              />
            </section>
          ) : null}

          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Общие данные</h3>
            <FieldRow label="Сотрудник" value={record.full_name || (record.employee_id ? `ID ${record.employee_id}` : "—")} />
            <FieldRow label="ИИН" value={record.iin_masked || "—"} />
            <FieldRow
              label="Привязка"
              value={
                <span className="space-y-1">
                  <span
                    className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${employeeBindingBadgeClass(bindingStatus)}`}
                  >
                    {EMPLOYEE_BINDING_STATUS_LABELS[bindingStatus] || bindingStatus}
                  </span>
                  {binding?.method ? (
                    <span className="block text-xs text-zinc-500">
                      {EMPLOYEE_BINDING_METHOD_LABELS[binding.method] || binding.method}
                    </span>
                  ) : null}
                  {binding?.directory_employee_name ? (
                    <span className="block text-xs text-zinc-600 dark:text-zinc-400">
                      Справочник: {binding.directory_employee_name}
                      {binding.employee_id ? ` (ID ${binding.employee_id})` : ""}
                    </span>
                  ) : null}
                  {binding?.reason ? (
                    <span className="block text-xs text-amber-700 dark:text-amber-300">{binding.reason}</span>
                  ) : null}
                  {binding?.candidate_employee_ids && binding.candidate_employee_ids.length > 0 ? (
                    <span className="block text-xs text-zinc-500">
                      Кандидаты: {binding.candidate_employee_ids.join(", ")}
                    </span>
                  ) : null}
                </span>
              }
            />
            <FieldRow
              label="Тип записи"
              value={NORMALIZED_RECORD_KIND_LABELS[record.record_kind] || record.record_kind}
            />
            <FieldRow label="Источник" value={record.source_field} />
            <FieldRow
              label="Статус"
              value={
                <span
                  className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${reviewStatusBadgeClass(status)}`}
                >
                  {NORMALIZED_REVIEW_STATUS_LABELS[status] || status}
                </span>
              }
            />
            {hasOverride ? (
              <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-100">
                Есть ручные исправления
                {record.review_override_updated_at
                  ? ` · ${formatDate(record.review_override_updated_at)}`
                  : ""}
              </div>
            ) : null}
          </section>

          {canBindEmployee && !editing ? (
            <section className="space-y-3 rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Ручная привязка</h3>
              <p className="text-xs text-zinc-500">
                Укажите ID сотрудника из кадрового справочника. Привязка применится ко всем записям этой строки импорта.
              </p>
              <div className="flex flex-wrap items-end gap-2">
                <label className="grid gap-1 text-sm">
                  <span className="text-xs font-medium uppercase tracking-wide text-zinc-500">ID сотрудника</span>
                  <input
                    type="number"
                    min={1}
                    value={manualEmployeeId}
                    onChange={(e) => setManualEmployeeId(e.target.value)}
                    className="w-40 rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  />
                </label>
                <button
                  type="button"
                  disabled={acting}
                  onClick={saveEmployeeBinding}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  Привязать
                </button>
              </div>
            </section>
          ) : null}

          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Исходный текст</h3>
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">
              {record.source_text || "—"}
            </div>
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                {editing ? "Исправить перед утверждением" : "Нормализованные данные"}
              </h3>
              {canEdit && !editing ? (
                <button
                  type="button"
                  disabled={acting}
                  onClick={() => {
                    setDraft(draftFromRecord(record));
                    setEditing(true);
                  }}
                  className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm font-medium hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
                >
                  Редактировать
                </button>
              ) : null}
            </div>
            {editing ? (
              <EditPayloadSection record={record} draft={draft} onChange={setDraft} />
            ) : (
              <PayloadSection record={record} />
            )}
            {!editing ? (
              <div className="grid gap-2 text-xs text-zinc-500 sm:grid-cols-2">
                <div>Метод: {record.parse_method}</div>
                <div>Уверенность: {record.confidence != null ? record.confidence : "—"}</div>
                <div>Ключ: {record.source_record_key}</div>
                <div>Тип документа: {record.document_type_code || "—"}</div>
              </div>
            ) : null}
          </section>

          {!locked && !editing ? (
            <section className="space-y-2">
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300" htmlFor="review-notes">
                Комментарий проверки
              </label>
              <textarea
                id="review-notes"
                rows={3}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                placeholder="Необязательно"
              />
            </section>
          ) : locked ? (
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              Статус «{NORMALIZED_REVIEW_STATUS_LABELS[status]}» не может быть изменён вручную.
            </div>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2 border-t border-zinc-200 px-5 py-4 dark:border-zinc-800">
          {editing ? (
            <>
              <button
                type="button"
                disabled={acting}
                onClick={saveOverride}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {acting ? "Сохранение…" : "Сохранить исправления"}
              </button>
              <button
                type="button"
                disabled={acting}
                onClick={() => {
                  setDraft(draftFromRecord(record));
                  setEditing(false);
                }}
                className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
              >
                Отмена
              </button>
            </>
          ) : (
            <>
              {canApprove ? (
                <button
                  type="button"
                  disabled={acting}
                  onClick={() => applyStatus("approved")}
                  className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                >
                  Утвердить
                </button>
              ) : null}
              {canReject ? (
                <button
                  type="button"
                  disabled={acting}
                  onClick={() => applyStatus("rejected")}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                >
                  Отклонить
                </button>
              ) : null}
              {canReturnPending ? (
                <button
                  type="button"
                  disabled={acting}
                  onClick={() => applyStatus("pending")}
                  className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
                >
                  Вернуть в ожидание
                </button>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
