"use client";

import { useEffect, useMemo, useRef, useState } from "react";
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
  previewPersonnelOrderTemplateDraft,
  savePersonnelOrderTemplateDraft,
} from "../_lib/personnelOrderTemplatesApi.client";

const TAB_CLASS = "rounded-xl border px-4 py-2 text-sm font-medium transition";

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

function FormalizedTemplateDetail({ detail }: { detail: PersonnelOrderTemplatePilotDetail }) {
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

      <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800" aria-labelledby="pilot-preview-heading">
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
      </section>
    </div>
  );
}

function DraftEditor({ draft, onSaved }: { draft: PersonnelOrderTemplateDraft; onSaved: (draft: PersonnelOrderTemplateDraft) => void }) {
  const [values, setValues] = useState<PersonnelOrderTemplateDraftText>(() => editableDraftText(draft));
  const [preview, setPreview] = useState<Record<"ru" | "kk", PersonnelOrderTemplatePreview> | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const previewRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => { if (preview) previewRef.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" }); }, [preview]);
  const fields: Array<[keyof PersonnelOrderTemplateDraftText, string]> = [["title_ru", "Заголовок RU"], ["title_kk", "Заголовок KK"], ["preamble_ru", "Преамбула RU"], ["preamble_kk", "Преамбула KK"], ["body_template_ru", "Распорядительный текст RU"], ["body_template_kk", "Распорядительный текст KK"], ["basis_template_ru", "Основание RU"], ["basis_template_kk", "Основание KK"]];
  const change = (key: keyof PersonnelOrderTemplateDraftText, value: string) => setValues((old) => ({ ...old, [key]: value }));
  const showPreview = () => {
    setError("");
    setPreviewing(true);
    void previewPersonnelOrderTemplateDraft(draft.item_type_code, editableDraftText(values))
      .then((result) => setPreview(result.previews))
      .catch((cause) => setError(draftErrorMessage(cause)))
      .finally(() => setPreviewing(false));
  };
  const save = () => {
    setSaving(true);
    void savePersonnelOrderTemplateDraft(draft.item_type_code, { ...values, expected_revision: draft.revision })
      .then((next) => { onSaved(next); setValues(editableDraftText(next)); })
      .catch((cause) => setError(draftErrorMessage(cause)))
      .finally(() => setSaving(false));
  };
  return <section className="mt-5 rounded-xl border border-blue-200 p-4" data-testid="template-draft-editor"><h4 className="font-semibold">Черновая версия шаблона</h4><p className="text-sm">Версия {draft.version_number} · revision {draft.revision} · Черновик</p><p className="mt-2 text-sm text-amber-700">Черновик не применяется к кадровым приказам.</p><div className="mt-3 grid gap-3">{fields.map(([key, label]) => <label key={key} className="text-sm">{label}<textarea aria-label={label} value={values[key]} onChange={(e) => change(key, e.target.value)} className="mt-1 min-h-20 w-full rounded border p-2" /></label>)}</div><p className="mt-3 text-xs">Разрешённые переменные: employee.full_name, position.title_ru, position.title_kk, org_unit.title_ru, org_unit.title_kk, leave.start_ru, leave.start_kk, leave.end_ru, leave.end_kk, leave.days, basis.application_date_ru, basis.application_date_kk, basis.application_number_suffix.</p><div className="mt-5 flex flex-wrap items-center gap-3 border-t border-zinc-200 pt-4 dark:border-zinc-800" data-testid="template-draft-actions"><button type="button" onClick={showPreview} disabled={previewing} className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-800 transition hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800">{previewing ? "Формирование…" : "Предварительный просмотр"}</button><button type="button" onClick={save} disabled={saving} className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-blue-500 dark:text-zinc-950 dark:hover:bg-blue-400">{saving ? "Сохранение…" : "Сохранить черновик"}</button>{error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}</div>{preview ? <div ref={previewRef} data-testid="template-draft-preview" className="mt-4 grid gap-3 md:grid-cols-2">{(["ru", "kk"] as const).map((locale) => <article key={locale}><b>{locale.toUpperCase()}</b><p>{preview[locale].title}</p><p>{preview[locale].preamble}</p><p className="text-center">{preview[locale].directive}</p><p>{preview[locale].body}</p><p>{preview[locale].basis}</p><PreviewFooter locale={locale} /></article>)}</div> : null}</section>;
}

function TemplateDetail({ item }: { item: PersonnelOrderTemplateCatalogItem }) {
  const detail = item.template_detail ?? item.pilot_detail;
  const [draft, setDraft] = useState<PersonnelOrderTemplateDraft | null>(null);
  const [openingEditor, setOpeningEditor] = useState(false);
  const openEditor = () => {
    setOpeningEditor(true);
    void getPersonnelOrderTemplateDraft(item.type_code)
      .then((existing) => existing ?? createPersonnelOrderTemplateDraft(item.type_code))
      .then(setDraft)
      .finally(() => setOpeningEditor(false));
  };
  return (
    <aside data-testid="personnel-order-template-detail" className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
      <h3 className="text-lg font-semibold">{item.title_ru}</h3>
      <p className="mt-1">{item.title_kk}</p>
      <p className="mt-2 text-sm">{item.type_code} · {item.support_level}</p>
      <p className="mt-1 text-sm">{item.uses_specialized_generator ? "Специализированный генератор" : "Общий fallback"}</p>
      {detail ? <FormalizedTemplateDetail detail={detail} /> : <>
        <p className="mt-3">Обязательные поля: {item.required_fields.join(", ") || "не формализованы"}</p>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{item.notes}</p>
      </>}
      {item.editor_available && !draft ? <div className="mt-4"><button className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-blue-500 dark:text-zinc-950 dark:hover:bg-blue-400" type="button" onClick={openEditor} disabled={openingEditor}>{openingEditor ? "Открытие…" : "Редактировать"}</button></div> : null}
      {draft ? <DraftEditor draft={draft} onSaved={setDraft} /> : null}
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
  const selectedType = searchParams.get("type") || "";
  const selectedItem = items.find((item) => item.type_code === selectedType);

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
          {selectedItem ? <TemplateDetail item={selectedItem} /> : null}
        </section>
      )}
    </div>
  );
}
