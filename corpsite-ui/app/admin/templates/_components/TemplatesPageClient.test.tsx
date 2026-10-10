import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TemplatesPageClient from "./TemplatesPageClient";
import { PersonnelSectionLanguageProvider } from "@/app/directory/personnel/_lib/personnelSectionLanguage";
import { apiFetchJson } from "@/lib/api";
import { copyPersonnelTemplate, listPersonnelIndependentTemplates, listPersonnelTemplateVersions, removePersonnelTemplate } from "../_lib/personnelOrderTemplatesApi.client";
import { createPersonnelOrderTemplateDraft, getPersonnelOrderTemplateDraft, getPersonnelOrderTemplateEditorBase, getPersonnelOrderTemplatePublished, listPersonnelOrderTemplateCatalog, publishPersonnelOrderTemplateDraft, savePersonnelOrderTemplateDraft } from "../_lib/personnelOrderTemplatesApi.client";

let currentSearch = new URLSearchParams("section=personnel-orders&type=TERMINATION");
const routerPush=vi.hoisted(()=>vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: routerPush }), useSearchParams: () => currentSearch, usePathname: () => "/admin/templates" }));
vi.mock("@/lib/api", async () => ({ ...(await vi.importActual<object>("@/lib/api")), apiFetchJson: vi.fn() }));
vi.mock("@/app/regular-tasks/_components/RegularTasksAdminClient", () => ({ default: () => null }));
vi.mock("../_lib/personnelOrderTemplatesApi.client", () => ({ listPersonnelIndependentTemplates: vi.fn().mockResolvedValue({items: []}), listPersonnelTemplateVersions: vi.fn().mockResolvedValue({items: []}), copyPersonnelTemplate: vi.fn(), removePersonnelTemplate: vi.fn(), listPersonnelOrderTemplateCatalog: vi.fn(), getPersonnelOrderTemplateDraft: vi.fn(), getPersonnelOrderTemplatePublished: vi.fn(), getPersonnelOrderTemplateEditorBase: vi.fn(), createPersonnelOrderTemplateDraft: vi.fn(), savePersonnelOrderTemplateDraft: vi.fn(), previewPersonnelOrderTemplateDraft: vi.fn(), publishPersonnelOrderTemplateDraft: vi.fn() }));

const texts = { title_ru: "Заголовок RU", title_kk: "Тақырып KK", preamble_ru: "Преамбула RU", preamble_kk: "Преамбула KK", body_template_ru: "{{employee.full_name}}", body_template_kk: "{{employee.full_name}}", basis_template_ru: "Основание", basis_template_kk: "Негіз" };
const published = { ...texts, template_version_id: 20, item_type_code: "TERMINATION", version_number: 2, revision: 4, status: "PUBLISHED", based_on_built_in: true };
const draft = { ...texts, title_ru: "Изменённый заголовок", template_version_id: 21, item_type_code: "TERMINATION", version_number: 3, revision: 1, status: "DRAFT", based_on_built_in: true };
const catalog = { items: [{ type_code: "TERMINATION", title_ru: "Об увольнении", title_kk: "Жұмыстан босату туралы", source: "BUILT_IN" as const, support_level: "SUPPORTED" as const, supported_locales: ["ru", "kk"], uses_specialized_generator: true, is_pilot: false, editor_available: true, allowed_variables: ["employee.full_name"], required_fields: [], notes: "", pilot_detail: null, template_detail: null }] };
const publishedBase = { ...texts, source: "PUBLISHED" as const, item_type_code: "TERMINATION", template_version_id: 20, version_number: 2, revision: 4 };
const initialBase = { ...texts, source: "INITIAL" as const, item_type_code: "TERMINATION", template_version_id: null, version_number: null, revision: null };
const setup = () => render(<TemplatesPageClient />);
const open = async (label = "Редактировать шаблон") => { await screen.findByRole("button", { name: label }); fireEvent.click(screen.getByRole("button", { name: label })); return screen.findByTestId("template-draft-editor"); };
const changeTitle = (value: string) => fireEvent.change(screen.getByLabelText("Заголовок RU"), { target: { value } });

describe("TemplatesPageClient draft lifecycle", () => {
  it("lists and searches every independent identity rather than only the type's default name",async()=>{
    const first={template_id:9,item_type_code:"TERMINATION",name_ru:"TEST обычный",name_kk:"TEST бірінші",is_default:true,template_version_id:20,draft_version_id:null};
    const second={...first,template_id:24,name_ru:"TEST процентная доплата",name_kk:"TEST қосымша ақы",is_default:false,template_version_id:null,draft_version_id:36};
    vi.mocked(listPersonnelOrderTemplateCatalog).mockResolvedValue({items:[{...catalog.items[0],templates:[first,second]}]});
    vi.mocked(apiFetchJson).mockResolvedValue({language:"ru",can_edit:false});
    render(<PersonnelSectionLanguageProvider><TemplatesPageClient/></PersonnelSectionLanguageProvider>);
      await waitFor(()=>expect(document.querySelector('[data-catalog-template-id="24"]')).toBeInTheDocument());
      const list = screen.getByTestId("personnel-order-template-list");
      expect(document.querySelector('[data-catalog-template-id="9"]')?.parentElement).toBe(list);
      expect(document.querySelector('[data-catalog-template-id="24"]')?.parentElement).toBe(list);
    fireEvent.change(screen.getByLabelText("Поиск шаблонов кадровых приказов"),{target:{value:"процентная доплата"}});
      expect(document.querySelector('[data-catalog-template-id="9"]')).not.toBeInTheDocument();
    expect(document.querySelector('[data-catalog-template-id="24"]')).toBeInTheDocument();
    fireEvent.click(document.querySelector<HTMLButtonElement>('[data-catalog-template-id="24"]')!);
    expect(routerPush.mock.calls.at(-1)?.[0]).toContain("template_id=24");
    expect(routerPush.mock.calls.at(-1)?.[0]).toContain("type=TERMINATION");
    expect(publishPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });
  it("shows the backend revision-conflict message and preserves the edited title", async () => {
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(draft);
    vi.mocked(savePersonnelOrderTemplateDraft).mockRejectedValue({status:409,message:"HTTP 409",details:{detail:{code:"TEMPLATE_REVISION_CONFLICT",message:"Черновик изменён другим пользователем."}}});
    setup(); await open("Продолжить редактирование"); changeTitle("TEST новое название");
    fireEvent.click(screen.getByRole("button",{name:"Сохранить черновик"}));
    expect(await screen.findByRole("alert")).toHaveTextContent("Черновик изменён другим пользователем.");
    expect(screen.getByLabelText("Заголовок RU")).toHaveValue("TEST новое название");
  });
  it("cancels deletion without writes and discards an unsaved working copy", async () => {
    vi.mocked(getPersonnelOrderTemplatePublished).mockResolvedValue(null);
    vi.mocked(getPersonnelOrderTemplateEditorBase).mockResolvedValue(initialBase);
    setup(); await open(); changeTitle("TEST unsaved");
    fireEvent.click(screen.getByRole("button",{name:"Удалить шаблон"}));
    fireEvent.click(screen.getByRole("button",{name:"Бас тарту"}));
    expect(screen.getByLabelText("Заголовок RU")).toHaveValue("TEST unsaved");
    expect(removePersonnelTemplate).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button",{name:"Удалить шаблон"}));
    fireEvent.click(screen.getByRole("button",{name:"Жою"}));
    await waitFor(()=>expect(screen.queryByTestId("template-draft-editor")).not.toBeInTheDocument());
    expect(removePersonnelTemplate).not.toHaveBeenCalled();
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("allows confirmed deletion of a saved default and closes its editor", async () => {
    const template={template_id:99,item_type_code:"TERMINATION",name_ru:"TEST RU",name_kk:"TEST KK",is_default:true,template_version_id:20,draft_version_id:null};
    let removed=false;
    vi.mocked(listPersonnelIndependentTemplates).mockImplementation(async()=>({items:removed?[]:[template]}));
    vi.mocked(removePersonnelTemplate).mockImplementation(async()=>{removed=true;return {template_id:99,action:"ARCHIVED"};});
    setup(); await open();
    const actions=screen.getByTestId("template-draft-actions");
    const buttons=Array.from(actions.querySelectorAll("button")).map(b=>b.textContent);
    expect(buttons.indexOf("Удалить шаблон")).toBe(buttons.indexOf("Сохранить черновик")+1);
    fireEvent.click(screen.getByRole("button",{name:"Удалить шаблон"}));
    fireEvent.click(screen.getByRole("button",{name:"Жою"}));
    await waitFor(()=>expect(removePersonnelTemplate).toHaveBeenCalledWith(template));
    await waitFor(()=>expect(screen.queryByTestId("template-draft-editor")).not.toBeInTheDocument());
  });
  it("deletes a persisted identity without versions through the API and refreshes the catalogue", async () => {
    const template={template_id:7,item_type_code:"TERMINATION",name_ru:"TEST empty",name_kk:"TEST KK",is_default:true,template_version_id:null,draft_version_id:null};
    let removed=false;
    vi.mocked(apiFetchJson).mockResolvedValue({language:"ru",can_edit:false});
    vi.mocked(listPersonnelIndependentTemplates).mockImplementation(async()=>({items:removed?[]:[template]}));
    vi.mocked(listPersonnelOrderTemplateCatalog).mockImplementation(async()=>({items:[{...catalog.items[0],templates:removed?[]:[template]}]}));
    vi.mocked(getPersonnelOrderTemplatePublished).mockResolvedValue(null);
    vi.mocked(getPersonnelOrderTemplateEditorBase).mockResolvedValue({...initialBase,template_id:7});
    vi.mocked(removePersonnelTemplate).mockImplementation(async()=>{removed=true;return {template_id:7,action:"DELETED"};});
    render(<PersonnelSectionLanguageProvider><TemplatesPageClient/></PersonnelSectionLanguageProvider>);
    await open();
    expect(screen.getByTestId("template-draft-editor")).toHaveTextContent("Шаблон №7 · Версия не сохранена");
    expect(document.querySelector('[data-catalog-template-id="7"]')).toHaveTextContent("Шаблон №7 · Версия не сохранена");
    fireEvent.click(screen.getByRole("button",{name:"Удалить шаблон"}));
    expect(screen.getByTestId("template-remove-dialog")).toHaveTextContent('„TEST empty“ (ID 7)');
    fireEvent.click(screen.getByRole("button",{name:"Удалить"}));
    await waitFor(()=>expect(removePersonnelTemplate).toHaveBeenCalledWith(template));
    await waitFor(()=>expect(document.querySelector('[data-catalog-template-id="7"]')).not.toBeInTheDocument());
    expect(screen.queryByTestId("template-draft-editor")).not.toBeInTheDocument();
  });
  it.each(["rejected", "wrong identity"])("keeps the editor open when deletion is %s",async mode=>{
    const template={template_id:7,item_type_code:"TERMINATION",name_ru:"TEST empty",name_kk:"TEST KK",is_default:true,template_version_id:null,draft_version_id:null};
    vi.mocked(listPersonnelIndependentTemplates).mockResolvedValue({items:[template]});
    vi.mocked(getPersonnelOrderTemplatePublished).mockResolvedValue(null);
    vi.mocked(getPersonnelOrderTemplateEditorBase).mockResolvedValue({...initialBase,template_id:7});
    if(mode==="rejected")vi.mocked(removePersonnelTemplate).mockRejectedValue({status:500});
    else vi.mocked(removePersonnelTemplate).mockResolvedValue({template_id:8,action:"DELETED"});
    setup();await open();
    fireEvent.click(screen.getByRole("button",{name:"Удалить шаблон"}));
    fireEvent.click(screen.getByRole("button",{name:"Жою"}));
    await screen.findByRole("alert");
    expect(screen.getByTestId("template-remove-dialog")).toBeInTheDocument();
    expect(screen.getByTestId("template-draft-editor")).toBeInTheDocument();
    expect(screen.getByLabelText("Заголовок RU")).toHaveValue(initialBase.title_ru);
  });
  beforeEach(() => { vi.mocked(listPersonnelIndependentTemplates).mockReset().mockResolvedValue({items: []}); vi.mocked(listPersonnelTemplateVersions).mockReset().mockResolvedValue({items: []}); vi.mocked(copyPersonnelTemplate).mockReset(); vi.mocked(removePersonnelTemplate).mockReset().mockResolvedValue({template_id:99,action:"DELETED"});
    Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value: function () { this.setAttribute("open", ""); } });
    currentSearch = new URLSearchParams("section=personnel-orders&type=TERMINATION"); window.localStorage.clear();
    vi.mocked(listPersonnelOrderTemplateCatalog).mockReset().mockResolvedValue(catalog);
    vi.mocked(getPersonnelOrderTemplatePublished).mockReset().mockResolvedValue(published);
    vi.mocked(getPersonnelOrderTemplateDraft).mockReset().mockResolvedValue(null);
    vi.mocked(getPersonnelOrderTemplateEditorBase).mockReset().mockResolvedValue(publishedBase);
    vi.mocked(createPersonnelOrderTemplateDraft).mockReset().mockResolvedValue(draft);
    vi.mocked(savePersonnelOrderTemplateDraft).mockReset().mockResolvedValue({ ...draft, revision: 2 });
    vi.mocked(publishPersonnelOrderTemplateDraft).mockReset().mockResolvedValue({ ...draft, status: "PUBLISHED" });
    vi.stubGlobal("confirm", vi.fn(() => true));
  });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it("reports catalog loading failures and retries instead of silently hiding all cards",async()=>{
    vi.mocked(listPersonnelOrderTemplateCatalog).mockRejectedValueOnce({status:500});
    setup();await screen.findByRole("alert");
    expect(screen.getByRole("alert")).toHaveTextContent("каталог кадровых шаблонов");
    expect(screen.getByRole("alert")).toHaveTextContent("HTTP 500");
    fireEvent.click(screen.getByRole("button",{name:"Повторить загрузку каталога"}));
    await screen.findByTestId("personnel-order-template-detail");
  });

  it("reports the failing version read on the card while preserving a visible editor entry",async()=>{
    vi.mocked(getPersonnelOrderTemplateDraft).mockRejectedValue({status:500});
    setup();await screen.findByRole("alert");
    expect(screen.getByRole("alert")).toHaveTextContent("черновик и опубликованную версию");
    expect(screen.getByRole("button",{name:"Редактировать шаблон"})).toBeEnabled();
    expect(screen.getByRole("button",{name:"Повторить загрузку карточки"})).toBeEnabled();
  });

  it("shows the selected card after the tiles and before general requirements without an extra type selection", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders");
    vi.mocked(apiFetchJson).mockResolvedValue({ language: "kk", can_edit: false });
    render(<PersonnelSectionLanguageProvider><TemplatesPageClient /></PersonnelSectionLanguageProvider>);
    const openButton = await screen.findByRole("button", { name: "Редактировать шаблон" });
    const actions = screen.getByTestId("personnel-template-actions");
    expect(actions).toContainElement(openButton);
    const copyButton = screen.getByRole("button", { name: /Создать на основе|Негізінде жасау/ });
    expect(actions).toContainElement(copyButton);
    await waitFor(() => expect(copyButton).toBeEnabled());
    expect(screen.getByTestId("personnel-order-template-list").compareDocumentPosition(actions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(actions.compareDocumentPosition(screen.getByTestId("personnel-order-common-requirements")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    fireEvent.click(copyButton);
    expect(screen.getByLabelText("Жаңа үлгінің орысша атауы")).toBeVisible();
    expect(screen.getByLabelText("Жаңа үлгінің қазақша атауы")).toBeVisible();
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("automatically opens the independent copied draft and confirms the original is preserved", async () => {
    vi.mocked(apiFetchJson).mockResolvedValue({ language: "ru", can_edit: false });
    vi.mocked(copyPersonnelTemplate).mockResolvedValue({ ...draft, template_id: 99, version_number: 1 }); vi.mocked(listPersonnelIndependentTemplates).mockImplementation(async () => ({items: vi.mocked(copyPersonnelTemplate).mock.calls.length ? [{template_id:99,item_type_code:"TERMINATION",name_ru:"Новый вариант",name_kk:"Жаңа нұсқа",is_default:false,template_version_id:null,draft_version_id:21}] : []}));
    render(<PersonnelSectionLanguageProvider><TemplatesPageClient /></PersonnelSectionLanguageProvider>);
    await waitFor(() => expect(screen.getByRole("button", { name: "Создать на основе…" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Создать на основе…" }));
    expect(screen.getByRole("dialog", { name: "Создать на основе шаблона" })).toBeVisible();
    await waitFor(() => expect(screen.getByLabelText("Исходный шаблон")).toBeEnabled());
    fireEvent.change(screen.getByLabelText("Название нового шаблона на русском"), { target: { value: "Новый вариант" } });
    fireEvent.change(screen.getByLabelText("Название нового шаблона на казахском"), { target: { value: "Жаңа нұсқа" } });
    await waitFor(() => expect(screen.getByRole("button", { name: "Создать и редактировать" })).toBeEnabled()); fireEvent.click(screen.getByRole("button", { name: "Создать и редактировать" }));
    await screen.findByTestId("template-draft-editor");
    expect(screen.getByTestId("template-copy-success")).toHaveTextContent("Создан отдельный черновик «Новый вариант». Исходный шаблон сохранён");
    expect(screen.getByLabelText("Заголовок RU")).toHaveValue(draft.title_ru);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it.each(["ru", "kk"] as const)("uses shared %s names in list and editor without changing bilingual texts", async language => {
    vi.mocked(apiFetchJson).mockResolvedValue({ language, can_edit: false });
    render(<PersonnelSectionLanguageProvider><TemplatesPageClient /></PersonnelSectionLanguageProvider>);
    const title = language === "ru" ? catalog.items[0].title_ru : catalog.items[0].title_kk;
    await screen.findByRole("heading", { name: title });
    expect(screen.getByRole("button", { name: language === "ru" ? "Создать на основе…" : "Негізінде жасау…" })).toBeVisible();
    expect(screen.getByTestId("personnel-order-template-TERMINATION")).toHaveTextContent(title);
    await open();
    expect(screen.getByLabelText("Заголовок RU")).toHaveValue(texts.title_ru);
    expect(screen.getByLabelText("Заголовок KK")).toHaveValue(texts.title_kk);
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
    expect(savePersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("mount and reload request PUBLISHED and DRAFT only", async () => {
    const view = setup(); await screen.findByTestId("template-published-read-only");
    expect(getPersonnelOrderTemplatePublished).toHaveBeenCalledWith("TERMINATION"); expect(getPersonnelOrderTemplateDraft).toHaveBeenCalledWith("TERMINATION"); expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
    view.unmount(); setup(); await screen.findByTestId("template-published-read-only"); expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("opens a PUBLISHED working copy without POST, without draftExists, and with disabled actions", async () => {
    setup(); const editor = await open();
    expect(editor).toHaveTextContent("Несохранённая рабочая копия опубликованной версии 2"); expect(editor).not.toHaveTextContent("revision 0"); expect(screen.getByLabelText("Заголовок RU")).toHaveValue(texts.title_ru);
    expect(screen.getByTestId("template-editor-application-notice")).toHaveTextContent("Эта версия не применяется к кадровым приказам.");
    expect(editor).not.toHaveTextContent("Черновая версия шаблона");
    expect(screen.getByTestId("template-published-read-only")).not.toHaveTextContent("Имеется черновик следующей версии"); expect(screen.getByRole("button", { name: "Сохранить черновик" })).toBeDisabled(); expect(screen.getByRole("button", { name: "Опубликовать версию" })).toBeDisabled(); expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("first changed save sends all text with typed PUBLISHED optimistic base", async () => {
    setup(); await open(); changeTitle("Новая редакция"); await waitFor(()=>expect(screen.getByRole("button", { name: "Сохранить черновик" })).toBeEnabled()); expect(screen.getByRole("button", { name: "Опубликовать версию" })).toBeDisabled(); fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));
    await waitFor(() => expect(createPersonnelOrderTemplateDraft).toHaveBeenCalledWith("TERMINATION", expect.objectContaining({ ...texts, title_ru: "Новая редакция", base_source: "PUBLISHED", base_published_template_version_id: 20, base_published_revision: 4 })));
    await waitFor(() => expect(screen.getByRole("button", { name: "Опубликовать версию" })).toBeEnabled());
  });

  it("server DRAFT continues only by click and blocks publish while dirty", async () => {
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(draft); setup(); await open("Продолжить редактирование");
    expect(screen.getByTestId("template-editor-application-notice")).toHaveTextContent("Эта версия не применяется к кадровым приказам.");
    expect(screen.getByTestId("template-draft-editor")).toHaveTextContent("Черновая версия шаблона");
    expect(screen.getByTestId("template-draft-editor")).not.toHaveTextContent("Несохранённая рабочая копия опубликованной версии");
    expect(screen.getByRole("button", { name: "Сохранить черновик" })).toBeDisabled(); expect(screen.getByRole("button", { name: "Опубликовать версию" })).toBeEnabled(); changeTitle("Ещё не сохранено"); expect(screen.getByRole("button", { name: "Опубликовать версию" })).toBeDisabled(); fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));
    await waitFor(() => expect(savePersonnelOrderTemplateDraft).toHaveBeenCalledWith("TERMINATION", expect.objectContaining({ expected_revision: 1, title_ru: "Ещё не сохранено" })));
  });

  it("shows current server-side spec variables instead of stale version metadata", async () => {
    const currentSpecVariables = [
      "employee.full_name_dative_ru", "employee.full_name_dative_kk", "employee.full_name_genitive_kk",
      "position.document_possessive_kk", "org_unit.document_genitive_kk",
      "leave.period_text_ru", "leave.period_text_kk", "leave.period_clause_ru", "leave.period_clause_kk",
    ];
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    vi.mocked(listPersonnelOrderTemplateCatalog).mockResolvedValue({ items: [{
      ...catalog.items[0],
      type_code: "LEAVE.UNPAID.GRANT",
      allowed_variables: currentSpecVariables,
      template_detail: {
        required_fields: [], additional_fields: [], document_parts: [],
        variables: [{ code: "legacy.version_metadata_only", label: "устаревшая metadata версии" }],
        specialty_note: "", previews: {
          ru: { title: "", preamble: "", directive: "", body: "", basis: "", footer: "" },
          kk: { title: "", preamble: "", directive: "", body: "", basis: "", footer: "" },
        },
      },
    }] });
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue({ ...draft, item_type_code: "LEAVE.UNPAID.GRANT" });
    vi.mocked(getPersonnelOrderTemplatePublished).mockResolvedValue({ ...published, item_type_code: "LEAVE.UNPAID.GRANT" });

    setup();
    await open("Продолжить редактирование");

    const allowed = screen.getByTestId("template-editor-allowed-variables");
    for (const variable of currentSpecVariables) expect(allowed).toHaveTextContent(variable);
    expect(allowed).not.toHaveTextContent("legacy.version_metadata_only");
  });

  it("identical actual DRAFT is visible but cannot publish", async () => {
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue({ ...published, template_version_id: 21, version_number: 3, status: "DRAFT", revision: 1 }); setup(); const editor = await open("Продолжить редактирование");
    expect(editor).toHaveTextContent("Черновик полностью совпадает с опубликованной версией и не может быть опубликован"); expect(screen.getByRole("button", { name: "Опубликовать версию" })).toBeDisabled(); expect(publishPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("INITIAL is read-only until click and allows an unchanged first save", async () => {
    vi.mocked(getPersonnelOrderTemplatePublished).mockResolvedValue(null); vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(null); vi.mocked(getPersonnelOrderTemplateEditorBase).mockResolvedValue(initialBase); setup(); const editor = await open();
    expect(editor).toHaveTextContent("Первая версия шаблона ещё не сохранена"); expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled(); expect(screen.getByRole("button", { name: "Сохранить черновик" })).toBeEnabled(); fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" })); await waitFor(() => expect(createPersonnelOrderTemplateDraft).toHaveBeenCalledWith("TERMINATION", expect.objectContaining({ ...texts, base_source: "INITIAL" })));
  });

  it("PUBLISHED absent plus DRAFT present opens the existing v1 without create", async () => {
    vi.mocked(getPersonnelOrderTemplatePublished).mockResolvedValue(null); vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue({ ...draft, version_number: 1 }); setup(); const editor = await open("Продолжить редактирование");
    expect(editor).toHaveTextContent("v1 · Нұсқа ID 21 · DRAFT · revision 1"); expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("publish re-reads PUBLISHED and null DRAFT and creates no successor", async () => {
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValueOnce(draft).mockResolvedValueOnce(draft).mockResolvedValue(null); vi.mocked(getPersonnelOrderTemplatePublished).mockResolvedValueOnce(published).mockResolvedValueOnce({ ...draft, status: "PUBLISHED" }); setup(); await open("Продолжить редактирование"); fireEvent.click(screen.getByRole("button", { name: "Опубликовать версию" }));
    await waitFor(() => expect(publishPersonnelOrderTemplateDraft).toHaveBeenCalledWith("TERMINATION", 1)); await waitFor(() => expect(screen.queryByTestId("template-draft-editor")).not.toBeInTheDocument()); expect(getPersonnelOrderTemplatePublished).toHaveBeenCalledTimes(2); expect(getPersonnelOrderTemplateDraft).toHaveBeenCalledTimes(3); expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it.each(["ru", "kk"] as const)("shows publication errors and a durable named confirmation in %s", async language => {
    vi.mocked(apiFetchJson).mockResolvedValue({language,can_edit:false});
    let completed=false;
    const scoped={...draft,template_id:101,template_version_id:1327,revision:4,version_number:1};
    const result={...scoped,status:"PUBLISHED"};
    vi.mocked(listPersonnelIndependentTemplates).mockImplementation(async()=>({items:[{template_id:101,item_type_code:"TERMINATION",name_ru:"Об отзыве из отпуска",name_kk:"Еңбек демалысынан шақырту туралы",is_default:false,template_version_id:completed?1327:null,draft_version_id:completed?null:1327}]}));
    vi.mocked(listPersonnelTemplateVersions).mockResolvedValue({items:[scoped]});
    vi.mocked(getPersonnelOrderTemplateDraft).mockImplementation(async()=>completed?null:scoped);
    vi.mocked(getPersonnelOrderTemplatePublished).mockImplementation(async()=>completed?result:null);
    vi.mocked(publishPersonnelOrderTemplateDraft).mockRejectedValueOnce({message:"Конфликт ревизии: обновите черновик."}).mockImplementation(async()=>{completed=true;return result;});
    currentSearch=new URLSearchParams("section=personnel-orders&type=TERMINATION&template_id=101");
    render(<PersonnelSectionLanguageProvider><TemplatesPageClient/></PersonnelSectionLanguageProvider>);
    await screen.findByTestId("template-draft-editor");
    fireEvent.click(screen.getByRole("button",{name:"Опубликовать версию"}));
    expect(await screen.findByText("Конфликт ревизии: обновите черновик.")).toBeVisible();
    expect(screen.getByLabelText("Заголовок RU")).toHaveValue(scoped.title_ru);
    fireEvent.click(screen.getByRole("button",{name:"Опубликовать версию"}));
    const notice=await screen.findByTestId("template-publication-success");
    expect(notice).toHaveTextContent(language==="kk"?"жарияланды":"опубликована");
    expect(notice).toHaveTextContent(language==="kk"?"Еңбек демалысынан шақырту туралы":"Об отзыве из отпуска");
    await screen.findByTestId("template-published-read-only");
    expect(screen.queryByTestId("template-draft-editor")).not.toBeInTheDocument();
    expect(savePersonnelOrderTemplateDraft).not.toHaveBeenCalled();
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("keeps typed values after a validation or stale-base error", async () => {
    vi.mocked(createPersonnelOrderTemplateDraft).mockRejectedValue({ status: 409, message: "Конфликт базы" }); setup(); await open(); changeTitle("Не потерять"); fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" })); expect(await screen.findByRole("alert")).toHaveTextContent("Конфликт базы"); expect(screen.getByLabelText("Заголовок RU")).toHaveValue("Не потерять");
  });

  it.each([404, 500])("shows a safe editor-base %i error without creating a DRAFT", async (status) => {
    vi.mocked(getPersonnelOrderTemplateEditorBase).mockRejectedValueOnce({ status, message: "internal backend detail" });
    setup();
    await screen.findByRole("button", { name: "Редактировать шаблон" });
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Не удалось открыть редактор. Повторите попытку.");
    expect(screen.queryByTestId("template-draft-editor")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Редактировать шаблон" })).toBeEnabled();
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("opens a WORKING_COPY when a retry succeeds after editor-base failure", async () => {
    vi.mocked(getPersonnelOrderTemplateEditorBase).mockRejectedValueOnce({ status: 500, message: "internal backend detail" }).mockResolvedValue(publishedBase);
    setup();
    await screen.findByRole("button", { name: "Редактировать шаблон" });
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Не удалось открыть редактор. Повторите попытку.");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByTestId("template-draft-editor")).toHaveTextContent("Несохранённая рабочая копия опубликованной версии 2");
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("restores paired textarea height for the current type without creating a DRAFT", async () => {
    window.localStorage.setItem("corpsite.personnel-order-template-draft-heights.v1:TERMINATION", JSON.stringify({ title: 150 }));
    setup(); await open();
    await waitFor(() => expect(screen.getByLabelText("Заголовок RU")).toHaveStyle({ height: "150px" }));
    expect(screen.getByLabelText("Заголовок KK")).toHaveStyle({ height: "150px" });
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("ignores a late PUBLISHED/DRAFT response from the previous type", async () => {
    let resolveOld: ((value: typeof published | null) => void) | undefined;
    const oldPublished = new Promise<typeof published | null>((resolve) => { resolveOld = resolve; });
    const hire = { ...published, item_type_code: "HIRE", title_ru: "Приём", version_number: 7 };
    vi.mocked(listPersonnelOrderTemplateCatalog).mockResolvedValue({ items: [...catalog.items, { ...catalog.items[0], type_code: "HIRE", title_ru: "Приём", title_kk: "Жұмысқа қабылдау" }] });
    vi.mocked(getPersonnelOrderTemplatePublished).mockImplementation((type) => type === "TERMINATION" ? oldPublished : Promise.resolve(hire));
    vi.mocked(getPersonnelOrderTemplateDraft).mockImplementation((type) => Promise.resolve(type === "HIRE" ? null : null));
    const view = setup(); await screen.findByRole("heading", { name: "Жұмыстан босату туралы" });
    currentSearch = new URLSearchParams("section=personnel-orders&type=HIRE"); view.rerender(<TemplatesPageClient />);
    expect(await screen.findByRole("heading", { name: "Жұмысқа қабылдау" })).toBeInTheDocument();
    resolveOld?.(published);
    await waitFor(() => expect(screen.getByTestId("personnel-order-template-detail")).toHaveTextContent("Жұмысқа қабылдау"));
    expect(screen.getByTestId("personnel-order-template-detail")).not.toHaveTextContent("Заголовок RU");
  });
});
