"use client";

import * as React from "react";

import {
  generatePersonnelOrderEditorial,
  getPersonnelOrderEditorial,
  mapPersonnelOrdersApiError,
  patchPersonnelOrderEditorialBlock,
  resetPersonnelOrderEditorialBlock,
  type PersonnelOrderEditorialBlock,
  type PersonnelOrderEditorialState,
  type PersonnelOrderItem,
} from "../_lib/personnelOrdersApi.client";
import {
  PERSONNEL_ORDER_EDITORIAL_UI_STATUS_LABELS,
  buildEditorialDocumentSections,
  displayPersonnelOrderEditorialBlockText,
  hasEditorialUiLocaleBlocks,
  mapEditorialConflictMessage,
  resolvePersonnelOrderEditorialUiStatus,
  type PersonnelOrderEditorialUiStatus,
} from "../_lib/personnelOrderEditorialUi";

const GENERATE_CONFIRM_MESSAGE = [
  "Пересформировать текст приказа?",
  "",
  "Будут обновлены автоматически сформированные тексты приказа.",
  "",
  "Продолжить?",
].join("\n");

type Props = {
  orderId: number;
  items: PersonnelOrderItem[];
  /** Structured DRAFT write permission from order status. */
  editable: boolean;
};

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

export default function PersonnelOrderEditorialTextEditor({ orderId, items, editable }: Props) {
  const [state, setState] = React.useState<PersonnelOrderEditorialState | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [message, setMessage] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let next = await getPersonnelOrderEditorial(orderId);
      if (editable && !hasEditorialUiLocaleBlocks(next)) {
        // Full generate (kk + ru) so READY gate remains satisfiable; UI still shows kk only.
        next = await generatePersonnelOrderEditorial(orderId);
      }
      setState(next);
    } catch (err) {
      setState(null);
      setError(mapPersonnelOrdersApiError(err, "Не удалось загрузить текст приказа."));
    } finally {
      setLoading(false);
    }
  }, [orderId, editable]);

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
      setMessage("Восстановлен автоматически сформированный текст.");
    } finally {
      setBusy(false);
    }
  }

  const sections = buildEditorialDocumentSections(state, items);

  return (
    <section data-testid="personnel-order-editorial-editor" className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Текст приказа</h3>
          <p className="mt-1 text-xs text-zinc-500">
            Редактирование казахского текста приказа. Русский язык будет доступен на следующем
            этапе.
          </p>
        </div>
        {canWrite ? (
          <button
            type="button"
            onClick={() => void handleGenerateAll()}
            disabled={busy || loading}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm disabled:opacity-60 dark:border-zinc-700"
            data-testid="personnel-order-editorial-generate"
          >
            {busy ? "Формирование…" : "Сформировать / обновить текст"}
          </button>
        ) : null}
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
                <BlockEditor
                  label="Основание"
                  block={section.basis}
                  editable={canWrite}
                  busy={busy}
                  onSave={handleSave}
                  onReset={handleReset}
                />
              </div>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
