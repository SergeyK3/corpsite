"use client";

import * as React from "react";

import {
  generatePersonnelOrderEditorial,
  getPersonnelOrderEditorial,
  mapPersonnelOrdersApiError,
  patchPersonnelOrderEditorialBlock,
  resetPersonnelOrderEditorialBlock,
  updatePersonnelOrderItem,
  type PersonnelOrderDetailResponse,
  type PersonnelOrderEditorialBlock,
  type PersonnelOrderEditorialState,
  type PersonnelOrderHeader,
  type PersonnelOrderItem,
} from "../_lib/personnelOrdersApi.client";
import {
  PERSONNEL_ORDER_EDITORIAL_LOCALE_LABELS,
  PERSONNEL_ORDER_EDITORIAL_UI_LOCALES,
  PERSONNEL_ORDER_EDITORIAL_UI_STATUS_LABELS,
  buildEditorialDocumentSections,
  displayPersonnelOrderEditorialBlockText,
  editorialLocaleHint,
  hasRequiredEditorialLocales,
  mapEditorialConflictMessage,
  resolvePersonnelOrderEditorialUiStatus,
  type PersonnelOrderEditorialUiLocale,
  type PersonnelOrderEditorialUiStatus,
} from "../_lib/personnelOrderEditorialUi";
import PersonnelOrderDocumentRequisitesPreview from "./PersonnelOrderDocumentRequisitesPreview";

const GENERATE_CONFIRM_MESSAGE = [
  "Пересформировать текст приказа?",
  "",
  "Будут обновлены автоматически сформированные тексты приказа.",
  "",
  "Продолжить?",
].join("\n");

type Props = {
  orderId: number;
  order: Pick<PersonnelOrderHeader, "order_date" | "signed_by_name" | "signed_by_position">;
  items: PersonnelOrderItem[];
  /** Structured DRAFT write permission from order status. */
  editable: boolean;
  basisDocuments?: Array<{ basis_id?: unknown; document_type?: unknown; description?: unknown; source_text?: unknown }>;
  onOrderChanged?: (detail: PersonnelOrderDetailResponse) => void;
  onEditorialChanged?: (state: PersonnelOrderEditorialState) => void;
};

type BasisEntry = { document_type: string; basis_id: string; other_text: string };

const BASIS_EDITOR_LABELS = {
  ru: { basis: "Основание", imported: "Импортированный текст", kind: "Вид основания", empty: "Не выбрано", application: "Заявление работника", other: "Другое", add: "Добавить основание", manual: "Ручная корректировка", linked: "Связанный документ", save: "Сохранить", cancel: "Отмена", edit: "Редактировать", memo: "Служебная записка", report: "Докладная записка" },
  kk: { basis: "Негіз", imported: "Импортталған мәтін", kind: "Негіз түрі", empty: "Таңдалмаған", application: "Қызметкердің өтініші", other: "Басқа", add: "Негіз қосу", manual: "Қолмен түзету", linked: "Байланысты құжат", save: "Сақтау", cancel: "Болдырмау", edit: "Өңдеу", memo: "Қызметтік хат", report: "Баяндау хат" },
} as const;

function basisEntriesForItem(item: PersonnelOrderItem, documents: Props["basisDocuments"]): BasisEntry[] {
  const payload = item.payload || {};
  const stored = Array.isArray(payload.basis_entries) ? payload.basis_entries : [];
  const entries = stored
    .filter((entry): entry is Record<string, unknown> => Boolean(entry) && typeof entry === "object")
    .map((entry) => ({ document_type: String(entry.document_type || ""), basis_id: String(entry.basis_id || ""), other_text: String(entry.other_text || "") }));
  if (entries.length) return entries;
  const ids = Array.isArray(payload.basis_ids) ? payload.basis_ids.filter((id): id is string => typeof id === "string") : [];
  const derived = ids.map((basisId) => ({
    basis_id: basisId,
    document_type: String(documents?.find((document) => document.basis_id === basisId)?.document_type || ""),
    other_text: "",
  }));
  const manual = typeof payload.basis_other_text === "string" ? payload.basis_other_text : "";
  if (manual) derived.push({ document_type: "OTHER", basis_id: "", other_text: manual });
  return derived;
}

function basisTypeLabel(type: string, locale: PersonnelOrderEditorialUiLocale): string {
  const labels = BASIS_EDITOR_LABELS[locale];
  return ({ EMPLOYEE_APPLICATION: labels.application, SERVICE_MEMO: labels.memo, REPORT_MEMO: labels.report } as Record<string, string>)[type] || type;
}

function StructuredBasisBlockEditor({ item, block, editable, documents = [], onChanged, locale }: { item: PersonnelOrderItem; block: PersonnelOrderEditorialBlock | null; editable: boolean; documents?: Props["basisDocuments"]; onChanged?: Props["onOrderChanged"]; locale: PersonnelOrderEditorialUiLocale }) {
  const [editing, setEditing] = React.useState(false);
  const [entries, setEntries] = React.useState<BasisEntry[]>(() => basisEntriesForItem(item, documents));
  const [manualCorrection, setManualCorrection] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const imported = documents.find((document) => typeof document.basis_id === "string" && (item.payload?.basis_ids as unknown[] || []).includes(document.basis_id));
  const types = Array.from(new Set(documents.map((document) => String(document.document_type || "")).filter(Boolean)));
  const ui = BASIS_EDITOR_LABELS[locale];
  React.useEffect(() => { if (!editing) setEntries(basisEntriesForItem(item, documents)); }, [item, documents, editing]);
  const update = (index: number, next: Partial<BasisEntry>) => setEntries((previous) => previous.map((entry, entryIndex) => entryIndex === index ? { ...entry, ...next } : entry));
  async function save() {
    setSaving(true);
    try {
      const valid = entries.filter((entry) => entry.document_type && (entry.basis_id || (entry.document_type === "OTHER" && entry.other_text.trim())));
      const linkedIds = valid.map((entry) => entry.basis_id).filter(Boolean);
      const otherText = valid.filter((entry) => entry.document_type === "OTHER").map((entry) => entry.other_text.trim()).filter(Boolean).join("\n");
      const payload = { ...(item.payload || {}), basis_entries: valid, basis_ids: linkedIds, ...(otherText ? { basis_other_text: otherText } : {}) };
      const detail = await updatePersonnelOrderItem(item.order_id, item.item_id, { item_type_code: item.item_type_code, employee_id: item.employee_id ?? null, effective_date: item.effective_date ?? null, period_start: item.period_start ?? null, period_end: item.period_end ?? null, item_number: item.item_number, payload });
      onChanged?.(detail);
      setEditing(false);
    } finally { setSaving(false); }
  }
  if (!editing) return <div className="space-y-2" data-testid="personnel-order-editorial-basis-block"><h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{ui.basis}</h4><div className="min-h-[2.5rem] whitespace-pre-wrap rounded-lg border border-zinc-200 bg-zinc-50/80 px-3 py-2 text-sm leading-relaxed text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-200">{displayPersonnelOrderEditorialBlockText(block).trim() || "—"}</div>{editable ? <button type="button" onClick={() => setEditing(true)} className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700" data-testid="personnel-order-editorial-basis-edit">{ui.edit}</button> : null}</div>;
  return <div className="space-y-3" data-testid="personnel-order-editorial-basis-editor"><h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{ui.basis}</h4>{typeof imported?.source_text === "string" ? <p className="text-xs text-zinc-500">{ui.imported}: {imported.source_text}</p> : null}{entries.map((entry, index) => <div key={index} className="grid gap-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800"><label className="text-sm">{ui.kind}<select value={entry.document_type} onChange={(e) => update(index, { document_type: e.target.value, basis_id: "", other_text: "" })} className="mt-1 w-full rounded border p-2"><option value="">{ui.empty}</option>{types.map((type) => <option key={type} value={type}>{basisTypeLabel(type, locale)}</option>)}<option value="OTHER">{ui.other}</option></select></label>{entry.document_type && entry.document_type !== "OTHER" ? <label className="text-sm">{ui.linked}<select value={entry.basis_id} onChange={(e) => update(index, { basis_id: e.target.value })} className="mt-1 w-full rounded border p-2"><option value="">{ui.empty}</option>{documents.filter((document) => document.document_type === entry.document_type && typeof document.basis_id === "string").map((document) => <option key={String(document.basis_id)} value={String(document.basis_id)}>{String((document.description as Record<string, unknown> | undefined)?.[locale] || (document.description as Record<string, unknown> | undefined)?.ru || (document.description as Record<string, unknown> | undefined)?.kk || document.basis_id)}</option>)}</select></label> : null}{(entry.document_type === "OTHER" || manualCorrection) ? <label className="text-sm">{ui.basis}<textarea value={entry.other_text} onChange={(e) => update(index, { other_text: e.target.value })} className="mt-1 w-full rounded border p-2" /></label> : null}</div>)}<div className="flex flex-wrap gap-2"><button type="button" onClick={() => setEntries((previous) => [...previous, { document_type: "", basis_id: "", other_text: "" }])} className="rounded border px-3 py-1.5 text-sm">{ui.add}</button><button type="button" onClick={() => setManualCorrection((value) => !value)} className="rounded border px-3 py-1.5 text-sm">{ui.manual}</button><button type="button" onClick={() => void save()} disabled={saving} className="rounded bg-zinc-900 px-3 py-1.5 text-sm text-white">{saving ? `${ui.save}…` : ui.save}</button><button type="button" onClick={() => setEditing(false)} className="rounded border px-3 py-1.5 text-sm">{ui.cancel}</button></div></div>;
}

function PositionTextOverrideEditor({ item, editable, onChanged }: { item: PersonnelOrderItem; editable: boolean; onChanged?: Props["onOrderChanged"] }) {
  const stored = (item.payload?.position_text_override || {}) as Record<string, unknown>;
  const [ru, setRu] = React.useState(String(stored.ru || ""));
  const [kk, setKk] = React.useState(String(stored.kk || ""));
  const [saving, setSaving] = React.useState(false);
  React.useEffect(() => { setRu(String(stored.ru || "")); setKk(String(stored.kk || "")); }, [item.item_id, stored.ru, stored.kk]);
  if (!editable) return null;
  async function save() {
    setSaving(true);
    try {
      const payload = { ...(item.payload || {}), position_text_override: { ru: ru.trim(), kk: kk.trim() } };
      const detail = await updatePersonnelOrderItem(item.order_id, item.item_id, {
        item_type_code: item.item_type_code, employee_id: item.employee_id ?? null,
        effective_date: item.effective_date ?? null, period_start: item.period_start ?? null,
        period_end: item.period_end ?? null, item_number: item.item_number, payload,
      });
      onChanged?.(detail);
    } finally { setSaving(false); }
  }
  return <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800" data-testid="personnel-order-position-text-override">
    <p className="text-sm font-semibold">Название должности в тексте приказа</p>
    <label className="mt-2 block text-sm">Русский<input list={`personnel-position-ru-options-${item.item_id}`} value={ru} onChange={(event) => setRu(event.target.value)} className="mt-1 w-full rounded border p-2" /></label>
    <datalist id={`personnel-position-ru-options-${item.item_id}`}><option value="медицинская сестра" /><option value="медицинский брат" /><option value="Другое" /></datalist>
    <label className="mt-2 block text-sm">Қазақша<input value={kk} onChange={(event) => setKk(event.target.value)} className="mt-1 w-full rounded border p-2" /></label>
    <button type="button" onClick={() => void save()} disabled={saving} className="mt-3 rounded border px-3 py-1.5 text-sm">{saving ? "Сохранение…" : "Сохранить"}</button>
  </div>;
}

function StatusBadge({ status }: { status: PersonnelOrderEditorialUiStatus }) {
  const label = PERSONNEL_ORDER_EDITORIAL_UI_STATUS_LABELS[status];
  const tone =
    status === "requires_review"
      ? "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-100"
      : status === "edited"
        ? "border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-900/60 dark:bg-sky-950/40 dark:text-sky-100"
        : "border-zinc-200 bg-zinc-50 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300";
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${tone}`}
      data-testid="personnel-order-editorial-status"
      data-status={status}
    >
      {label}
    </span>
  );
}

function BlockEditor({
  label,
  block,
  editable,
  busy,
  onSave,
  onReset,
}: {
  label: string;
  block: PersonnelOrderEditorialBlock | null;
  editable: boolean;
  busy: boolean;
  onSave: (blockId: number, text: string, revision: number) => Promise<void>;
  onReset: (blockId: number) => Promise<void>;
}) {
  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState("");
  const [localError, setLocalError] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);

  const displayText = displayPersonnelOrderEditorialBlockText(block);
  const status = resolvePersonnelOrderEditorialUiStatus(block);
  const canEdit = editable && Boolean(block) && !busy;
  const hasOverride = Boolean(String(block?.override_text ?? "").trim());

  React.useEffect(() => {
    if (!editing) {
      setDraft(displayText);
      setLocalError(null);
    }
  }, [displayText, editing, block?.block_id, block?.revision]);

  async function handleSave() {
    if (!block || !canEdit) return;
    setSaving(true);
    setLocalError(null);
    try {
      await onSave(block.block_id, draft, block.revision);
      setEditing(false);
    } catch (err) {
      const raw = mapPersonnelOrdersApiError(err, "Не удалось сохранить текст.");
      setLocalError(mapEditorialConflictMessage(raw));
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    if (!block || !canEdit) return;
    const confirmed = window.confirm(
      "Вернуть автоматически сформированный текст? Ручные правки этого блока будут удалены.",
    );
    if (!confirmed) return;
    setSaving(true);
    setLocalError(null);
    try {
      await onReset(block.block_id);
      setEditing(false);
    } catch (err) {
      setLocalError(mapPersonnelOrdersApiError(err, "Не удалось вернуть текст."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-2" data-testid={`personnel-order-editorial-block-${label}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{label}</h4>
        <StatusBadge status={status} />
      </div>

      {!block ? (
        <p className="text-sm text-zinc-500">Текст ещё не сформирован.</p>
      ) : editing ? (
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={label === "Заголовок" ? 2 : 5}
          disabled={saving || busy}
          className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm leading-relaxed text-zinc-900 disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
          data-testid="personnel-order-editorial-textarea"
          spellCheck
        />
      ) : (
        <div
          className="min-h-[2.5rem] whitespace-pre-wrap rounded-lg border border-zinc-200 bg-zinc-50/80 px-3 py-2 text-sm leading-relaxed text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-200"
          data-testid="personnel-order-editorial-readonly"
        >
          {displayText.trim() ? displayText : "—"}
        </div>
      )}

      {localError ? (
        <p className="text-sm text-red-700 dark:text-red-300" role="alert">
          {localError}
        </p>
      ) : null}

      {canEdit ? (
        <div className="flex flex-wrap gap-2">
          {!editing ? (
            <button
              type="button"
              onClick={() => {
                setDraft(displayText);
                setEditing(true);
                setLocalError(null);
              }}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
              data-testid="personnel-order-editorial-edit"
            >
              Редактировать
            </button>
          ) : (
            <>
              <button
                type="button"
                onClick={() => void handleSave()}
                disabled={saving}
                className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
                data-testid="personnel-order-editorial-save"
              >
                {saving ? "Сохранение…" : "Сохранить"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setEditing(false);
                  setDraft(displayText);
                  setLocalError(null);
                }}
                disabled={saving}
                className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm disabled:opacity-60 dark:border-zinc-700"
              >
                Отмена
              </button>
            </>
          )}
          <button
            type="button"
            onClick={() => void handleReset()}
            disabled={saving || !hasOverride}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm disabled:opacity-40 dark:border-zinc-700"
            data-testid="personnel-order-editorial-reset"
            title={hasOverride ? undefined : "Нет ручных правок для этого блока"}
          >
            Вернуть автоматически сгенерированный текст
          </button>
        </div>
      ) : null}
    </div>
  );
}

export default function PersonnelOrderEditorialTextEditor({
  orderId,
  order,
  items,
  editable,
  basisDocuments = [],
  onOrderChanged,
  onEditorialChanged,
}: Props) {
  const [state, setState] = React.useState<PersonnelOrderEditorialState | null>(null);
  const [activeLocale, setActiveLocale] = React.useState<PersonnelOrderEditorialUiLocale>("kk");
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [message, setMessage] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let next = await getPersonnelOrderEditorial(orderId);
      if (editable && !hasRequiredEditorialLocales(next)) {
        // Full generate (kk + ru) so READY gate remains satisfiable.
        next = await generatePersonnelOrderEditorial(orderId);
      }
      setState(next);
      onEditorialChanged?.(next);
    } catch (err) {
      setState(null);
      setError(mapPersonnelOrdersApiError(err, "Не удалось загрузить текст приказа."));
    } finally {
      setLoading(false);
    }
  }, [orderId, editable, onEditorialChanged]);

  React.useEffect(() => {
    void load();
  }, [load]);

  const canWrite = editable && Boolean(state?.editable);

  async function handleGenerateAll() {
    if (!window.confirm(GENERATE_CONFIRM_MESSAGE)) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const next = await generatePersonnelOrderEditorial(orderId);
      setState(next);
      onEditorialChanged?.(next);
      setMessage("Текст приказа сформирован.");
    } catch (err) {
      setError(mapPersonnelOrdersApiError(err, "Не удалось сформировать текст приказа."));
    } finally {
      setBusy(false);
    }
  }

  async function handleSave(blockId: number, text: string, revision: number) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const next = await patchPersonnelOrderEditorialBlock(orderId, blockId, {
        override_text: text,
        expected_revision: revision,
      });
      setState(next);
      onEditorialChanged?.(next);
      setMessage("Текст сохранён.");
    } finally {
      setBusy(false);
    }
  }

  async function handleReset(blockId: number) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const next = await resetPersonnelOrderEditorialBlock(orderId, blockId);
      setState(next);
      onEditorialChanged?.(next);
      setMessage("Восстановлен автоматически сформированный текст.");
    } finally {
      setBusy(false);
    }
  }

  const sections = buildEditorialDocumentSections(state, items, activeLocale);

  return (
    <section data-testid="personnel-order-editorial-editor" className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Текст приказа</h3>
          <p className="mt-1 text-xs text-zinc-500">{editorialLocaleHint(activeLocale)}</p>
        </div>
        {canWrite ? (
          <button
            type="button"
            onClick={() => void handleGenerateAll()}
            disabled={busy || loading}
            className="rounded-lg bg-blue-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-blue-600 dark:hover:bg-blue-500"
            data-testid="personnel-order-editorial-generate"
          >
            {busy ? "Формирование…" : "Сформировать / обновить текст"}
          </button>
        ) : null}
      </div>

      <div
        className="flex flex-wrap gap-2"
        role="tablist"
        aria-label="Язык редакции приказа"
        data-testid="personnel-order-editorial-locale-tabs"
      >
        {PERSONNEL_ORDER_EDITORIAL_UI_LOCALES.map((locale) => {
          const selected = activeLocale === locale;
          return (
            <button
              key={locale}
              type="button"
              role="tab"
              aria-selected={selected}
              data-testid={`personnel-order-editorial-locale-${locale}`}
              onClick={() => setActiveLocale(locale)}
              className={
                selected
                  ? "rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
                  : "rounded-lg border border-zinc-300 px-3 py-1.5 text-sm text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
              }
            >
              {PERSONNEL_ORDER_EDITORIAL_LOCALE_LABELS[locale]}
            </button>
          );
        })}
      </div>

      {!editable ? (
        <p className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-300">
          Приказ доступен только для просмотра. Редактирование текста разрешено в статусе «Черновик».
        </p>
      ) : null}

      {loading ? <p className="text-sm text-zinc-500">Загрузка текста приказа…</p> : null}

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
          {error}
        </div>
      ) : null}

      {message ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900 dark:border-emerald-900/55 dark:bg-emerald-950/35 dark:text-emerald-100">
          {message}
        </div>
      ) : null}

      {!loading && !error ? (
        <div className="space-y-6">
          {sections.map((section) => {
            if (section.kind === "order") {
              const isClosing = section.blockType === "closing";
              return (
                <div
                  key={section.key}
                  className="border-t border-zinc-200 pt-4 first:border-t-0 first:pt-0 dark:border-zinc-800"
                >
                  <BlockEditor
                    label={section.title}
                    block={section.block}
                    editable={canWrite}
                    busy={busy}
                    onSave={handleSave}
                    onReset={handleReset}
                  />
                  {isClosing ? (
                    <div className="mt-4 space-y-2" data-testid="personnel-order-editorial-requisites">
                      <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                        Реквизиты документа
                      </h4>
                      <PersonnelOrderDocumentRequisitesPreview
                        key={`${order.order_date ?? ""}:${order.signed_by_position ?? ""}:${order.signed_by_name ?? ""}`}
                        order={order}
                        locale={activeLocale}
                      />
                    </div>
                  ) : null}
                </div>
              );
            }

            return (
              <div
                key={section.key}
                className="space-y-4 border-t border-zinc-200 pt-4 dark:border-zinc-800"
                data-testid={`personnel-order-editorial-item-${section.orderItemId}`}
              >
                <div>
                  <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                    Пункт №{section.itemNumber}
                  </h4>
                  {section.employeeName ? (
                    <p className="mt-0.5 text-xs text-zinc-500">{section.employeeName}</p>
                  ) : null}
                </div>
                <BlockEditor
                  label="Текст пункта"
                  block={section.body}
                  editable={canWrite}
                  busy={busy}
                  onSave={handleSave}
                  onReset={handleReset}
                />
                <PositionTextOverrideEditor item={items.find((item) => item.item_id === section.orderItemId)!} editable={canWrite} onChanged={onOrderChanged} />
                <StructuredBasisBlockEditor item={items.find((item) => item.item_id === section.orderItemId)!} block={section.basis} editable={canWrite} documents={basisDocuments} onChanged={onOrderChanged} locale={activeLocale} />
              </div>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
