"use client";
import { usePersonnelSectionLanguage, localizedPersonnelTitle } from "@/app/directory/personnel/_lib/personnelSectionLanguage";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import PersonnelReplacementPreviewForm from "./PersonnelReplacementPreviewForm";
import PersonnelTemplateRemoveDialog from "./PersonnelTemplateRemoveDialog";
import PersonnelTemplateVariants from "./PersonnelTemplateVariants";
import PersonnelTemplateIdentity from "./PersonnelTemplateIdentity";
import { PERSONNEL_ORDER_GROUPS, PERSONNEL_ORDER_TYPE_GROUP } from "@/app/directory/personnel/_lib/personnelOrderTypeGroups";
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
  type PersonnelIndependentTemplate,
  createPersonnelOrderTemplateDraft,
  getPersonnelOrderTemplateDraft,
  getPersonnelOrderTemplatePublished,
  getPersonnelOrderTemplateEditorBase,
  previewPersonnelOrderTemplateDraft,
  previewSavedPersonnelOrderTemplateDraft,
  savePersonnelOrderTemplateDraft,
  publishPersonnelOrderTemplateDraft,
} from "../_lib/personnelOrderTemplatesApi.client";

const TAB_CLASS = "rounded-xl border px-4 py-2 text-sm font-medium transition";
function templateArgs(id?: number | null): [] | [number] { return id == null ? [] : [id]; }
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
  const error = cause as { status?: number; message?: unknown; details?: { detail?: unknown } };
  const detail=error?.details?.detail;
  if (detail && typeof detail === "object" && "code" in detail && detail.code === "TEMPLATE_SCHEMA_REQUIRED") {
    return "Требуется согласованное обновление структуры БД до hrrecall001. БД автоматически не изменяется.";
  }
  if (error?.status === 403) return "Недостаточно прав управления кадровыми шаблонами.";
  if (error?.status && error.status >= 500) return `Ошибка загрузки API (HTTP ${error.status}). Повторите попытку.`;
  const validation = Array.isArray(error?.details?.detail) ? error.details.detail[0] as { loc?: unknown; msg?: unknown } : null;
  if (validation) {
    const location = Array.isArray(validation.loc) ? validation.loc.filter((part) => part !== "body").join(".") : "";
    const message = typeof validation.msg === "string" ? validation.msg : "Некорректное значение";
    return location ? `Поле «${location}»: ${message}` : message;
  }
  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string" && detail.message.trim()) return detail.message;
  return typeof error?.message === "string" && error.message.trim() ? error.message : "Не удалось выполнить действие.";
}

function templateLoadError(cause: unknown): string {
  const error=cause as {status?: number; details?: {detail?: {code?: string}}};
  if (error?.details?.detail?.code === "TEMPLATE_SCHEMA_REQUIRED") return draftErrorMessage(cause);
  if (error?.status === 403) return "Недостаточно прав управления кадровыми шаблонами.";
  return error?.status ? `Ответ API: HTTP ${error.status}.` : "Проверьте соединение и повторите загрузку.";
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

function PreviewFooter({ locale, itemTypeCode }: { locale: "ru" | "kk"; itemTypeCode?: string }) {
  if (itemTypeCode === "CONCURRENT_DUTY_END") return null;
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

type WorkingCopy = PersonnelOrderTemplateDraftText & {
  template_id?: number;
  kind: "WORKING_COPY";
  item_type_code: string;
  base: Awaited<ReturnType<typeof getPersonnelOrderTemplateEditorBase>>;
};

type EditorDocument =
  | { kind: "DRAFT"; draft: PersonnelOrderTemplateDraft }
  | { kind: "WORKING_COPY"; workingCopy: WorkingCopy };

function textMatches(left: PersonnelOrderTemplateDraftText, right: PersonnelOrderTemplateDraftText): boolean {
  return DRAFT_HEIGHT_FIELDS.every(({ ru, kk }) => left[ru[0]] === right[ru[0]] && left[kk[0]] === right[kk[0]]);
}

function DraftEditor({ editor, published, onSaved, onPublished, variables, requiredVariables, warning, onRemove }: { onRemove: (name: string) => void; editor: EditorDocument; published: PersonnelOrderTemplateDraft | null; onSaved: (draft: PersonnelOrderTemplateDraft) => void; onPublished: (draft: PersonnelOrderTemplateDraft) => void; variables: string[]; requiredVariables?: Partial<Record<keyof PersonnelOrderTemplateDraftText, string[]>>; warning?: string }) {
  const { language: sectionLanguage } = usePersonnelSectionLanguage();
  const initial = editor.kind === "DRAFT" ? editor.draft : editor.workingCopy;
  const [savedDraft, setSavedDraft] = useState<PersonnelOrderTemplateDraftText & { item_type_code: string; template_id?: number | null }>(initial);
  const [values, setValues] = useState<PersonnelOrderTemplateDraftText>(() => editableDraftText(initial));
  const [preview, setPreview] = useState<Record<"ru" | "kk", PersonnelOrderTemplatePreview> | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [previewSaved, setPreviewSaved] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const editorRef = useRef<HTMLElement | null>(null);
  const previewRef = useRef<HTMLDivElement | null>(null);
  const previewRequest = useRef(0);
  const editorDocument = useRef(editor);
  const ruTextareas = useRef<Partial<Record<keyof PersonnelOrderTemplateDraftText, HTMLTextAreaElement | null>>>({});
  const kkTextareas = useRef<Partial<Record<keyof PersonnelOrderTemplateDraftText, HTMLTextAreaElement | null>>>({});
  useEffect(() => {
    if (editorDocument.current === editor) return;
    editorDocument.current = editor;
    const next = editor.kind === "DRAFT" ? editor.draft : editor.workingCopy;
    setSavedDraft(next);
    setValues(editableDraftText(next));
  }, [editor]);
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
  const isWorkingCopy = editor.kind === "WORKING_COPY";
  const serverDraft = editor.kind === "DRAFT" ? editor.draft : null;
  const isInitialWorkingCopy = isWorkingCopy && editor.workingCopy.base.source === "INITIAL";
  const isDirty = !textMatches(values, savedDraft);
  const differsFromPublished = serverDraft != null && published != null && !textMatches(serverDraft, published);
  const canSave = !saving && (isInitialWorkingCopy || isDirty);
  const incompatible = Object.entries(values).flatMap(([field, value]) => {
    const tokens = [...value.matchAll(/\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}/g)].map(match => match[1]);
    const unknown = [...new Set(tokens.filter(code => !variables.includes(code)))];
    const missing = (requiredVariables?.[field as keyof PersonnelOrderTemplateDraftText] ?? []).filter(code => !tokens.includes(code));
    return unknown.length || missing.length ? [{ field, unknown, missing }] : [];
  });
  const replacementMode = /\{\{\s*replacement\.term\s*\}\}/.test(values.body_template_ru) ? (/\{\{\s*allowance\.percent\s*\}\}/.test(values.body_template_ru) ? "PAY" : "RATE") : null;
  const canPublish = incompatible.length === 0 && serverDraft != null && !publishing && !isDirty && (published == null || differsFromPublished);
  const showPreview = () => {
    const request = ++previewRequest.current;
    const submittedValues = editableDraftText(values);
    setError("");
    setNotice("");
    setPreview(null);
    setPreviewing(true);
    const useSaved = Boolean(serverDraft?.template_id && !isDirty);
    setPreviewSaved(useSaved);
    void (useSaved ? previewSavedPersonnelOrderTemplateDraft(serverDraft!) : previewPersonnelOrderTemplateDraft(savedDraft.item_type_code, submittedValues))
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
      ? createPersonnelOrderTemplateDraft(savedDraft.item_type_code, {
        ...submittedValues,
        base_source: editor.workingCopy.base.source,
        ...(editor.workingCopy.base.source === "INITIAL" ? {} : {
          base_published_template_version_id: editor.workingCopy.base.template_version_id!,
          base_published_revision: editor.workingCopy.base.revision!,
        }),
      }, ...templateArgs(savedDraft.template_id))
      : savePersonnelOrderTemplateDraft(savedDraft.item_type_code, { ...submittedValues, expected_revision: serverDraft!.revision, expected_template_version_id: serverDraft!.template_version_id }, ...templateArgs(savedDraft.template_id));
    void persist
      .then((next) => {
        const savedValues = editableDraftText(next);
        setSavedDraft(next);
        onSaved(next);
        setValues(savedValues);
        setNotice("Черновик сохранён");
        setPreviewSaved(true);
        const request = ++previewRequest.current;
        return (next.template_id ? previewSavedPersonnelOrderTemplateDraft(next) : previewPersonnelOrderTemplateDraft(next.item_type_code, savedValues))
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
        setError(`${draftErrorMessage(cause)} ${sectionLanguage === "kk" ? "Өзгерістер сақталмады. Енгізілген мәтін редакторда қалды." : "Изменения не сохранены. Введённый текст остался в редакторе."}`);
      })
      .finally(() => setSaving(false));
  };
  const reloadCurrentDraft = () => {
    if (!serverDraft) return;
    setReloading(true);
    setError("");
    setNotice("");
    void getPersonnelOrderTemplateDraft(savedDraft.item_type_code, ...templateArgs(savedDraft.template_id))
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
    void publishPersonnelOrderTemplateDraft(savedDraft.item_type_code, serverDraft!.revision, ...templateArgs(savedDraft.template_id))
      // Publishing returns an immutable snapshot, never the next editable
      // draft.  Let the parent replace and close the editor atomically.
      .then((next) => { onPublished(next); })
      .catch((cause) => setError(draftErrorMessage(cause))).finally(() => setPublishing(false));
  };
  return (
    <section ref={editorRef} className="mt-5 rounded-xl border border-blue-200 p-4" data-testid="template-draft-editor" data-template-id={savedDraft.template_id} data-template-version-id={serverDraft?.template_version_id} data-revision={serverDraft?.revision}>
      <h4 className="font-semibold">{isWorkingCopy ? (isInitialWorkingCopy ? "Первая версия шаблона ещё не сохранена" : `Несохранённая рабочая копия опубликованной версии ${editor.workingCopy.base.version_number}`) : "Черновая версия шаблона"}</h4>
      <p className="text-sm">{isWorkingCopy && editor.workingCopy.base.source === "PUBLISHED" ? "Основа: " : ""}<PersonnelTemplateIdentity templateId={savedDraft.template_id} versionId={serverDraft?.template_version_id ?? (isWorkingCopy ? editor.workingCopy.base.template_version_id : undefined)} versionNumber={serverDraft?.version_number ?? (isWorkingCopy ? editor.workingCopy.base.version_number : undefined)} status={serverDraft?.status ?? "PUBLISHED"} />{serverDraft ? ` · revision ${serverDraft.revision}` : ""}</p>
      <p className="mt-2 text-sm text-amber-700" data-testid="template-editor-application-notice">Эта версия не применяется к кадровым приказам.</p>
      {incompatible.length ? <div role="alert" data-testid="template-incompatible-variables" className="mt-3 text-sm text-red-700">
        <p>{sectionLanguage === "kk" ? "Жаңа бұйрық түрінің айнымалыларын жариялау алдында түзетіңіз." : "Исправьте переменные для нового вида приказа до публикации."}</p>
        {incompatible.map(issue => <p key={issue.field}>{issue.field}: {issue.unknown.length ? `${sectionLanguage === "kk" ? "Үйлесімсіз" : "Несовместимые"}: ${issue.unknown.join(", ")}. ` : ""}{issue.missing.length ? `${sectionLanguage === "kk" ? "Міндетті айнымалылар жоқ" : "Отсутствуют обязательные переменные"}: ${issue.missing.join(", ")}.` : ""}</p>)}
      </div> : null}
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
              onChange={(e) => change(ru[0], e.target.value)}
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
              onChange={(e) => change(kk[0], e.target.value)}
              className={`mt-1 w-full resize-none rounded border p-2 ${heightClass}`}
              style={{ minHeight: TEXTAREA_MIN_HEIGHT, maxHeight: TEXTAREA_MAX_HEIGHT }}
            />
          </label>,
        ])}
      </div>

      <p className="mt-3 text-xs" data-testid="template-editor-allowed-variables">Разрешённые переменные: {variables.join(", ")}.</p>
      <div className="mt-4 flex items-center gap-2 overflow-x-auto whitespace-nowrap border-t border-zinc-200 pt-3 dark:border-zinc-800" data-testid="template-draft-actions">
        <button type="button" onClick={showPreview} disabled={previewing} className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-800 transition hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800">{previewing ? "Формирование…" : "Предварительный просмотр"}</button>
        <button type="button" onClick={save} disabled={!canSave} className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-blue-500 dark:text-zinc-950 dark:hover:bg-blue-400">{saving ? "Сохранение…" : "Сохранить черновик"}</button>
        <button type="button" onClick={() => onRemove(sectionLanguage === "kk" ? values.title_kk : values.title_ru)} disabled={saving || publishing} className="shrink-0 rounded-lg border border-red-600 px-3 py-2 text-sm font-semibold text-red-700">Удалить шаблон</button>
        <button type="button" onClick={publish} disabled={!canPublish} className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{publishing ? "Публикация…" : "Опубликовать версию"}</button>
        <button type="button" onClick={resetHeights} className="rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800">Сбросить высоту полей</button>
        {error && serverDraft ? <button type="button" onClick={reloadCurrentDraft} disabled={reloading} className="rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60">{reloading ? "Загрузка…" : "Загрузить актуальную версию"}</button> : null}
        {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
        {notice ? <p role="status" className="text-sm text-emerald-700">{notice}</p> : null}
      </div>
      {serverDraft && published && !differsFromPublished && !isDirty ? <p className="mt-3 text-sm text-amber-700">Черновик полностью совпадает с опубликованной версией и не может быть опубликован</p> : null}
      {serverDraft && replacementMode && !isDirty ? <PersonnelReplacementPreviewForm draft={serverDraft} mode={replacementMode} onPreview={result=>{setPreview(result.previews);setPreviewSaved(true);setError("");}}/> : null}
      {preview ? <p className="mt-3 text-sm" data-testid="template-preview-origin">{previewSaved
        ? (sectionLanguage === "kk" ? "Сақталған жобаны алдын ала қарау" : "Просмотр сохранённого черновика")
        : (sectionLanguage === "kk" ? "Сақталмаған өзгерістерді алдын ала қарау" : "Просмотр несохранённых изменений")}</p> : null}
      {preview ? <div ref={previewRef} data-testid="template-draft-preview" data-preview-source={previewSaved ? "SAVED_DRAFT" : "EDITOR_VALUES"} data-template-id={previewSaved ? savedDraft.template_id : undefined} data-template-version-id={previewSaved ? serverDraft?.template_version_id : undefined} data-revision={previewSaved ? serverDraft?.revision : undefined} className="mt-4 grid gap-3 md:grid-cols-2">{(["ru", "kk"] as const).map((locale) => <article key={locale}><b>{locale.toUpperCase()}</b><p>{preview[locale].title}</p><p>{preview[locale].preamble}</p><p className="text-center">{preview[locale].directive}</p><p className="whitespace-pre-wrap">{preview[locale].body}</p><p>{preview[locale].basis}</p>{!replacementMode ? <PreviewFooter locale={locale} itemTypeCode={savedDraft.item_type_code} /> : null}</article>)}</div> : null}
    </section>
  );
}

function TemplateDetail({ item, templateId, selectedTemplate, onChanged, onRemoved, copyActions, copyForm, createdDraft }: { onRemoved?: () => void; item: PersonnelOrderTemplateCatalogItem; templateId?: number; selectedTemplate?: PersonnelIndependentTemplate; onChanged?: (published?: PersonnelOrderTemplateDraft) => void; copyActions?: React.ReactNode; copyForm?: React.ReactNode; createdDraft?: PersonnelOrderTemplateDraft }) {
  const { language } = usePersonnelSectionLanguage();
  const detail = item.template_detail ?? item.pilot_detail;
  const [editor, setEditor] = useState<EditorDocument | null>(null);
  const [serverDraft, setServerDraft] = useState<PersonnelOrderTemplateDraft | null>(null);
  const [published, setPublished] = useState<PersonnelOrderTemplateDraft | null>(null);
  const [removing, setRemoving] = useState(false);
  const [removalName, setRemovalName] = useState("");
  // The identity is persisted even before its first version is saved.
  const persistedTemplate = selectedTemplate;
  const [openingEditor, setOpeningEditor] = useState(false);
  const [openError, setOpenError] = useState("");
  const [loadError, setLoadError] = useState("");
  const openRequest = useRef(0);
  const loadRequest = useRef(0);
  const createdEditorRef = useRef<HTMLDivElement>(null);
  const draftExists = serverDraft?.status === "DRAFT";
  const reloadState = useCallback(() => {
    const request = ++loadRequest.current;
    setLoadError("");
    // Both reads are unconditional: a first-version DRAFT has no PUBLISHED
    // predecessor, and neither read is allowed to create a DRAFT.
    void Promise.all([getPersonnelOrderTemplatePublished(item.type_code, ...templateArgs(templateId)), getPersonnelOrderTemplateDraft(item.type_code, ...templateArgs(templateId))])
      .then(([nextPublished, nextDraft]) => {
        if (request !== loadRequest.current) return;
        setPublished(nextPublished);
        setServerDraft(nextDraft?.status === "DRAFT" ? nextDraft : null);
        if (templateId != null && selectedTemplate?.is_default === false && nextDraft?.status === "DRAFT") setEditor(current => current ?? { kind: "DRAFT", draft: nextDraft });
      })
      .catch(cause => {
        if (request !== loadRequest.current) return;
        setPublished(null);
        setServerDraft(null);
        setLoadError(`Не удалось загрузить черновик и опубликованную версию. ${templateLoadError(cause)}`);
      });
  }, [item.type_code, templateId, selectedTemplate?.is_default]);
  const openEditor = useCallback(() => {
    const request = ++openRequest.current;
    setOpenError("");
    setOpeningEditor(true);
    void getPersonnelOrderTemplateDraft(item.type_code, ...templateArgs(templateId))
      .then(async (existing): Promise<EditorDocument> => {
        if (existing?.status === "DRAFT") return { kind: "DRAFT", draft: existing };
        const base = await getPersonnelOrderTemplateEditorBase(item.type_code, ...templateArgs(templateId));
        return { kind: "WORKING_COPY", workingCopy: { kind: "WORKING_COPY", template_id: templateId, item_type_code: base.item_type_code, base, ...editableDraftText(base) } };
      })
      .then((next) => { if (request === openRequest.current) setEditor(current => current ?? next); })
      .catch(cause => {
        if (request === openRequest.current) {
          // Do not expose backend detail here: it can contain implementation
          // diagnostics. The user can safely retry the read-only bootstrap.
          setOpenError(`Не удалось открыть редактор. Повторите попытку. ${templateLoadError(cause)}`);
        }
      })
      .finally(() => { if (request === openRequest.current) setOpeningEditor(false); });
  }, [item.type_code, templateId]);
  useEffect(() => {
    setEditor(createdDraft ? { kind: "DRAFT", draft: createdDraft } : null); setPublished(null); setServerDraft(createdDraft ?? null); setOpenError("");
    if (item.editor_available) reloadState();
    return () => { loadRequest.current += 1; openRequest.current += 1; };
  }, [item.type_code, item.editor_available, reloadState, createdDraft]);
  useEffect(() => {
    if (editor) createdEditorRef.current?.scrollIntoView?.({ block: "start" });
  }, [createdDraft, Boolean(editor)]);
  return (
    <aside data-testid="personnel-order-template-detail" data-template-id={templateId} className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="text-lg font-semibold">{selectedTemplate ? (language === "kk" ? selectedTemplate.name_kk || selectedTemplate.name_ru : selectedTemplate.name_ru || selectedTemplate.name_kk) : localizedPersonnelTitle(item, language)}</h3>
      <p className="mt-2 text-sm">{item.type_code} · {item.support_level}</p>
      <p className="text-sm"><PersonnelTemplateIdentity templateId={templateId} versionId={serverDraft?.template_version_id ?? published?.template_version_id} versionNumber={serverDraft?.version_number ?? published?.version_number} status={serverDraft?.status ?? published?.status} /></p>
      <div data-testid="personnel-template-actions" className="mt-3 flex flex-wrap items-center gap-2">{item.editor_available && !editor ? <><button aria-label={openingEditor ? "Открытие…" : (draftExists ? "Продолжить редактирование" : "Редактировать шаблон")} className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-blue-500 dark:text-zinc-950 dark:hover:bg-blue-400" type="button" onClick={openEditor} disabled={openingEditor}>{openingEditor ? "Открытие…" : (draftExists ? "Продолжить редактирование" : "Редактировать шаблон")}</button>{openingEditor ? <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400" data-testid="template-editor-opening">Открытие редактора…</p> : null}{openError ? <p className="mt-2 text-sm text-red-700" role="alert">{openError}</p> : null}</> : null}{copyActions}</div>
      {copyForm}
      {loadError ? <div role="alert" className="mt-3 text-red-700">{loadError}<button type="button" onClick={reloadState} className="ml-2 rounded border px-3 py-2">Повторить загрузку карточки</button></div> : null}
      {published ? <section className="mt-4 rounded-lg border border-emerald-200 p-3" data-testid="template-published-read-only"><h4 className="font-semibold">Опубликованная версия шаблона</h4><p className="text-sm"><PersonnelTemplateIdentity templateId={templateId} versionId={published.template_version_id} versionNumber={published.version_number} status={published.status} /></p><p className="mt-2 whitespace-pre-wrap text-sm">{localizedPersonnelTitle(published, language)}</p>{draftExists ? <p className="mt-2 text-sm text-amber-700">Имеется черновик следующей версии.</p> : null}</section> : null}
      <p className="mt-1 text-sm">{item.uses_specialized_generator ? "Специализированный генератор" : "Общий fallback"}</p>
      {detail ? <FormalizedTemplateDetail detail={detail} showCatalogPreview={!item.editor_available} /> : <>
        <p className="mt-3">Обязательные поля: {item.required_fields.join(", ") || "не формализованы"}</p>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{item.notes}</p>
      </>}

      {editor ? <div ref={createdEditorRef} className="scroll-mt-20">{createdDraft ? <p role="status" className="mt-4 text-sm text-emerald-700" data-testid="template-copy-success">{createdDraft.type_changed ? (language === "kk" ? "Үлгінің түрі өзгертілді. Мәтін сақталды." : "Вид шаблона изменён. Тексты сохранены.") : language === "kk" ? `Бөлек жоба «${selectedTemplate?.name_kk || createdDraft.name_kk || createdDraft.title_kk}» жасалды. Бастапқы үлгі сақталды` : `Создан отдельный черновик «${selectedTemplate?.name_ru || createdDraft.name_ru || createdDraft.title_ru}». Исходный шаблон сохранён`}</p> : null}<DraftEditor editor={editor} published={published} onSaved={(next) => { setEditor({ kind: "DRAFT", draft: next }); setServerDraft(next); onChanged?.(next); }} onRemove={name => { setRemovalName(name); setRemoving(true); }} onPublished={next => { setEditor(null); setServerDraft(null); setPublished(next); reloadState(); onChanged?.(next); }} variables={item.allowed_variables} requiredVariables={item.required_variables} warning={item.support_level === "PARTIAL" ? "Шаблон требует дальнейшей предметной формализации; неподтверждённые реквизиты не добавлены." : undefined} /></div> : null}
      {removing ? <PersonnelTemplateRemoveDialog template={persistedTemplate} name={removalName} onClose={() => setRemoving(false)} onRemoved={() => { ++openRequest.current; ++loadRequest.current; setRemoving(false); setEditor(null); setServerDraft(null); setPublished(null); if (persistedTemplate) onRemoved?.(); }} /> : null}
    </aside>
  );
}

export default function TemplatesPageClient() {
  const { language } = usePersonnelSectionLanguage();
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeSection = resolveTemplateSection(searchParams.get("section"));
  const [items, setItems] = useState<PersonnelOrderTemplateCatalogItem[]>([]);
  const [catalogError, setCatalogError] = useState("");
  const [catalogRefresh, setCatalogRefresh] = useState(0);
  const selectedCardRef = useRef<HTMLDivElement>(null);
  const [group, setGroup] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("ALL");
  const [copiedDraft, setCopiedDraft] = useState<PersonnelOrderTemplateDraft>();
  const [switchingType, setSwitchingType] = useState<string | null>(null);
  const selectedType = searchParams.get("type") || "";
  const displayedType = switchingType ?? selectedType;
  const selectedItem = items.find((item) => item.type_code === displayedType && (!group || PERSONNEL_ORDER_TYPE_GROUP[item.type_code as keyof typeof PERSONNEL_ORDER_TYPE_GROUP] === group))
    ?? items.find((item) => !group || PERSONNEL_ORDER_TYPE_GROUP[item.type_code as keyof typeof PERSONNEL_ORDER_TYPE_GROUP] === group);

  useEffect(() => {
    if (selectedItem && displayedType) selectedCardRef.current?.scrollIntoView?.({block:"start"});
  },[selectedItem?.type_code,displayedType]);

  useEffect(() => {
    if (switchingType && selectedType === switchingType) setSwitchingType(null);
  }, [selectedType, switchingType]);

  useEffect(() => {
    if (activeSection !== TEMPLATE_SECTIONS.personnelOrders) return;
    let active=true; setCatalogError("");
    void listPersonnelOrderTemplateCatalog().then(data => {if(active) setItems(data.items);}).catch(cause => {if(active) {setItems([]);setCatalogError(`Не удалось загрузить каталог кадровых шаблонов. ${templateLoadError(cause)}`);}});
    return () => {active=false;};
  }, [activeSection,catalogRefresh]);

  const visibleItems = useMemo(() => items.filter((item) => {
    if (group && PERSONNEL_ORDER_TYPE_GROUP[item.type_code as keyof typeof PERSONNEL_ORDER_TYPE_GROUP] !== group) return false;
    return level === "ALL" || item.support_level === level;
  }), [items, level, group]);

  function selectSection(section: TemplateSection) {
    if (section === activeSection) return;
    router.push(buildTemplateSectionHref(section, searchParams));
  }

  function selectType(type: string) {
    if (type === displayedType) return;
    setCopiedDraft(undefined);
    setSwitchingType(type);
    const params = new URLSearchParams(searchParams.toString());
    params.set("section", TEMPLATE_SECTIONS.personnelOrders);
    params.set("type", type);
    params.delete("template_id");
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
          {catalogError ? <div role="alert" className="text-red-700">{catalogError}<button type="button" onClick={()=>setCatalogRefresh(n=>n+1)} className="ml-2 rounded border px-3 py-2">Повторить загрузку каталога</button></div> : null}
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">Откройте выбранный шаблон для редактирования или создайте на его основе независимый черновик с названиями RU/KZ.</p>
          <div className="flex gap-2"><input aria-label="Поиск шаблонов кадровых приказов" value={query} onChange={(e) => setQuery(e.target.value)} className="rounded border px-2 py-1" /><select aria-label="Уровень поддержки" value={level} onChange={(e) => setLevel(e.target.value)} className="rounded border px-2 py-1"><option value="ALL">Все уровни</option><option value="SUPPORTED">SUPPORTED</option><option value="PARTIAL">PARTIAL</option><option value="NOT_IMPLEMENTED">NOT_IMPLEMENTED</option></select></div>
          <div role="group" aria-label={language === "kk" ? "Бұйрық топтары" : "Группы приказов"} className="mb-3 flex flex-wrap gap-2">{PERSONNEL_ORDER_GROUPS.map(entry => <button type="button" key={entry.id} aria-pressed={group === entry.id} onClick={() => { const nextGroup = group === entry.id ? null : entry.id; setGroup(nextGroup); if (nextGroup && selectedItem && PERSONNEL_ORDER_TYPE_GROUP[selectedItem.type_code as keyof typeof PERSONNEL_ORDER_TYPE_GROUP] !== nextGroup) { const nextItem = items.find(item => PERSONNEL_ORDER_TYPE_GROUP[item.type_code as keyof typeof PERSONNEL_ORDER_TYPE_GROUP] === nextGroup); if (nextItem) selectType(nextItem.type_code); } }} className="rounded border px-3 py-2">{entry[language]}</button>)}</div>
          <div className="grid gap-2 md:grid-cols-2" data-testid="personnel-order-template-list">{visibleItems.flatMap((item) => item.templates?.length ? item.templates.filter(template => `${item.type_code} ${template.name_ru} ${template.name_kk}`.toLowerCase().includes(query.toLowerCase())).map(template=><button key={template.template_id} type="button" data-catalog-template-id={template.template_id} className="rounded border p-3 text-left hover:bg-blue-50 dark:hover:bg-zinc-800" onClick={()=>{
              setCopiedDraft(undefined);setSwitchingType(item.type_code);
              const params=new URLSearchParams(searchParams.toString());params.set("section",TEMPLATE_SECTIONS.personnelOrders);params.set("type",item.type_code);params.set("template_id",String(template.template_id));router.push(`/admin/templates?${params.toString()}`);
            }}><div className="font-medium">{language === "kk" ? template.name_kk || template.name_ru : template.name_ru || template.name_kk}</div><div className="font-mono text-xs">{item.type_code}</div><div className="text-sm"><PersonnelTemplateIdentity templateId={template.template_id} versionId={template.draft_version_id ?? template.template_version_id} versionNumber={template.draft_version_id ? template.draft_version_number : template.version_number} status={template.draft_version_id ? "DRAFT" : "PUBLISHED"} /></div></button>) : `${item.type_code} ${item.title_ru} ${item.title_kk}`.toLowerCase().includes(query.toLowerCase()) ? [<button key={item.type_code} type="button" onClick={() => selectType(item.type_code)} className="rounded border p-3 text-left" data-testid={`personnel-order-template-${item.type_code}`}><div className="font-medium">{localizedPersonnelTitle(item, language)}</div><div className="font-mono text-xs">{item.type_code}</div><div className="text-sm">{item.support_level} · {item.supported_locales.join(", ")}</div></button>] : [])}</div>
          {selectedItem ? <div ref={selectedCardRef} className="scroll-mt-20" data-testid="selected-personnel-template-card"><PersonnelTemplateVariants key={selectedItem.type_code} item={selectedItem} catalog={items} initialTemplateId={selectedItem.type_code === selectedType ? Number(searchParams.get("template_id")) || undefined : undefined} onSelected={id => { setCopiedDraft(undefined); const params = new URLSearchParams(searchParams.toString()); params.set("type", selectedItem.type_code); if (id) params.set("template_id", String(id)); else params.delete("template_id"); router.push(`/admin/templates?${params.toString()}`); }} initialDraft={copiedDraft?.item_type_code === selectedItem.type_code ? copiedDraft : undefined} onCreated={draft => { setGroup(null); setSwitchingType(draft.item_type_code); setCopiedDraft(draft); const params = new URLSearchParams(searchParams.toString()); params.set("type", draft.item_type_code); params.set("template_id", String(draft.template_id)); router.push(`/admin/templates?${params.toString()}`); }} onCatalogChanged={() => setCatalogRefresh(n => n + 1)} renderEditor={(templateId, onChanged, copyActions, copyForm, createdDraft, editorItem = selectedItem, selectedTemplate, onRemoved) => <TemplateDetail key={`${editorItem.type_code}:${templateId || "default"}`} item={editorItem} selectedTemplate={selectedTemplate} templateId={templateId} onChanged={onChanged} onRemoved={onRemoved} copyActions={copyActions} copyForm={copyForm} createdDraft={createdDraft} />} /></div> : null}
          <GeneralPersonnelOrderRequirements />
        </section>
      )}
    </div>
  );
}
