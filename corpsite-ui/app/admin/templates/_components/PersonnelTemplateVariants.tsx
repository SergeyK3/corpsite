"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { usePersonnelSectionLanguage } from "@/app/directory/personnel/_lib/personnelSectionLanguage";
import PersonnelTemplateCopyDialog from "./PersonnelTemplateCopyDialog";
import PersonnelTemplateTypeDialog from "./PersonnelTemplateTypeDialog";
import { listPersonnelIndependentTemplates, listPersonnelTemplateVersions,
  type PersonnelIndependentTemplate, type PersonnelOrderTemplateCatalogItem, type PersonnelOrderTemplateDraft } from "../_lib/personnelOrderTemplatesApi.client";

export default function PersonnelTemplateVariants({ item, catalog = [item], initialDraft, initialTemplateId, onSelected, onCreated, onCatalogChanged, renderEditor }: {
  item: PersonnelOrderTemplateCatalogItem; catalog?: PersonnelOrderTemplateCatalogItem[]; initialDraft?: PersonnelOrderTemplateDraft; initialTemplateId?: number;
  onSelected?: (templateId: number | undefined) => void;
  onCreated?: (draft: PersonnelOrderTemplateDraft) => void;
  onCatalogChanged?: () => void;
  renderEditor: (templateId: number | undefined, onChanged: (published?: PersonnelOrderTemplateDraft) => void, copyActions: ReactNode, copyForm: ReactNode, createdDraft?: PersonnelOrderTemplateDraft, editorItem?: PersonnelOrderTemplateCatalogItem, selectedTemplate?: PersonnelIndependentTemplate, onRemoved?: () => void) => ReactNode;
}) {
  const [editorItem, setEditorItem] = useState(item);
  const { language, ready, error: languageError, reload: reloadLanguage } = usePersonnelSectionLanguage();
  const kk = language === "kk";
  const [templates, setTemplates] = useState<PersonnelIndependentTemplate[]>([]);
  const [selected, setSelected] = useState<number | undefined>(initialDraft?.template_id ?? initialTemplateId);
  const [selectionCleared, setSelectionCleared] = useState(false);
  const [changingType, setChangingType] = useState(false);
  const [versions, setVersions] = useState<PersonnelOrderTemplateDraft[]>([]);
  const [source, setSource] = useState<number>();
  const [copying, setCopying] = useState(false);
  const [legacySchema, setLegacySchema] = useState(false);
  const [loadStatus, setLoadStatus] = useState<number>();
  const [error, setError] = useState<"" | "templates" | "versions" | "copy">("");
  const [createdDraft, setCreatedDraft] = useState<PersonnelOrderTemplateDraft | undefined>(initialDraft);
  const [publication, setPublication] = useState<PersonnelOrderTemplateDraft>();
  const selectedTemplate = templates.find(t => t.template_id === selected) ?? (createdDraft?.template_id === selected && createdDraft?.name_ru && createdDraft?.name_kk ? {
    template_id: selected!, item_type_code: createdDraft.item_type_code, name_ru: createdDraft.name_ru, name_kk: createdDraft.name_kk,
    is_default: false, template_version_id: null, draft_version_id: createdDraft.template_version_id,
  } : undefined);
  const messages = kk ? {
    title: "Үлгі негізінде жасау", source: "Бастапқы үлгі", ru: "Нұсқаның орысша атауы", kk: "Нұсқаның қазақша атауы",
    hint: "Нұсқа атауы бұйрық тақырыбынан бөлек. Екі тілдегі мазмұн бөлек жобаға көшіріледі. Көшірме жарияланбайды.",
    create: "Жоба жасау", creating: "Жасалуда…", cancel: "Бас тарту", initial: "Кірістірілген үлгі",
    templates: "Дербес үлгілерді жүктеу мүмкін болмады.", versions: "Үлгі нұсқаларын жүктеу мүмкін болмады.",
    copy: "Көшірме жасау мүмкін болмады. Атауларды тексеріп, нұсқаларды жаңартыңыз.",
  } : {
    title: "Создать на основе шаблона", source: "Исходный шаблон", ru: "Название варианта на русском", kk: "Название варианта на казахском",
    hint: "Название варианта отличается от заголовка приказа. Содержание на обоих языках копируется в отдельный черновик. Копия не публикуется.",
    create: "Создать черновик", creating: "Создание…", cancel: "Отмена", initial: "Встроенный шаблон",
    templates: "Не удалось загрузить самостоятельные шаблоны.", versions: "Не удалось загрузить версии шаблона.",
    copy: "Не удалось создать копию. Проверьте названия и обновите версии.",
  };
  const errorMessage = error ? messages[error] : "";
  const [refresh, setRefresh] = useState(0);
  const [templatesLoaded, setTemplatesLoaded] = useState(false);
  const loadedType = useRef<string | undefined>(undefined);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [loadedTemplateId, setLoadedTemplateId] = useState<number | null>();
  useEffect(() => {
    if (initialTemplateId == null || initialTemplateId === selected) return;
    setSelected(initialTemplateId); setSelectionCleared(false); setCreatedDraft(undefined); setCopying(false);
  }, [initialTemplateId]);
  useEffect(() => {
    let cancelled = false;
    // Keep the validated card mounted while refreshing the same type after
    // save/publication, so its success/error state is not discarded.
    if (loadedType.current !== editorItem.type_code) setTemplatesLoaded(false);
    setError("");
    setLegacySchema(false); setLoadStatus(undefined);
    listPersonnelIndependentTemplates(editorItem.type_code).then(result => {
      if (cancelled) return;
      setTemplates(result.items);
      loadedType.current = editorItem.type_code;
      setTemplatesLoaded(true);
      const valid = result.items.some(t => t.template_id === selected);
      if (!valid && !selectionCleared) {
        const fallback = result.items.find(t => t.is_default)?.template_id ?? result.items[0]?.template_id;
        setSelected(fallback);
        if (selected != null) onSelected?.(fallback);
      }
    }).catch(cause => {
      if (cancelled) return;
      setError("templates"); setLoadStatus(cause?.status);
      if (cause?.details?.detail?.code === "TEMPLATE_SCHEMA_REQUIRED") {
        setLegacySchema(true); setTemplates([]); setTemplatesLoaded(true);
        setSelected(undefined); if (selected != null) onSelected?.(undefined);
      }
    });
    return () => { cancelled = true; };
  }, [editorItem.type_code, refresh]);
  useEffect(() => {
    let cancelled = false;
    setVersions([]); setSource(undefined);
    setVersionsLoading(selected != null);
    setLoadedTemplateId(selected == null ? null : undefined);
    if (!templatesLoaded || (selected != null && !templates.some(t => t.template_id === selected))) {
      setVersionsLoading(false);
      return () => { cancelled = true; };
    }
    if (selected != null) listPersonnelTemplateVersions(editorItem.type_code, selected).then(result => {
      if (cancelled) return;
      setVersions(result.items); setSource(result.items[0]?.template_version_id); setLoadedTemplateId(selected); setError("");
    }).catch(() => { if (!cancelled) setError("versions"); }).finally(() => { if (!cancelled) setVersionsLoading(false); });
    return () => { cancelled = true; };
  }, [editorItem.type_code, selected, refresh, templatesLoaded, templates]);
  const versionsReady = loadedTemplateId === (selected ?? null);
  const initialAvailable = templatesLoaded && versionsReady && !versionsLoading && !versions.length &&
    (selected == null ? templates.length === 0 : templates.find(t => t.template_id === selected)?.is_default === true);
  // The dialog loads its own sources. Opening it must not wait for this card's
  // versions, or a failed read leaves a visible button silently disabled.
  const schemaReason = kk
    ? "Дербес үлгілер үшін БД құрылымын hrrecall001 нұсқасына келісілген жаңарту қажет. Бұрынғы үлгілердің редакторы қолжетімді; БД автоматты түрде өзгермейді."
    : "Для независимых вариантов требуется согласованное обновление структуры БД до hrrecall001. Редактор прежних шаблонов доступен; БД автоматически не изменяется.";
  const copyBlockedReason = legacySchema ? schemaReason : ready === false
    ? languageError
      ? (kk ? "Кадр бөлімінің тілін жүктеу мүмкін болмады. Жүктеуді қайталаңыз." : "Не удалось загрузить язык кадрового раздела. Повторите загрузку.")
      : (kk ? "Кадр бөлімінің тілі жүктелуде. Жүктелгеннен кейін диалог қолжетімді болады." : "Загружается язык кадрового раздела. После загрузки диалог станет доступен.")
    : editorItem.editor_available === false
      ? (kk ? "Осы бұйрық түрі үшін үлгі жасау қолжетімсіз." : "Для этого вида приказа создание шаблона недоступно.")
      : "";
  const copyActions = <>
    <button type="button" disabled={Boolean(copyBlockedReason)} aria-describedby={copyBlockedReason ? "template-copy-blocked-reason" : undefined} onClick={() => { setCopying(true); setError(""); }}
      className="shrink-0 rounded-lg border border-blue-700 px-4 py-2 text-sm font-semibold text-blue-700 disabled:opacity-50 dark:border-blue-400 dark:text-blue-300">
      {kk ? "Негізінде жасау…" : "Создать на основе…"}
    </button>
    {copyBlockedReason ? <p id="template-copy-blocked-reason" role="status" className="text-sm text-amber-700">{copyBlockedReason}</p> : null}
    {languageError ? <button type="button" onClick={reloadLanguage} className="rounded border px-3 py-2 text-sm">{kk ? "Тілді қайта жүктеу" : "Повторить загрузку языка"}</button> : null}
    {versions.length ? <label className="text-sm">{kk ? "Бастапқы нұсқа" : "Исходная версия"}<select aria-label={kk ? "Бастапқы нұсқа" : "Исходная версия"} value={source ?? ""}
      onChange={event => setSource(Number(event.target.value))} className="ml-2 rounded border p-2">
      {versions.map(v => <option key={v.template_version_id} value={v.template_version_id}>v{v.version_number} · {kk ? "Нұсқа ID" : "ID версии"} {v.template_version_id} · {v.status}</option>)}
    </select></label> : <span className="text-sm text-zinc-500">{!templatesLoaded || versionsLoading ? (kk ? "Жүктелуде…" : "Загрузка…") : initialAvailable ? (kk ? "Бастапқы нұсқа: кірістірілген үлгі" : "Исходная основа: встроенный шаблон") : (kk ? "Бастапқы нұсқа қолжетімсіз" : "Исходная версия недоступна")}</span>}
    <button type="button" onClick={() => setRefresh(n => n + 1)} className="rounded border px-3 py-2 text-sm">{kk ? "Жаңарту" : "Обновить версии"}</button>

    {selectedTemplate && !selectedTemplate.is_default && versionsReady && versions.length === 1 && versions[0].status === "DRAFT" ? <button type="button" onClick={() => setChangingType(true)} className="rounded border px-3 py-2 text-sm">{kk ? "Үлгі түрін өзгерту…" : "Изменить вид шаблона…"}</button> : null}
  </>;
  const copyForm = copying ? <PersonnelTemplateCopyDialog item={editorItem} catalog={catalog} templateId={selected}
    sourceVersion={versions.find(v => v.template_version_id === source)} onClose={() => setCopying(false)}
    onCreated={(draft, target) => { setSelectionCleared(false); setEditorItem(target); setCreatedDraft(draft); setSelected(draft.template_id); setRefresh(n => n + 1); setCopying(false); onCreated?.(draft); }} /> : null;
  return <section className="mt-4 space-y-3" data-testid="personnel-independent-templates">
    <div role="group" aria-label={kk ? "Үлгі нұсқалары" : "Самостоятельные шаблоны"} className="grid gap-2 sm:grid-cols-2">
      {templates.map(t => <button key={t.template_id} type="button" aria-pressed={selected === t.template_id}
        data-template-id={t.template_id} onClick={() => { setSelectionCleared(false); setSelected(t.template_id); setCreatedDraft(undefined); setCopying(false); setError(""); onSelected?.(t.template_id); }} className="rounded border px-3 py-2">
        {kk ? t.name_kk || t.name_ru : t.name_ru || t.name_kk}{t.is_default ? (kk ? " · Әдепкі" : " · По умолчанию") : ""}<span className="ml-2 text-xs text-zinc-500">#{t.template_id}</span>
      </button>)}
    </div>
    {errorMessage && !copying && !legacySchema ? <p role="alert">{errorMessage}{loadStatus ? ` (HTTP ${loadStatus})` : ""}</p> : null}
    {publication && publication.template_id === selected ? <p role="status" data-testid="template-publication-success" className="text-sm text-emerald-700">{kk ? `«${selectedTemplate?.name_kk || publication.title_kk}» үлгісінің v${publication.version_number} нұсқасы жарияланды.` : `Версия v${publication.version_number} шаблона «${selectedTemplate?.name_ru || publication.title_ru}» опубликована.`}</p> : null}
    {copyForm}
    {changingType && versions[0] && selectedTemplate ? <PersonnelTemplateTypeDialog draft={{...versions[0], name_ru: selectedTemplate.name_ru, name_kk: selectedTemplate.name_kk}} catalog={catalog} onClose={() => setChangingType(false)} onChanged={draft => { setChangingType(false); setCreatedDraft(draft); setEditorItem(catalog.find(item => item.type_code === draft.item_type_code)!); setRefresh(n => n + 1); onCreated?.(draft); }} /> : null}

    {selectionCleared ? <p role="status">{kk ? "Үлгіні таңдаңыз." : "Выберите шаблон."}</p> : templatesLoaded && (selected == null || selectedTemplate) ? renderEditor(selected, published => { if (published?.status === "PUBLISHED") { setPublication(published); setCreatedDraft(undefined); } setRefresh(n => n + 1); onCatalogChanged?.(); }, copyActions, null, createdDraft?.template_id === selected ? createdDraft : undefined, editorItem, selectedTemplate, () => { setSelectionCleared(true); setSelected(undefined); setCreatedDraft(undefined); setPublication(undefined); setRefresh(n => n + 1); onSelected?.(undefined); onCatalogChanged?.(); }) : <div>{copyActions}{!error ? <p role="status">{kk ? "Үлгі жүктелуде…" : "Загрузка шаблона…"}</p> : null}</div>}
  </section>;
}
