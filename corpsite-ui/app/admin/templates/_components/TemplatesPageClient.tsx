"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import RegularTasksAdminClient from "@/app/regular-tasks/_components/RegularTasksAdminClient";
import { blankPersonnelOrderAcknowledgementFooter } from "@/app/directory/personnel/_lib/personnelOrderPrintLocale";

import {
  buildTemplateSectionHref,
  resolveTemplateSection,
  TEMPLATE_SECTIONS,
  type TemplateSection,
} from "../_lib/templateSections";
import {
  listPersonnelOrderTemplateCatalog,
  type PersonnelOrderTemplateCatalogItem,
  type PersonnelOrderTemplatePilotDetail,
  type PersonnelOrderTemplatePreview,
  type PersonnelOrderTemplateDraft,
  type PersonnelOrderTemplateDraftText,
  createPersonnelOrderTemplateDraft,
  getPersonnelOrderTemplateDraft,
  getPersonnelOrderTemplatePublished,
  getPersonnelOrderTemplateEditorBase,
  previewPersonnelOrderTemplateDraft,
  savePersonnelOrderTemplateDraft,
  publishPersonnelOrderTemplateDraft,
} from "../_lib/personnelOrderTemplatesApi.client";

const TAB_CLASS = "rounded-xl border px-4 py-2 text-sm font-medium transition";
const DRAFT_HEIGHT_STORAGE_PREFIX = "corpsite.personnel-order-template-draft-heights.v1";
const TEXTAREA_MIN_HEIGHT = 64;
const TEXTAREA_MAX_HEIGHT = 640;

type DraftHeightPair = "title" | "preamble" | "body_template" | "basis_template";

const DRAFT_HEIGHT_FIELDS: Array<{
  pair: DraftHeightPair;
  ru: [keyof PersonnelOrderTemplateDraftText, string];
  kk: [keyof PersonnelOrderTemplateDraftText, string];
  heightClass: string;
}> = [
  { pair: "title", ru: ["title_ru", "Заголовок RU"], kk: ["title_kk", "Заголовок KK"], heightClass: "h-16" },
  { pair: "preamble", ru: ["preamble_ru", "Преамбула RU"], kk: ["preamble_kk", "Преамбула KK"], heightClass: "h-28" },
  { pair: "body_template", ru: ["body_template_ru", "Распорядительный текст RU"], kk: ["body_template_kk", "Распорядительный текст KK"], heightClass: "h-48" },
  { pair: "basis_template", ru: ["basis_template_ru", "Основание RU"], kk: ["basis_template_kk", "Основание KK"], heightClass: "h-28" },
];

function draftHeightStorageKey(itemTypeCode: string): string {
  return `${DRAFT_HEIGHT_STORAGE_PREFIX}:${itemTypeCode}`;
}

function clampTextareaHeight(value: number): number | null {
  if (!Number.isFinite(value) || value <= 0) return null;
  return Math.max(TEXTAREA_MIN_HEIGHT, Math.min(TEXTAREA_MAX_HEIGHT, Math.round(value)));
}

function readDraftHeights(itemTypeCode: string): Partial<Record<DraftHeightPair, number>> {
  try {
    const raw = window.localStorage.getItem(draftHeightStorageKey(itemTypeCode));
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return {};
    return Object.fromEntries(DRAFT_HEIGHT_FIELDS.flatMap(({ pair }) => {
      const height = clampTextareaHeight((parsed as Record<string, unknown>)[pair] as number);
      return height == null ? [] : [[pair, height]];
    })) as Partial<Record<DraftHeightPair, number>>;
  } catch {
    return {};
  }
}

function writeDraftHeights(itemTypeCode: string, heights: Partial<Record<DraftHeightPair, number>>): void {
  try {
    window.localStorage.setItem(draftHeightStorageKey(itemTypeCode), JSON.stringify(heights));
  } catch {
    // Layout preferences must never prevent editing a DRAFT.
  }
}

function draftErrorMessage(cause: unknown): string {
  const error = cause as { message?: unknown; details?: { detail?: unknown } };
  const validation = Array.isArray(error?.details?.detail) ? error.details.detail[0] as { loc?: unknown; msg?: unknown } : null;
  if (validation) {
    const location = Array.isArray(validation.loc) ? validation.loc.filter((part) => part !== "body").join(".") : "";
    const message = typeof validation.msg === "string" ? validation.msg : "Некорректное значение";
    return location ? `Поле «${location}»: ${message}` : message;
  }
  return typeof error?.message === "string" && error.message.trim() ? error.message : "Не удалось выполнить действие.";
}

function GeneralPersonnelOrderRequirements() {
  return (
    <section className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40" data-testid="personnel-order-common-requirements">
      <h3 className="font-semibold">Общие требования к кадровым приказам</h3>
      <ul className="mt-3 grid list-disc gap-x-8 gap-y-1 pl-5 text-sm md:grid-cols-2">
        <li>Документ поддерживает RU и KK.</li>
        <li>Заголовок и преамбула.</li>
        <li>Отдельная центрированная строка ПРИКАЗЫВАЮ: / БҰЙЫРАМЫН:.</li>
        <li>Распорядительная часть.</li>
        <li>Основание выводится один раз.</li>
        <li>Печатный подвал.</li>
        <li>Ознакомление сотрудника.</li>
        <li>Фактическая дата ознакомления либо место для её заполнения.</li>
        <li>Исполнитель приказа.</li>
      </ul>
    </section>
  );
}

function PreviewFooter({ locale }: { locale: "ru" | "kk" }) {
  const footer = blankPersonnelOrderAcknowledgementFooter(locale);
  return (
    <div className="mt-5 whitespace-pre-line border-t border-zinc-200 pt-3 text-sm dark:border-zinc-800">
      <p>{footer.familiarization} ___________________ {footer.namePlaceholder}</p>
      <p>{footer.date}</p>
      <p>{footer.executor}</p>
    </div>
  );
}

function editableDraftText(source: PersonnelOrderTemplateDraftText): PersonnelOrderTemplateDraftText {
  return {
    title_ru: source.title_ru,
    title_kk: source.title_kk,
    preamble_ru: source.preamble_ru,
    preamble_kk: source.preamble_kk,
    body_template_ru: source.body_template_ru,
    body_template_kk: source.body_template_kk,
    basis_template_ru: source.basis_template_ru,
    basis_template_kk: source.basis_template_kk,
  };
}

function FormalizedTemplateDetail({ detail, showCatalogPreview }: { detail: PersonnelOrderTemplatePilotDetail; showCatalogPreview: boolean }) {
  return (
    <div className="mt-5 space-y-4" data-testid="formalized-template-detail">
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
          <h4 className="font-semibold">Реквизиты этого шаблона</h4>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
            {detail.required_fields.map((field) => <li key={field}>{field}</li>)}
          </ul>
          {detail.additional_fields.length > 0 ? (
            <>
              <h5 className="mt-4 font-medium">Дополнительные реквизиты</h5>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                {detail.additional_fields.map((field) => <li key={field}>{field}</li>)}
              </ul>
            </>
          ) : null}
        </section>

        <section className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
          <h4 className="font-semibold">Переменные шаблона</h4>
          <dl className="mt-3 space-y-1 text-sm">
            {detail.variables.map((variable) => (
              <div key={variable.code} className="flex flex-wrap items-baseline gap-x-1 leading-5">
                <dt className="font-mono text-xs text-zinc-700 dark:text-zinc-300">{variable.code}:</dt>
                {" "}
                <dd className="text-zinc-600 dark:text-zinc-400">{variable.label}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-sm text-zinc-600 dark:text-zinc-400">{detail.specialty_note}</p>
        </section>
      </div>

      {showCatalogPreview ? <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800" aria-labelledby="pilot-preview-heading">
        <h4 id="pilot-preview-heading" className="font-semibold">Предварительный просмотр</h4>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Нейтральный пример без персональных данных.</p>
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          {(["ru", "kk"] as const).map((locale) => {
            const preview = detail.previews[locale];
            return (
              <article key={locale} data-testid={`pilot-preview-${locale}`} className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
                <h5 className="font-semibold">{locale === "ru" ? "Русский" : "Қазақша"}</h5>
                <p className="mt-3 font-medium">{preview.title}</p>
                <p className="mt-3 text-sm">{preview.preamble}</p>
                <p className="my-5 text-center font-semibold tracking-wide">{preview.directive}</p>
                <p className="text-sm">{preview.body}</p>
                <p className="mt-3 text-sm">{preview.basis}</p>
                <PreviewFooter locale={locale} />
              </article>
            );
          })}
        </div>
      </section> : null}
    </div>
  );
}

function DraftEditor({ draft, onSaved, onPublished, variables, warning }: { draft: PersonnelOrderTemplateDraft; onSaved: (draft: PersonnelOrderTemplateDraft) => void; onPublished: (draft: PersonnelOrderTemplateDraft) => void; variables: string[]; warning?: string }) {
  const [savedDraft, setSavedDraft] = useState(draft);
  const [values, setValues] = useState<PersonnelOrderTemplateDraftText>(() => editableDraftText(draft));
  const [preview, setPreview] = useState<Record<"ru" | "kk", PersonnelOrderTemplatePreview> | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const editorRef = useRef<HTMLElement | null>(null);
  const previewRef = useRef<HTMLDivElement | null>(null);
  const previewRequest = useRef(0);
  const ruTextareas = useRef<Partial<Record<keyof PersonnelOrderTemplateDraftText, HTMLTextAreaElement | null>>>({});
  const kkTextareas = useRef<Partial<Record<keyof PersonnelOrderTemplateDraftText, HTMLTextAreaElement | null>>>({});
  useEffect(() => { setSavedDraft(draft); }, [draft]);
  useEffect(() => { if (preview) previewRef.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" }); }, [preview]);
  const setPairHeight = useCallback((pair: DraftHeightPair, rawHeight: number, persist: boolean) => {
    const height = clampTextareaHeight(rawHeight);
    if (height == null) return;
    const field = DRAFT_HEIGHT_FIELDS.find((entry) => entry.pair === pair);
    if (!field) return;
    const value = `${height}px`;
    const ruTextarea = ruTextareas.current[field.ru[0]];
    const kkTextarea = kkTextareas.current[field.kk[0]];
    if (ruTextarea) ruTextarea.style.height = value;
    if (kkTextarea) kkTextarea.style.height = value;
    if (persist) writeDraftHeights(savedDraft.item_type_code, { ...readDraftHeights(savedDraft.item_type_code), [pair]: height });
  }, [savedDraft.item_type_code]);
  useEffect(() => {
    const heights = readDraftHeights(savedDraft.item_type_code);
    DRAFT_HEIGHT_FIELDS.forEach(({ pair }) => {
      const height = heights[pair];
      if (height != null) setPairHeight(pair, height, false);
    });
  }, [savedDraft.item_type_code, setPairHeight]);
  useEffect(() => {
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      entries.forEach(({ target }) => {
        const pair = target.getAttribute("data-height-pair") as DraftHeightPair | null;
        const height = target.getBoundingClientRect().height;
        if (pair) setPairHeight(pair, height, true);
      });
    });
    editorRef.current?.querySelectorAll<HTMLTextAreaElement>("[data-height-pair]").forEach((textarea) => observer.observe(textarea));
    return () => observer.disconnect();
  }, [setPairHeight]);
  const resetHeights = () => {
    try { window.localStorage.removeItem(draftHeightStorageKey(savedDraft.item_type_code)); } catch { /* no-op */ }
    DRAFT_HEIGHT_FIELDS.forEach(({ ru, kk }) => {
      if (ruTextareas.current[ru[0]]) ruTextareas.current[ru[0]]!.style.height = "";
      if (kkTextareas.current[kk[0]]) kkTextareas.current[kk[0]]!.style.height = "";
    });
  };
  const change = (key: keyof PersonnelOrderTemplateDraftText, value: string) => {
    previewRequest.current += 1;
    setValues((old) => ({ ...old, [key]: value }));
    setPreview(null);
    setError("");
    setNotice("");
  };
  const isWorkingCopy = savedDraft.status === "WORKING_COPY";
  const isDirty = DRAFT_HEIGHT_FIELDS.some(({ ru, kk }) => values[ru[0]] !== savedDraft[ru[0]] || values[kk[0]] !== savedDraft[kk[0]]);
  const showPreview = () => {
    const request = ++previewRequest.current;
    const submittedValues = editableDraftText(values);
    setError("");
    setNotice("");
    setPreview(null);
    setPreviewing(true);
    void previewPersonnelOrderTemplateDraft(savedDraft.item_type_code, submittedValues)
      .then((result) => { if (request === previewRequest.current) setPreview(result.previews); })
      .catch((cause) => {
        if (request !== previewRequest.current) return;
        setPreview(null);
        setError(draftErrorMessage(cause));
      })
      .finally(() => { if (request === previewRequest.current) setPreviewing(false); });
  };
  const save = () => {
    const submittedValues = editableDraftText(values);
    setError("");
    setNotice("");
    setSaving(true);
    const persist = isWorkingCopy
      ? createPersonnelOrderTemplateDraft(savedDraft.item_type_code, { ...submittedValues, base_source: (savedDraft as PersonnelOrderTemplateDraft & { base_source?: "PUBLISHED" | "INITIAL" }).base_source ?? "PUBLISHED", ...((savedDraft as PersonnelOrderTemplateDraft & { base_source?: string }).base_source === "INITIAL" ? {} : { base_published_template_version_id: savedDraft.template_version_id, base_published_revision: savedDraft.revision }) })
      : savePersonnelOrderTemplateDraft(savedDraft.item_type_code, { ...submittedValues, expected_revision: savedDraft.revision });
    void persist
      .then((next) => {
        const savedValues = editableDraftText(next);
        setSavedDraft(next);
        onSaved(next);
        setValues(savedValues);
        setNotice("Черновик сохранён");
        const request = ++previewRequest.current;
        return previewPersonnelOrderTemplateDraft(next.item_type_code, savedValues)
          .then((result) => { if (request === previewRequest.current) setPreview(result.previews); })
          .catch(() => {
            if (request !== previewRequest.current) return;
            setPreview(null);
            setError("Черновик сохранён, но не удалось обновить предварительный просмотр.");
          });
      })
      .catch((cause) => {
        previewRequest.current += 1;
        setPreview(null);
        setError(draftErrorMessage(cause));
      })
      .finally(() => setSaving(false));
  };
  const reloadCurrentDraft = () => {
    setReloading(true);
    setError("");
    setNotice("");
    void getPersonnelOrderTemplateDraft(savedDraft.item_type_code)
      .then((next) => {
        if (!next) throw new Error("Актуальная черновая версия не найдена.");
        const reloadedValues = editableDraftText(next);
        setSavedDraft(next);
        onSaved(next);
        setValues(reloadedValues);
        setPreview(null);
        setNotice("Загружена актуальная версия черновика.");
      })
      .catch((cause) => setError(draftErrorMessage(cause)))
      .finally(() => setReloading(false));
  };
  const publish = () => {
    if (!window.confirm("Опубликовать эту версию шаблона?")) return;
    setPublishing(true); setError("");
    void publishPersonnelOrderTemplateDraft(savedDraft.item_type_code, savedDraft.revision)
      // Publishing returns an immutable snapshot, never the next editable
      // draft.  Let the parent replace and close the editor atomically.
      .then((next) => { onPublished(next); })
      .catch((cause) => setError(draftErrorMessage(cause))).finally(() => setPublishing(false));
  };
  return (
    <section ref={editorRef} className="mt-5 rounded-xl border border-blue-200 p-4" data-testid="template-draft-editor">
      <h4 className="font-semibold">{isWorkingCopy ? "Несохранённая рабочая копия опубликованной версии" : "Черновая версия шаблона"}</h4>
      <p className="text-sm">Версия {savedDraft.version_number} · revision {savedDraft.revision} · {savedDraft.status}</p>
      <p className="mt-2 text-sm text-amber-700">Черновик не применяется к кадровым приказам.</p>
      {warning ? <p className="mt-2 text-sm font-medium text-amber-700" role="note">{warning}</p> : null}

      <div className="mt-3 grid grid-cols-1 gap-x-4 gap-y-3 md:grid-cols-2" data-testid="template-draft-fields">
        <h5 className="text-base font-semibold" data-testid="template-draft-language-ru">Русский</h5>
        <h5 className="text-base font-semibold" data-testid="template-draft-language-kk">Қазақша</h5>
        {DRAFT_HEIGHT_FIELDS.flatMap(({ pair, ru, kk, heightClass }) => [
          <label key={ru[0]} className="min-w-0 text-sm" data-testid={`template-draft-field-${ru[0]}`}>
            {ru[1]}
            <textarea
              aria-label={ru[1]}
              data-height-pair={pair}
              ref={(node) => { ruTextareas.current[ru[0]] = node; }}
              value={values[ru[0]]}
              onChange={(e) => change(ru[0], e.target.value)} disabled={savedDraft.status !== "DRAFT" && !isWorkingCopy}
              className={`mt-1 w-full resize-y rounded border p-2 ${heightClass}`}
              style={{ minHeight: TEXTAREA_MIN_HEIGHT, maxHeight: TEXTAREA_MAX_HEIGHT }}
            />
          </label>,
          <label key={kk[0]} className="min-w-0 text-sm" data-testid={`template-draft-field-${kk[0]}`}>
            {kk[1]}
            <textarea
              aria-label={kk[1]}
              ref={(node) => { kkTextareas.current[kk[0]] = node; }}
              value={values[kk[0]]}
              onChange={(e) => change(kk[0], e.target.value)} disabled={savedDraft.status !== "DRAFT" && !isWorkingCopy}
              className={`mt-1 w-full resize-none rounded border p-2 ${heightClass}`}
              style={{ minHeight: TEXTAREA_MIN_HEIGHT, maxHeight: TEXTAREA_MAX_HEIGHT }}
            />
          </label>,
        ])}
      </div>

      <p className="mt-3 text-xs">Разрешённые переменные: {variables.join(", ")}.</p>
      <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-zinc-200 pt-3 dark:border-zinc-800" data-testid="template-draft-actions">
        <button type="button" onClick={showPreview} disabled={previewing || (savedDraft.status !== "DRAFT" && !isWorkingCopy)} className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-800 transition hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800">{previewing ? "Формирование…" : "Предварительный просмотр"}</button>
        <button type="button" onClick={save} disabled={saving || (isWorkingCopy && !isDirty) || (savedDraft.status !== "DRAFT" && !isWorkingCopy)} className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-blue-500 dark:text-zinc-950 dark:hover:bg-blue-400">{saving ? "Сохранение…" : "Сохранить черновик"}</button>
        <button type="button" onClick={publish} disabled={publishing || isDirty || savedDraft.status !== "DRAFT"} className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{publishing ? "Публикация…" : "Опубликовать версию"}</button>
        <button type="button" onClick={resetHeights} className="rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800">Сбросить высоту полей</button>
        {error ? <button type="button" onClick={reloadCurrentDraft} disabled={reloading} className="rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60">{reloading ? "Загрузка…" : "Загрузить актуальную версию"}</button> : null}
        {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
        {notice ? <p role="status" className="text-sm text-emerald-700">{notice}</p> : null}
      </div>
      {preview ? <div ref={previewRef} data-testid="template-draft-preview" className="mt-4 grid gap-3 md:grid-cols-2">{(["ru", "kk"] as const).map((locale) => <article key={locale}><b>{locale.toUpperCase()}</b><p>{preview[locale].title}</p><p>{preview[locale].preamble}</p><p className="text-center">{preview[locale].directive}</p><p>{preview[locale].body}</p><p>{preview[locale].basis}</p><PreviewFooter locale={locale} /></article>)}</div> : null}
    </section>
  );
}

function TemplateDetail({ item }: { item: PersonnelOrderTemplateCatalogItem }) {
  const detail = item.template_detail ?? item.pilot_detail;
  const [draft, setDraft] = useState<PersonnelOrderTemplateDraft | null>(null);
  const [published, setPublished] = useState<PersonnelOrderTemplateDraft | null>(null);
  const [draftExists, setDraftExists] = useState(false);
  const [openingEditor, setOpeningEditor] = useState(false);
  const openRequest = useRef(0);
  const openEditor = useCallback((userInitiated = false) => {
    // Creation of a DRAFT is deliberately reachable only from an explicit
    // button click.  Effects and publish callbacks may refresh read-only data,
    // but cannot turn a page load into a write.
    if (!userInitiated) return;
    const request = ++openRequest.current;
    setDraft(null);
    setOpeningEditor(true);
    void getPersonnelOrderTemplateDraft(item.type_code)
      .then((existing) => {
        if (existing) return existing;
        return getPersonnelOrderTemplateEditorBase(item.type_code).then((base) => ({ ...base, template_version_id: base.template_version_id ?? 0, version_number: base.version_number ?? 0, revision: base.revision ?? 0, based_on_built_in: base.source === "INITIAL", status: "WORKING_COPY", base_source: base.source } as unknown as PersonnelOrderTemplateDraft));
      })
      .then((next) => { if (request === openRequest.current) { setDraft(next); setDraftExists(true); } })
      .catch(() => { /* The page remains read-only until a published snapshot is available. */ })
      .finally(() => { if (request === openRequest.current) setOpeningEditor(false); });
  }, [item.type_code, published]);
  useEffect(() => {
    let active = true;
    setDraft(null); setDraftExists(false); setPublished(null);
    if (!item.editor_available) return () => { active = false; };
    void getPersonnelOrderTemplatePublished(item.type_code)
      .then(async (nextPublished) => {
        const nextDraft = nextPublished ? await getPersonnelOrderTemplateDraft(item.type_code) : null;
        return [nextPublished, nextDraft] as const;
      })
      .then(([nextPublished, nextDraft]) => {
        if (!active) return;
        setPublished(nextPublished);
        setDraftExists(Boolean(nextDraft));
      })
      .catch(() => { if (active) { setPublished(null); setDraftExists(false); } });
    return () => { active = false; };
  }, [item.type_code, item.editor_available]);
  useEffect(() => () => { openRequest.current += 1; }, []);
  return (
    <aside data-testid="personnel-order-template-detail" className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="text-lg font-semibold">{item.title_ru}</h3>
      <p className="mt-1">{item.title_kk}</p>
      <p className="mt-2 text-sm">{item.type_code} · {item.support_level}</p>
      {published ? <section className="mt-4 rounded-lg border border-emerald-200 p-3" data-testid="template-published-read-only"><h4 className="font-semibold">Опубликованная версия шаблона</h4><p className="text-sm">Версия {published.version_number} · {published.status}</p><p className="mt-2 whitespace-pre-wrap text-sm">{published.title_ru}</p>{draftExists ? <p className="mt-2 text-sm text-amber-700">Имеется черновик следующей версии.</p> : null}</section> : null}
      <p className="mt-1 text-sm">{item.uses_specialized_generator ? "Специализированный генератор" : "Общий fallback"}</p>
      {detail ? <FormalizedTemplateDetail detail={detail} showCatalogPreview={!item.editor_available} /> : <>
        <p className="mt-3">Обязательные поля: {item.required_fields.join(", ") || "не формализованы"}</p>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{item.notes}</p>
      </>}
      {item.editor_available && !draft ? <div className="mt-4"><button aria-label={openingEditor ? "Открытие…" : "Редактировать шаблон"} className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-blue-500 dark:text-zinc-950 dark:hover:bg-blue-400" type="button" onClick={() => openEditor(true)} disabled={openingEditor}>{openingEditor ? "Открытие…" : "Редактировать шаблон"}</button>{openingEditor ? <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400" data-testid="template-editor-opening">Открытие редактора…</p> : null}</div> : null}
      {draft ? <DraftEditor draft={draft} onSaved={setDraft} onPublished={(next) => {
        setDraft(null); setDraftExists(false);
        void Promise.all([getPersonnelOrderTemplatePublished(item.type_code), getPersonnelOrderTemplateDraft(item.type_code)])
          .then(([actualPublished, actualDraft]) => { setPublished(actualPublished); setDraftExists(Boolean(actualDraft)); })
          .catch(() => setPublished(next));
      }} variables={(detail?.variables ?? []).map((variable) => variable.code)} warning={item.support_level === "PARTIAL" ? "Шаблон требует дальнейшей предметной формализации; неподтверждённые реквизиты не добавлены." : undefined} /> : null}
    </aside>
  );
}

export default function TemplatesPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeSection = resolveTemplateSection(searchParams.get("section"));
  const [items, setItems] = useState<PersonnelOrderTemplateCatalogItem[]>([]);
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("ALL");
  const [switchingType, setSwitchingType] = useState<string | null>(null);
  const selectedType = searchParams.get("type") || "";
  const displayedType = switchingType ?? selectedType;
  const selectedItem = items.find((item) => item.type_code === displayedType);

  useEffect(() => {
    if (switchingType && selectedType === switchingType) setSwitchingType(null);
  }, [selectedType, switchingType]);

  useEffect(() => {
    if (activeSection !== TEMPLATE_SECTIONS.personnelOrders) return;
    void listPersonnelOrderTemplateCatalog().then((data) => setItems(data.items)).catch(() => setItems([]));
  }, [activeSection]);

  const visibleItems = useMemo(() => items.filter((item) => {
    const haystack = `${item.type_code} ${item.title_ru} ${item.title_kk}`.toLowerCase();
    return (level === "ALL" || item.support_level === level) && haystack.includes(query.toLowerCase());
  }), [items, level, query]);

  function selectSection(section: TemplateSection) {
    if (section === activeSection) return;
    router.push(buildTemplateSectionHref(section, searchParams));
  }

  function selectType(type: string) {
    if (type === displayedType) return;
    setSwitchingType(type);
    const params = new URLSearchParams(searchParams.toString());
    params.set("section", TEMPLATE_SECTIONS.personnelOrders);
    params.set("type", type);
    router.push(`/admin/templates?${params.toString()}`);
  }

  return (
    <div className="notranslate flex flex-col gap-3 text-zinc-900 dark:text-zinc-50" lang="ru" translate="no" data-testid="templates-page">
      <header><h1 className="text-3xl font-semibold tracking-tight">Шаблоны</h1></header>
      <nav className="flex flex-wrap gap-2" aria-label="Разделы шаблонов">
        <button type="button" onClick={() => selectSection(TEMPLATE_SECTIONS.tasks)} className={`${TAB_CLASS} ${activeSection === TEMPLATE_SECTIONS.tasks ? "border-blue-700 bg-blue-700 text-white shadow-sm hover:bg-blue-800 dark:border-blue-400 dark:bg-blue-500 dark:text-zinc-950 dark:hover:bg-blue-400" : "border-zinc-200 bg-zinc-100/30 text-zinc-600 hover:bg-zinc-200 dark:border-zinc-800 dark:bg-zinc-900/30 dark:text-zinc-400 dark:hover:bg-zinc-800"}`} aria-current={activeSection === TEMPLATE_SECTIONS.tasks ? "page" : undefined}>Шаблоны задач</button>
        <button type="button" onClick={() => selectSection(TEMPLATE_SECTIONS.personnelOrders)} className={`${TAB_CLASS} ${activeSection === TEMPLATE_SECTIONS.personnelOrders ? "border-blue-700 bg-blue-700 text-white shadow-sm hover:bg-blue-800 dark:border-blue-400 dark:bg-blue-500 dark:text-zinc-950 dark:hover:bg-blue-400" : "border-zinc-200 bg-zinc-100/30 text-zinc-600 hover:bg-zinc-200 dark:border-zinc-800 dark:bg-zinc-900/30 dark:text-zinc-400 dark:hover:bg-zinc-800"}`} aria-current={activeSection === TEMPLATE_SECTIONS.personnelOrders ? "page" : undefined}>Шаблоны кадровых приказов</button>
      </nav>

      {activeSection === TEMPLATE_SECTIONS.tasks ? (
        <section aria-labelledby="task-templates-heading" data-testid="task-templates-section"><h2 id="task-templates-heading" className="sr-only">Шаблоны задач</h2><RegularTasksAdminClient embedded /></section>
      ) : (
        <section className="space-y-3" aria-labelledby="personnel-order-templates-heading" data-testid="personnel-order-templates-catalog">
          <h2 id="personnel-order-templates-heading" className="text-xl font-semibold">Шаблоны кадровых приказов</h2>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">Встроенные read-only шаблоны, построенные по действующим генераторам. Редактирование и версионирование будут добавлены на следующем этапе.</p>
          <GeneralPersonnelOrderRequirements />
          <div className="flex gap-2"><input aria-label="Поиск шаблонов кадровых приказов" value={query} onChange={(e) => setQuery(e.target.value)} className="rounded border px-2 py-1" /><select aria-label="Уровень поддержки" value={level} onChange={(e) => setLevel(e.target.value)} className="rounded border px-2 py-1"><option value="ALL">Все уровни</option><option value="SUPPORTED">SUPPORTED</option><option value="PARTIAL">PARTIAL</option><option value="NOT_IMPLEMENTED">NOT_IMPLEMENTED</option></select></div>
          <div className="grid gap-2 md:grid-cols-2" data-testid="personnel-order-template-list">{visibleItems.map((item) => <button type="button" key={item.type_code} onClick={() => selectType(item.type_code)} className="rounded border p-3 text-left" data-testid={`personnel-order-template-${item.type_code}`}><div className="font-medium">{item.title_ru}</div><div>{item.title_kk}</div><div className="font-mono text-xs">{item.type_code}</div><div>{item.support_level} · {item.supported_locales.join(", ")} · Встроенный шаблон {item.is_pilot ? "· Пилот" : ""}</div></button>)}</div>
          {selectedItem ? <TemplateDetail key={selectedItem.type_code} item={selectedItem} /> : null}
        </section>
      )}
    </div>
  );
}
