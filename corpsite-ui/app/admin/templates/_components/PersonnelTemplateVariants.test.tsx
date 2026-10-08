import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import PersonnelTemplateVariants from "./PersonnelTemplateVariants";
import { copyPersonnelTemplate, listPersonnelIndependentTemplates, listPersonnelTemplateVersions } from "../_lib/personnelOrderTemplatesApi.client";
import type { PersonnelOrderTemplateCatalogItem } from "../_lib/personnelOrderTemplatesApi.client";
vi.mock("../_lib/personnelOrderTemplatesApi.client", () => ({ copyPersonnelTemplate: vi.fn(), listPersonnelIndependentTemplates: vi.fn(), listPersonnelTemplateVersions: vi.fn() }));
const sectionLanguage = vi.hoisted(() => ({ language: "ru" as "ru" | "kk" }));
vi.mock("@/app/directory/personnel/_lib/personnelSectionLanguage", () => ({ usePersonnelSectionLanguage: () => ({...sectionLanguage,ready:true}) }));
afterEach(() => { cleanup(); vi.resetAllMocks(); sectionLanguage.language = "ru"; });
beforeEach(() => { Object.defineProperty(HTMLDialogElement.prototype, "showModal", { configurable: true, value: function () { this.setAttribute("open", ""); } }); vi.mocked(listPersonnelTemplateVersions).mockResolvedValue({items: []}); });

it("opens the existing default card when independent schema is not migrated and explains copying availability",async()=>{
  vi.mocked(listPersonnelIndependentTemplates).mockRejectedValue({status:503,details:{detail:{code:"TEMPLATE_SCHEMA_REQUIRED"}}});
  const editor=vi.fn((_id,_changed,actions)=><div>Existing template card{actions}</div>);
  render(<PersonnelTemplateVariants item={{type_code:"LEAVE.UNPAID.GRANT",editor_available:true} as PersonnelOrderTemplateCatalogItem} renderEditor={editor}/>);
  await screen.findByText("Existing template card");
  expect(editor).toHaveBeenCalledWith(undefined,expect.any(Function),expect.anything(),null,undefined,expect.anything(),undefined);
  expect(screen.getByRole("button",{name:"Создать на основе…",exact:true})).toBeDisabled();
  expect(screen.getByRole("status")).toHaveTextContent("hrrecall001");
  expect(listPersonnelTemplateVersions).not.toHaveBeenCalled();
});

it("shows a failed independent read explicitly without a permanent loading indicator or a wrong scoped card",async()=>{
  vi.mocked(listPersonnelIndependentTemplates).mockRejectedValue({status:500});
  const editor=vi.fn(()=>null);
  render(<PersonnelTemplateVariants item={{type_code:"LEAVE.ANNUAL.RECALL"} as PersonnelOrderTemplateCatalogItem} initialTemplateId={101} renderEditor={editor}/>);
  await screen.findByRole("alert");expect(screen.getByRole("alert")).toHaveTextContent("HTTP 500");
  expect(screen.queryByText("Загрузка шаблона…")).not.toBeInTheDocument();expect(editor).not.toHaveBeenCalled();
});

it("waits for template membership before requesting versions or opening the editor", async () => {
  let resolve!: (value: Awaited<ReturnType<typeof listPersonnelIndependentTemplates>>) => void;
  vi.mocked(listPersonnelIndependentTemplates).mockReturnValue(new Promise(done => {resolve = done;}));
  const editor=vi.fn(() => <div>Saved editor</div>);
  render(<PersonnelTemplateVariants item={{type_code:"LEAVE.ANNUAL.RECALL"} as PersonnelOrderTemplateCatalogItem} initialTemplateId={101} renderEditor={editor}/>);
  expect(listPersonnelTemplateVersions).not.toHaveBeenCalled(); expect(editor).not.toHaveBeenCalled();
  resolve({items:[{template_id:101,item_type_code:"LEAVE.ANNUAL.RECALL",name_ru:"Отзыв",name_kk:"Шақырту",is_default:false,template_version_id:null,draft_version_id:1327}]});
  await waitFor(() => expect(listPersonnelTemplateVersions).toHaveBeenCalledWith("LEAVE.ANNUAL.RECALL",101));
  expect(editor).toHaveBeenCalledWith(101,expect.any(Function),expect.anything(),null,undefined,expect.anything(),expect.objectContaining({template_id:101}));
});

it("clears a stale template id belonging to a different type before any scoped API read", async () => {
  vi.mocked(listPersonnelIndependentTemplates).mockResolvedValue({items:[{template_id:52,item_type_code:"LEAVE.ANNUAL.GRANT",name_ru:"Трудовой отпуск",name_kk:"Еңбек демалысы",is_default:true,template_version_id:null,draft_version_id:null}]});
  const selected=vi.fn(); const editor=vi.fn(() => <div>Annual editor</div>);
  render(<PersonnelTemplateVariants item={{type_code:"LEAVE.ANNUAL.GRANT"} as PersonnelOrderTemplateCatalogItem} initialTemplateId={101} onSelected={selected} renderEditor={editor}/>);
  await waitFor(() => expect(listPersonnelTemplateVersions).toHaveBeenCalledWith("LEAVE.ANNUAL.GRANT",52));
  expect(listPersonnelTemplateVersions).not.toHaveBeenCalledWith("LEAVE.ANNUAL.GRANT",101);
  expect(selected).toHaveBeenCalledWith(52);expect(editor.mock.calls.every(args => args[0] !== 101)).toBe(true);
});

it("updates the exact copy caption only from the shared section language while keeping the selected source and entered names", async () => {
  vi.mocked(listPersonnelIndependentTemplates).mockResolvedValue({ items: [] });
  const item = { type_code: "HIRE", title_ru: "Русское содержание", title_kk: "Қазақша мазмұн" } as PersonnelOrderTemplateCatalogItem;
  const renderEditor = (_id: number | undefined, _changed: () => void, actions: React.ReactNode, form: React.ReactNode) => <div>{actions}{form}</div>;
  const view = render(<PersonnelTemplateVariants item={item} renderEditor={renderEditor} />);
  await waitFor(() => expect(screen.getByRole("button", { name: "Создать на основе…", exact: true })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Создать на основе…", exact: true }));
  fireEvent.change(screen.getByLabelText("Название нового шаблона на русском"), { target: { value: "Русский вариант" } });
  fireEvent.change(screen.getByLabelText("Название нового шаблона на казахском"), { target: { value: "Қазақша нұсқа" } });
  sectionLanguage.language = "kk";
  view.rerender(<PersonnelTemplateVariants item={{ ...item, title_ru: "Other content", title_kk: "Other content" }} renderEditor={renderEditor} />);
  expect(screen.getByRole("button", { name: "Негізінде жасау…", exact: true })).toBeEnabled();
  expect(screen.getByLabelText("Жаңа үлгінің орысша атауы")).toHaveValue("Русский вариант");
  expect(screen.getByLabelText("Жаңа үлгінің қазақша атауы")).toHaveValue("Қазақша нұсқа");
  sectionLanguage.language = "ru";
  view.rerender(<PersonnelTemplateVariants item={item} renderEditor={renderEditor} />);
  expect(screen.getByRole("button", { name: "Создать на основе…", exact: true })).toBeEnabled();
  expect(copyPersonnelTemplate).not.toHaveBeenCalled();
});
it("copies the selected version with separate variant names and selects the independent draft", async () => {
  vi.mocked(listPersonnelIndependentTemplates).mockResolvedValue({ items: [{ template_id: 1, item_type_code: "HIRE", name_ru: "Original", name_kk: "Original KZ", is_default: true, template_version_id: 20, draft_version_id: null }] });
  vi.mocked(listPersonnelTemplateVersions).mockResolvedValue({ items: [{ template_version_id: 20, version_number: 2, revision: 3, status: "PUBLISHED" }, { template_version_id: 10, version_number: 1, revision: 1, status: "ARCHIVED" }] as never });
  vi.mocked(copyPersonnelTemplate).mockResolvedValue({ template_id: 2, template_version_id: 30 } as never);
  render(<PersonnelTemplateVariants item={{ type_code: "HIRE" } as PersonnelOrderTemplateCatalogItem} renderEditor={(id, changed, actions, form) => <div><p>Editor {id}</p>{actions}{form}</div>} />);
  await waitFor(() => expect(screen.getByRole("button", { name: "Создать на основе…" })).toBeEnabled());
  fireEvent.change(await screen.findByLabelText("Исходная версия"), { target: { value: "10" } });
  fireEvent.click(screen.getByRole("button", { name: "Создать на основе…" }));
  fireEvent.change(screen.getByLabelText("Название нового шаблона на русском"), { target: { value: "Copy" } });
  fireEvent.change(screen.getByLabelText("Название нового шаблона на казахском"), { target: { value: "Copy KZ" } });
  await waitFor(() => expect(screen.getByRole("button", { name: "Создать и редактировать" })).toBeEnabled()); fireEvent.click(screen.getByRole("button", { name: "Создать и редактировать" }));
  await waitFor(() => expect(copyPersonnelTemplate).toHaveBeenCalledWith("HIRE", { source_version_id: 10, expected_revision: 1, name_ru: "Copy", name_kk: "Copy KZ" }));
  await screen.findByText("Editor 2");
});

it("offers an independent copy of a built-in template without saving the source first", async () => {
  vi.mocked(listPersonnelIndependentTemplates).mockResolvedValue({ items: [] });
  vi.mocked(listPersonnelTemplateVersions).mockResolvedValue({ items: [] });
  vi.mocked(copyPersonnelTemplate).mockResolvedValue({ template_id: 2, template_version_id: 30 } as never);
  render(<PersonnelTemplateVariants item={{ type_code: "TRANSFER" } as PersonnelOrderTemplateCatalogItem}
    renderEditor={(id, changed, actions, form) => <div>{actions}{form}</div>} />);
  await waitFor(() => expect(screen.getByRole("button", { name: "Создать на основе…" })).toBeEnabled());
  expect(screen.getByText("Исходная основа: встроенный шаблон")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Создать на основе…" }));
  fireEvent.change(screen.getByLabelText("Название нового шаблона на русском"), { target: { value: "Copy" } });
  fireEvent.change(screen.getByLabelText("Название нового шаблона на казахском"), { target: { value: "Copy KZ" } });
  await waitFor(() => expect(screen.getByRole("button", { name: "Создать и редактировать" })).toBeEnabled()); fireEvent.click(screen.getByRole("button", { name: "Создать и редактировать" }));
  await waitFor(() => expect(copyPersonnelTemplate).toHaveBeenCalledWith("TRANSFER", { base_source: "INITIAL", name_ru: "Copy", name_kk: "Copy KZ" }));
});

it.each(["ru", "kk"] as const)("localizes the complete copy dialog and error in %s", async language => {
  sectionLanguage.language = language;
  vi.mocked(listPersonnelIndependentTemplates).mockResolvedValue({ items: [] });
  vi.mocked(copyPersonnelTemplate).mockRejectedValue(new Error("internal backend error"));
  render(<PersonnelTemplateVariants item={{ type_code: "HIRE", title_ru: "Приём", title_kk: "Қабылдау" } as PersonnelOrderTemplateCatalogItem}
    renderEditor={(_id, _changed, actions, form) => <>{actions}{form}</>} />);
  const kk = language === "kk";
  const button = screen.getByRole("button", { name: kk ? "Негізінде жасау…" : "Создать на основе…" });
  await waitFor(() => expect(button).toBeEnabled()); fireEvent.click(screen.getByRole("button", { name: kk ? "Негізінде жасау…" : "Создать на основе…" }));
  expect(await screen.findByRole("dialog", { name: kk ? "Үлгі негізінде жасау" : "Создать на основе шаблона" })).toBeVisible();
  await waitFor(() => expect(screen.getByLabelText(kk ? "Бастапқы үлгі" : "Исходный шаблон")).toBeEnabled());
  fireEvent.change(screen.getByLabelText(kk ? "Жаңа үлгінің орысша атауы" : "Название нового шаблона на русском"), { target: { value: "Название" } });
  fireEvent.change(screen.getByLabelText(kk ? "Жаңа үлгінің қазақша атауы" : "Название нового шаблона на казахском"), { target: { value: "Атауы" } });
  await waitFor(() => expect(screen.getByRole("button", { name: kk ? "Жасау және өңдеу" : "Создать и редактировать" })).toBeEnabled()); fireEvent.click(screen.getByRole("button", { name: kk ? "Жасау және өңдеу" : "Создать и редактировать" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(kk ? "көшірме жасау мүмкін болмады" : "Не удалось загрузить шаблоны или создать копию");
  expect(screen.getByRole("button", { name: kk ? "Бас тарту" : "Отмена" })).toBeEnabled();
  expect(screen.queryByText("internal backend error")).not.toBeInTheDocument();
});
