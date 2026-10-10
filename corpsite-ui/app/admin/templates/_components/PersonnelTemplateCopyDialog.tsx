"use client";
import { useEffect, useRef, useState } from "react";
import { usePersonnelSectionLanguage } from "@/app/directory/personnel/_lib/personnelSectionLanguage";
import { PERSONNEL_ORDER_GROUPS, PERSONNEL_ORDER_TYPE_GROUP, type PersonnelOrderCreateType } from "@/app/directory/personnel/_lib/personnelOrderTypeGroups";
import { copyPersonnelTemplate, listPersonnelIndependentTemplates, listPersonnelTemplateVersions,
  type PersonnelIndependentTemplate, type PersonnelOrderTemplateCatalogItem, type PersonnelOrderTemplateDraft } from "../_lib/personnelOrderTemplatesApi.client";

type Choice = { key: string; item: PersonnelOrderTemplateCatalogItem; template?: PersonnelIndependentTemplate };
type CopyFailure = { stage: "sources" | "versions" | "copy"; status?: number; code?: string };
function copyFailure(stage: CopyFailure["stage"], cause: unknown): CopyFailure {
  const failure = cause as { status?: number; details?: { detail?: { code?: string } } } | null;
  return { stage, status: failure?.status, code: failure?.details?.detail?.code };
}
export default function PersonnelTemplateCopyDialog({ item, catalog, templateId, sourceVersion, onClose, onCreated }: {
  item: PersonnelOrderTemplateCatalogItem; catalog: PersonnelOrderTemplateCatalogItem[]; templateId?: number;
  sourceVersion?: PersonnelOrderTemplateDraft; onClose: () => void;
  onCreated: (draft: PersonnelOrderTemplateDraft, target: PersonnelOrderTemplateCatalogItem) => void;
}) {
  const { language } = usePersonnelSectionLanguage();
  const kk = language === "kk";
  const m = kk ? {
    title: "Үлгі негізінде жасау", source: "Бастапқы үлгі", search: "Үлгіні іздеу",
    ru: "Жаңа үлгінің орысша атауы", kz: "Жаңа үлгінің қазақша атауы", version: "Бастапқы нұсқа",
    hint: "Жаңа үлгі бастапқы үлгінің өрістері мен кадрлық әрекетін мұраға алады. Жаңа атауды енгізіп, көшірілген мәтінді өңдеңіз. Бастапқы үлгі сақталады; көшірме жарияланбаған жоба ретінде жасалады.",
    create: "Жасау және өңдеу", busy: "Жасалуда…", cancel: "Бас тарту", loading: "Жүктелуде…", initial: "Кірістірілген үлгі",
    error: "Үлгілерді жүктеу немесе көшірме жасау мүмкін болмады. Қайта көріңіз.", empty: "Үлгілер табылмады", draft: "Жоба", published: "Жарияланған", archive: "Мұрағат",
    sourcesLoading: "Бастапқы үлгілер жүктелуде. Жүктелгеннен кейін жасау қолжетімді болады.", versionsLoading: "Бастапқы үлгінің нұсқалары жүктелуде.",
    sourcesError: "Бастапқы үлгілерді жүктеу мүмкін болмады. Жүктеуді қайталаңыз.", versionsError: "Бастапқы үлгінің нұсқаларын жүктеу мүмкін болмады. Жүктеуді қайталаңыз немесе басқа үлгіні таңдаңыз.",
    unavailable: "Таңдалған үлгінің көшірілетін нұсқасы жоқ. Басқа бастапқы үлгіні таңдаңыз.", sourceRequired: "Бастапқы үлгіні таңдаңыз.",
    namesRequired: "Жасау үшін жаңа үлгінің орысша және қазақша атауларын енгізіңіз.", forbidden: "Үлгілерді көруге немесе жасауға рұқсат жеткіліксіз. Әкімшіге хабарласыңыз.",
    unauthorized: "Сессия аяқталды. Қайта кіріңіз.", conflict: "Бастапқы нұсқа өзгерді. Нұсқаларды қайта жүктеп, жасауды қайталаңыз.", retry: "Жүктеуді қайталау",
  } : {
    title: "Создать на основе шаблона", source: "Исходный шаблон", search: "Поиск шаблона",
    ru: "Название нового шаблона на русском", kz: "Название нового шаблона на казахском", version: "Исходная версия",
    hint: "Новый шаблон наследует поля и кадровое действие исходного шаблона. Введите новое название и отредактируйте скопированный текст. Исходный шаблон сохранится; копия создаётся как неопубликованный черновик",
    create: "Создать и редактировать", busy: "Создание…", cancel: "Отмена", loading: "Загрузка…", initial: "Встроенный шаблон",
    error: "Не удалось загрузить шаблоны или создать копию. Попробуйте ещё раз.", empty: "Шаблоны не найдены", draft: "Черновик", published: "Опубликован", archive: "Архив",
    sourcesLoading: "Загружаются исходные шаблоны. Создание станет доступно после загрузки.", versionsLoading: "Загружаются версии исходного шаблона.",
    sourcesError: "Не удалось загрузить исходные шаблоны. Повторите загрузку.", versionsError: "Не удалось загрузить версии исходного шаблона. Повторите загрузку или выберите другой исходник.",
    unavailable: "У выбранного шаблона нет версии для копирования. Выберите другой исходный шаблон.", sourceRequired: "Выберите исходный шаблон.",
    namesRequired: "Для создания укажите названия нового шаблона на русском и казахском.", forbidden: "Недостаточно прав для просмотра или создания шаблонов. Обратитесь к администратору.",
    unauthorized: "Сессия завершена. Войдите снова.", conflict: "Исходная версия изменена. Обновите версии и повторите создание.", retry: "Повторить загрузку",
  };
  const dialog = useRef<HTMLDialogElement>(null);
  const [choices, setChoices] = useState<Choice[]>([]);
  const [sourceKey, setSourceKey] = useState("");
  const [query, setQuery] = useState("");
  const [versions, setVersions] = useState<PersonnelOrderTemplateDraft[]>([]);
  const [versionId, setVersionId] = useState<number>();
  const [loadedKey, setLoadedKey] = useState("");
  const [names, setNames] = useState({ name_ru: "", name_kk: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<CopyFailure>();
  const [sourcesLoading, setSourcesLoading] = useState(true);
  const [sourcesRefresh, setSourcesRefresh] = useState(0);
  const [versionsRefresh, setVersionsRefresh] = useState(0);
  const eligible = catalog.length ? catalog.filter(t => t.editor_available !== false) : [item];
  useEffect(() => { dialog.current?.showModal(); }, []);
  useEffect(() => {
    let cancelled = false;
    setSourcesLoading(true); setError(undefined);
    void Promise.all(eligible.map(async entry => {
      const result = await listPersonnelIndependentTemplates(entry.type_code);
      const options: Choice[] = result.items.map(template => ({ key: `${entry.type_code}:${template.template_id}`, item: entry, template }));
      if (!result.items.some(t => t.is_default)) options.unshift({ key: `${entry.type_code}:initial`, item: entry });
      return options;
    })).then(results => {
      if (cancelled) return;
      const all = results.flat(); setChoices(all);
      const current = all.find(c => c.item.type_code === item.type_code && (templateId != null ? c.template?.template_id === templateId : !c.template || c.template.is_default));
      setSourceKey(current?.key ?? "");
    }).catch(cause => { if (!cancelled) setError(copyFailure("sources", cause)); })
      .finally(() => { if (!cancelled) setSourcesLoading(false); });
    return () => { cancelled = true; };
    // Snapshot the catalogue and source when the dialog opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourcesRefresh]);
  const source = choices.find(c => c.key === sourceKey);
  useEffect(() => {
    let cancelled = false;
    setLoadedKey(""); setVersions([]); setVersionId(undefined);
    if (!source) return;
    if (!source.template) { setLoadedKey(source.key); return; }
    void listPersonnelTemplateVersions(source.item.type_code, source.template.template_id).then(result => {
      if (cancelled) return;
      setVersions(result.items);
      setVersionId(result.items.find(v => v.template_version_id === sourceVersion?.template_version_id)?.template_version_id ?? result.items[0]?.template_version_id);
      setLoadedKey(source.key);
    }).catch(cause => { if (!cancelled) setError(copyFailure("versions", cause)); });
    return () => { cancelled = true; };
  }, [source, sourceVersion, versionsRefresh]);
  const label = (choice: Choice) => choice.template
    ? (kk ? choice.template.name_kk || choice.template.name_ru : choice.template.name_ru || choice.template.name_kk)
    : (kk ? choice.item.title_kk || choice.item.title_ru : choice.item.title_ru || choice.item.title_kk);
  const version = versions.find(v => v.template_version_id === versionId);
  const initialAvailable = Boolean(source && !versions.length && (!source.template || source.template.is_default));
  const canCreate = !sourcesLoading && error?.stage !== "sources" && Boolean(source && loadedKey === sourceKey && (version || initialAvailable));
  const errorMessage = !error ? "" : error.status === 401 ? m.unauthorized : error.status === 403 ? m.forbidden
    : error.status === 409 ? m.conflict : error.stage === "sources" ? m.sourcesError : error.stage === "versions" ? m.versionsError : m.error;
  const blockedReason = errorMessage || (sourcesLoading ? m.sourcesLoading : !source ? m.sourceRequired
    : loadedKey !== sourceKey ? m.versionsLoading : !canCreate ? m.unavailable
    : !names.name_ru.trim() || !names.name_kk.trim() ? m.namesRequired : "");
  const matches = choices.filter(c => query.toLocaleLowerCase().trim().split(/\s+/).every(word => `${c.template?.name_ru ?? ""} ${c.template?.name_kk ?? ""} ${c.item.title_ru} ${c.item.title_kk}`.toLocaleLowerCase().includes(word)));
  const filtered = choices.filter(c => c.key === sourceKey || matches.includes(c));
  async function create() {
    if (busy || !canCreate || !source) return;
    setBusy(true); setError(undefined);
    try {
      const draft = await copyPersonnelTemplate(source.item.type_code, { ...names,
        ...(version ? { source_version_id: version.template_version_id, expected_revision: version.revision } : { base_source: "INITIAL" as const }),
      });
      onCreated({ ...draft, name_ru: draft.name_ru ?? names.name_ru.trim(), name_kk: draft.name_kk ?? names.name_kk.trim() }, source.item);
    } catch (cause) { setError(copyFailure("copy", cause)); setBusy(false); }
  }
  return <dialog ref={dialog} aria-labelledby="copy-template-heading" aria-describedby="copy-template-hint" data-testid="personnel-template-copy-form" data-source-template-id={source?.template?.template_id}
    onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}
    className="m-auto max-h-[90vh] w-[min(95vw,40rem)] overflow-y-auto rounded-xl border border-zinc-300 bg-white p-6 text-zinc-900 shadow-xl backdrop:bg-black/50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50">
    <form className="space-y-4" onSubmit={event => { event.preventDefault(); void create(); }}>
      <h4 id="copy-template-heading" className="text-lg font-semibold">{m.title}</h4>
      <label className="block">{m.search}<input type="search" aria-label={m.search} autoFocus disabled={busy} value={query} onChange={e => setQuery(e.target.value)} className="mt-1 block w-full rounded border bg-transparent p-2" /></label>
      <label className="block">{m.source}<select aria-label={m.source} aria-describedby="copy-template-hint" disabled={busy || !choices.length} value={sourceKey}
        onChange={e => { setSourceKey(e.target.value); setError(undefined); }} className="mt-1 block w-full rounded border bg-white p-2 dark:bg-zinc-900">
        {!choices.length ? <option value="">{sourcesLoading ? m.loading : m.sourceRequired}</option> : null}
        {PERSONNEL_ORDER_GROUPS.map(group => <optgroup key={group.id} label={group[language]}>{filtered.filter(c => PERSONNEL_ORDER_TYPE_GROUP[c.item.type_code as PersonnelOrderCreateType] === group.id).map(c => <option key={c.key} value={c.key}>{label(c)}</option>)}</optgroup>)}
      </select></label>
      <p id="copy-template-hint" className="text-sm">{m.hint}</p>
      {source ? <p className="text-sm" data-testid="copy-template-source">{m.source}: {label(source)} · {version ? `v${version.version_number}` : loadedKey !== sourceKey ? m.loading : initialAvailable ? m.initial : m.unavailable}</p> : null}
      {!matches.length && query ? <p className="text-sm">{m.empty}</p> : null}
      {versions.length ? <label className="block">{m.version}<select aria-label={m.version} disabled={busy} value={versionId ?? ""} onChange={e => setVersionId(Number(e.target.value))} className="ml-2 rounded border bg-white p-2 dark:bg-zinc-900">{versions.map(v => <option key={v.template_version_id} value={v.template_version_id}>v{v.version_number} · {v.status === "DRAFT" ? m.draft : v.status === "PUBLISHED" ? m.published : m.archive}</option>)}</select></label> : null}
      <label className="block">{m.ru}<input type="text" aria-label={m.ru} lang="ru" required maxLength={200} disabled={busy} value={names.name_ru} onChange={e => setNames(n => ({ ...n, name_ru: e.target.value }))} className="mt-1 block w-full rounded border bg-transparent p-2" /></label>
      <label className="block">{m.kz}<input type="text" aria-label={m.kz} lang="kk" required maxLength={200} disabled={busy} value={names.name_kk} onChange={e => setNames(n => ({ ...n, name_kk: e.target.value }))} className="mt-1 block w-full rounded border bg-transparent p-2" /></label>
      {blockedReason ? <p id="copy-create-blocked-reason" data-testid="copy-create-blocked-reason" role={error ? "alert" : "status"} className={`text-sm ${error ? "text-red-600" : "text-zinc-500"}`}>{blockedReason}</p> : null}
      {error ? <button type="button" disabled={busy} onClick={() => { setError(undefined); if (error.stage === "sources") setSourcesRefresh(n => n + 1); else setVersionsRefresh(n => n + 1); }} className="rounded border px-3 py-2">{m.retry}</button> : null}
      <div className="flex gap-2"><button type="submit" aria-describedby={blockedReason ? "copy-create-blocked-reason" : undefined} disabled={busy || !canCreate || !names.name_ru.trim() || !names.name_kk.trim()} className="rounded bg-blue-700 px-3 py-2 text-white disabled:opacity-50">{busy ? m.busy : m.create}</button><button type="button" disabled={busy} onClick={onClose} className="rounded border px-3 py-2">{m.cancel}</button></div>
    </form>
  </dialog>;
}
