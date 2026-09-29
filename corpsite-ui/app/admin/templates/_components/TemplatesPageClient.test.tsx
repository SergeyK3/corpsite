import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TemplatesPageClient from "./TemplatesPageClient";
import { createPersonnelOrderTemplateDraft, getPersonnelOrderTemplateDraft, getPersonnelOrderTemplateEditorBase, getPersonnelOrderTemplatePublished, listPersonnelOrderTemplateCatalog, publishPersonnelOrderTemplateDraft, savePersonnelOrderTemplateDraft } from "../_lib/personnelOrderTemplatesApi.client";

let currentSearch = new URLSearchParams("section=personnel-orders&type=TERMINATION");
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), useSearchParams: () => currentSearch }));
vi.mock("@/app/regular-tasks/_components/RegularTasksAdminClient", () => ({ default: () => null }));
vi.mock("../_lib/personnelOrderTemplatesApi.client", () => ({ listPersonnelOrderTemplateCatalog: vi.fn(), getPersonnelOrderTemplateDraft: vi.fn(), getPersonnelOrderTemplatePublished: vi.fn(), getPersonnelOrderTemplateEditorBase: vi.fn(), createPersonnelOrderTemplateDraft: vi.fn(), savePersonnelOrderTemplateDraft: vi.fn(), previewPersonnelOrderTemplateDraft: vi.fn(), publishPersonnelOrderTemplateDraft: vi.fn() }));

const texts = { title_ru: "Заголовок RU", title_kk: "Тақырып KK", preamble_ru: "Преамбула RU", preamble_kk: "Преамбула KK", body_template_ru: "{{employee.full_name}}", body_template_kk: "{{employee.full_name}}", basis_template_ru: "Основание", basis_template_kk: "Негіз" };
const published = { ...texts, template_version_id: 20, item_type_code: "TERMINATION", version_number: 2, revision: 4, status: "PUBLISHED", based_on_built_in: true };
const draft = { ...texts, title_ru: "Изменённый заголовок", template_version_id: 21, item_type_code: "TERMINATION", version_number: 3, revision: 1, status: "DRAFT", based_on_built_in: true };
const catalog = { items: [{ type_code: "TERMINATION", title_ru: "Об увольнении", title_kk: "Жұмыстан босату туралы", source: "BUILT_IN" as const, support_level: "SUPPORTED" as const, supported_locales: ["ru", "kk"], uses_specialized_generator: true, is_pilot: false, editor_available: true, required_fields: [], notes: "", pilot_detail: null, template_detail: null }] };
const publishedBase = { ...texts, source: "PUBLISHED" as const, item_type_code: "TERMINATION", template_version_id: 20, version_number: 2, revision: 4 };
const initialBase = { ...texts, source: "INITIAL" as const, item_type_code: "TERMINATION", template_version_id: null, version_number: null, revision: null };
const setup = () => render(<TemplatesPageClient />);
const open = async (label = "Редактировать шаблон") => { await screen.findByRole("button", { name: label }); fireEvent.click(screen.getByRole("button", { name: label })); return screen.findByTestId("template-draft-editor"); };
const changeTitle = (value: string) => fireEvent.change(screen.getByLabelText("Заголовок RU"), { target: { value } });

describe("TemplatesPageClient draft lifecycle", () => {
  beforeEach(() => {
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

  it("mount and reload request PUBLISHED and DRAFT only", async () => {
    const view = setup(); await screen.findByTestId("template-published-read-only");
    expect(getPersonnelOrderTemplatePublished).toHaveBeenCalledWith("TERMINATION"); expect(getPersonnelOrderTemplateDraft).toHaveBeenCalledWith("TERMINATION"); expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
    view.unmount(); setup(); await screen.findByTestId("template-published-read-only"); expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("opens a PUBLISHED working copy without POST, without draftExists, and with disabled actions", async () => {
    setup(); const editor = await open();
    expect(editor).toHaveTextContent("Несохранённая рабочая копия опубликованной версии 2"); expect(editor).not.toHaveTextContent("revision 0"); expect(screen.getByLabelText("Заголовок RU")).toHaveValue(texts.title_ru);
    expect(screen.getByTestId("template-published-read-only")).not.toHaveTextContent("Имеется черновик следующей версии"); expect(screen.getByRole("button", { name: "Сохранить черновик" })).toBeDisabled(); expect(screen.getByRole("button", { name: "Опубликовать версию" })).toBeDisabled(); expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("first changed save sends all text with typed PUBLISHED optimistic base", async () => {
    setup(); await open(); changeTitle("Новая редакция"); expect(screen.getByRole("button", { name: "Сохранить черновик" })).toBeEnabled(); expect(screen.getByRole("button", { name: "Опубликовать версию" })).toBeDisabled(); fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));
    await waitFor(() => expect(createPersonnelOrderTemplateDraft).toHaveBeenCalledWith("TERMINATION", expect.objectContaining({ ...texts, title_ru: "Новая редакция", base_source: "PUBLISHED", base_published_template_version_id: 20, base_published_revision: 4 })));
    await waitFor(() => expect(screen.getByRole("button", { name: "Опубликовать версию" })).toBeEnabled());
  });

  it("server DRAFT continues only by click and blocks publish while dirty", async () => {
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(draft); setup(); await open("Продолжить редактирование");
    expect(screen.getByRole("button", { name: "Сохранить черновик" })).toBeDisabled(); expect(screen.getByRole("button", { name: "Опубликовать версию" })).toBeEnabled(); changeTitle("Ещё не сохранено"); expect(screen.getByRole("button", { name: "Опубликовать версию" })).toBeDisabled(); fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));
    await waitFor(() => expect(savePersonnelOrderTemplateDraft).toHaveBeenCalledWith("TERMINATION", expect.objectContaining({ expected_revision: 1, title_ru: "Ещё не сохранено" })));
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
    expect(editor).toHaveTextContent("Версия 1 · revision 1 · DRAFT"); expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("publish re-reads PUBLISHED and null DRAFT and creates no successor", async () => {
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValueOnce(draft).mockResolvedValueOnce(draft).mockResolvedValue(null); vi.mocked(getPersonnelOrderTemplatePublished).mockResolvedValueOnce(published).mockResolvedValueOnce({ ...draft, status: "PUBLISHED" }); setup(); await open("Продолжить редактирование"); fireEvent.click(screen.getByRole("button", { name: "Опубликовать версию" }));
    await waitFor(() => expect(publishPersonnelOrderTemplateDraft).toHaveBeenCalledWith("TERMINATION", 1)); await waitFor(() => expect(screen.queryByTestId("template-draft-editor")).not.toBeInTheDocument()); expect(getPersonnelOrderTemplatePublished).toHaveBeenCalledTimes(2); expect(getPersonnelOrderTemplateDraft).toHaveBeenCalledTimes(3); expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("keeps typed values after a validation or stale-base error", async () => {
    vi.mocked(createPersonnelOrderTemplateDraft).mockRejectedValue({ status: 409, message: "Конфликт базы" }); setup(); await open(); changeTitle("Не потерять"); fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" })); expect(await screen.findByRole("alert")).toHaveTextContent("Конфликт базы"); expect(screen.getByLabelText("Заголовок RU")).toHaveValue("Не потерять");
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
    const view = setup(); await screen.findByRole("heading", { name: "Об увольнении" });
    currentSearch = new URLSearchParams("section=personnel-orders&type=HIRE"); view.rerender(<TemplatesPageClient />);
    expect(await screen.findByRole("heading", { name: "Приём" })).toBeInTheDocument();
    resolveOld?.(published);
    await waitFor(() => expect(screen.getByTestId("personnel-order-template-detail")).toHaveTextContent("Приём"));
    expect(screen.getByTestId("personnel-order-template-detail")).not.toHaveTextContent("Заголовок RU");
  });
});
