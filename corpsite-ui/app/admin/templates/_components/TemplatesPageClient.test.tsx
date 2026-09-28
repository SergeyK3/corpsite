import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TemplatesPageClient from "./TemplatesPageClient";
import { createPersonnelOrderTemplateDraft, getPersonnelOrderTemplateDraft, listPersonnelOrderTemplateCatalog, previewPersonnelOrderTemplateDraft, savePersonnelOrderTemplateDraft } from "../_lib/personnelOrderTemplatesApi.client";

let currentSearch = new URLSearchParams();
const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
  useSearchParams: () => currentSearch,
}));

vi.mock("@/app/regular-tasks/_components/RegularTasksAdminClient", () => ({
  default: ({ embedded }: { embedded?: boolean }) => (
    <div data-testid="reused-regular-task-templates" data-embedded={String(embedded)}>
      Существующий интерфейс регулярных задач
    </div>
  ),
}));
vi.mock("../_lib/personnelOrderTemplatesApi.client", () => ({ listPersonnelOrderTemplateCatalog: vi.fn(), getPersonnelOrderTemplateDraft: vi.fn(), createPersonnelOrderTemplateDraft: vi.fn(), savePersonnelOrderTemplateDraft: vi.fn(), previewPersonnelOrderTemplateDraft: vi.fn() }));

const pilotDetail = {
  required_fields: ["ФИО сотрудника", "Должность на русском языке", "Дата выхода на работу"],
  additional_fields: [],
  document_parts: ["Заголовок", "Преамбула", "ПРИКАЗЫВАЮ: / БҰЙЫРАМЫН:", "Основание", "Печатный подвал"],
  variables: [{ code: "employee.full_name", label: "ФИО сотрудника" }],
  specialty_note: "Специальность хранится отдельно и в тело этого приказа не включается.",
  previews: {
    ru: {
      title: "О выходе на работу из отпуска по уходу за ребёнком",
      preamble: "В соответствии с законодательством Республики Казахстан",
      directive: "ПРИКАЗЫВАЮ:",
      body: "«ФИО сотрудника» приступить к работе в должности «Должность» подразделения «Подразделение» на «Ставка» ставки с «Дата выхода».",
      basis: "Основание: Личное заявление.",
      footer: "С приказом ознакомлен(а): ___________________ [Фамилия И.]\n«___» ______________ 20___ г.\nИсполнитель: [Инициалы и фамилия исполнителя]",
    },
    kk: {
      title: "Бала күтіміне байланысты демалыстан жұмысқа шығу туралы",
      preamble: "Қазақстан Республикасының заңнамасына сәйкес",
      directive: "БҰЙЫРАМЫН:",
      body: "«Қызметкердің аты-жөні» «Лауазым» лауазымында «Бөлімше» бөлімшесінде «Мөлшерлеме» мөлшерлемемен «Жұмысқа шығу күні» бастап жұмысқа кіріссін.",
      basis: "Негіз: Жеке өтініші.",
      footer: "Бұйрықпен таныстым: ___________________ [Тегі А.]\n«___» ______________ 20___ ж.\nОрындаушы: [Орындаушының аты-жөні]",
    },
  },
};

const unpaidDetail = {
  required_fields: ["ФИО сотрудника", "Дата начала отпуска", "Дата окончания отпуска", "Вычисляемое количество календарных дней", "Личное заявление"],
  additional_fields: ["Дата заявления (если известна)", "Номер заявления (если известен)"],
  document_parts: [],
  variables: [{ code: "leave.days", label: "Количество календарных дней" }, { code: "basis.application_date_ru", label: "Дата личного заявления на русском языке" }],
  specialty_note: "Ставка, специальность, сведения о ребёнке и рабочий период ежегодного отпуска в этот шаблон не включаются.",
  previews: {
    ru: {
      title: "О предоставлении отпуска без сохранения заработной платы",
      preamble: "В соответствии с Трудовым кодексом Республики Казахстан",
      directive: "ПРИКАЗЫВАЮ:",
      body: "Предоставить «ФИО сотрудника», Должность подразделения «Подразделение», отпуск без сохранения заработной платы с 15 января 2026 года по 17 января 2026 года включительно продолжительностью 3 календарных дней.",
      basis: "Основание: личное заявление от 10 января 2026 года № 15.",
      footer: "С приказом ознакомлен(а): ___________________ [Фамилия И.]\n«___» ______________ 20___ г.\nИсполнитель: [Инициалы и фамилия исполнителя]",
    },
    kk: {
      title: "Жалақы сақталмайтын демалыс беру туралы",
      preamble: "Қазақстан Республикасының Еңбек кодексіне сәйкес",
      directive: "БҰЙЫРАМЫН:",
      body: "«Қызметкердің аты-жөні», «Бөлімше» бөлімшесінің «Лауазым» қызметкеріне 2026 жылғы 15 қаңтар мен 2026 жылғы 17 қаңтар аралығындағы 3 күнтізбелік күнге жалақы сақталмайтын демалыс берілсін.",
      basis: "Негіз: 2026 жылғы 10 қаңтар күнгі жеке өтініш № 15.",
      footer: "Бұйрықпен таныстым: ___________________ [Тегі А.]\n«___» ______________ 20___ ж.\nОрындаушы: [Орындаушының аты-жөні]",
    },
  },
};

const unpaidDraft = {
  template_version_id: 7, item_type_code: "LEAVE.UNPAID.GRANT", version_number: 1, status: "DRAFT", revision: 1, based_on_built_in: true,
  title_ru: "Заголовок RU", title_kk: "Тақырып KK", preamble_ru: "Преамбула RU", preamble_kk: "Преамбула KK",
  body_template_ru: "{{employee.full_name}} {{position.title_ru}} {{org_unit.title_ru}} {{leave.start_ru}} {{leave.end_ru}} {{leave.days}}",
  body_template_kk: "{{employee.full_name}} {{position.title_kk}} {{org_unit.title_kk}} {{leave.start_kk}} {{leave.end_kk}} {{leave.days}}",
  basis_template_ru: "Основание: {{basis.application_date_ru}}", basis_template_kk: "Негіз: {{basis.application_date_kk}}",
};

const draftPreview = {
  previews: {
    ru: { title: "Просмотр RU", preamble: "Преамбула RU", directive: "ПРИКАЗЫВАЮ:", body: "Текст RU", basis: "Основание: Личное заявление.", footer: "" },
    kk: { title: "Қарау KK", preamble: "Кіріспе KK", directive: "БҰЙЫРАМЫН:", body: "Мәтін KK", basis: "Негіз: Жеке өтініш.", footer: "" },
  },
};

describe("TemplatesPageClient", () => {
  beforeEach(() => {
    currentSearch = new URLSearchParams();
    push.mockReset();
    vi.mocked(getPersonnelOrderTemplateDraft).mockReset();
    vi.mocked(createPersonnelOrderTemplateDraft).mockReset();
    vi.mocked(savePersonnelOrderTemplateDraft).mockReset();
    vi.mocked(previewPersonnelOrderTemplateDraft).mockReset();
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(null);
    vi.mocked(createPersonnelOrderTemplateDraft).mockResolvedValue(unpaidDraft);
    vi.mocked(savePersonnelOrderTemplateDraft).mockResolvedValue({ ...unpaidDraft, revision: 2 });
    vi.mocked(previewPersonnelOrderTemplateDraft).mockResolvedValue(draftPreview);
    vi.mocked(listPersonnelOrderTemplateCatalog).mockResolvedValue({ items: [{
      type_code: "RETURN_FROM_CHILDCARE_LEAVE",
      title_ru: "О выходе на работу из отпуска по уходу за ребёнком",
      title_kk: "Бала күтіміне байланысты демалыстан жұмысқа шығу туралы",
      source: "BUILT_IN",
      support_level: "SUPPORTED",
      supported_locales: ["ru", "kk"],
      uses_specialized_generator: true,
      is_pilot: true,
      editor_available: true,
      required_fields: [],
      notes: "Не формализованы",
      pilot_detail: pilotDetail,
      template_detail: null,
    }, {
      type_code: "LEAVE.UNPAID.GRANT",
      title_ru: "О предоставлении отпуска без сохранения заработной платы",
      title_kk: "Жалақы сақталмайтын демалыс беру туралы",
      source: "BUILT_IN",
      support_level: "SUPPORTED",
      supported_locales: ["ru", "kk"],
      uses_specialized_generator: true,
      is_pilot: false,
      editor_available: true,
      required_fields: unpaidDetail.required_fields,
      notes: "Формализованный read-only шаблон.",
      pilot_detail: null,
      template_detail: unpaidDetail,
    }, {
      type_code: "HIRE",
      title_ru: "Приём на работу",
      title_kk: "Жұмысқа қабылдау",
      source: "BUILT_IN",
      support_level: "SUPPORTED",
      supported_locales: ["ru", "kk"],
      uses_specialized_generator: true,
      is_pilot: false,
      editor_available: false,
      required_fields: [],
      notes: "Без редактора.",
      pilot_detail: null,
      template_detail: null,
    }] });
  });

  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

  it("opens task templates by default and reuses the regular task component", () => {
    render(<TemplatesPageClient />);

    expect(screen.getByRole("heading", { name: "Шаблоны" })).toBeInTheDocument();
    expect(screen.getByTestId("task-templates-section")).toBeInTheDocument();
    expect(screen.getByTestId("reused-regular-task-templates")).toHaveAttribute("data-embedded", "true");
    expect(screen.getByRole("button", { name: "Шаблоны задач" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "Шаблоны задач" })).toHaveClass("bg-blue-700");
    expect(screen.queryByTestId("personnel-order-templates-empty-state")).not.toBeInTheDocument();
  });

  it("shows the personnel order templates catalogue for its direct URL", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders");
    render(<TemplatesPageClient />);

    expect(await screen.findByTestId("personnel-order-templates-catalog")).toHaveTextContent("RETURN_FROM_CHILDCARE_LEAVE");
    expect(screen.queryByTestId("reused-regular-task-templates")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Шаблоны кадровых приказов" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "Шаблоны кадровых приказов" })).toHaveClass("bg-blue-700");
  });

  it("renders the pilot's bilingual read-only preview from a direct type URL", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=RETURN_FROM_CHILDCARE_LEAVE");
    render(<TemplatesPageClient />);

    expect(await screen.findByTestId("personnel-order-template-detail")).toHaveTextContent("Реквизиты этого шаблона");
    expect(screen.getByTestId("personnel-order-common-requirements")).toHaveTextContent("Общие требования к кадровым приказам");
    expect(screen.getByText("Специальность хранится отдельно и в тело этого приказа не включается.")).toBeInTheDocument();
    const ru = screen.getByTestId("pilot-preview-ru");
    const kk = screen.getByTestId("pilot-preview-kk");
    expect(ru).toHaveTextContent("ПРИКАЗЫВАЮ:");
    expect(kk).toHaveTextContent("БҰЙЫРАМЫН:");
    expect(ru).toHaveTextContent("«ФИО сотрудника»");
    expect(ru).toHaveTextContent("«Должность»");
    expect(ru).toHaveTextContent("«Подразделение»");
    expect(ru).toHaveTextContent("«Дата выхода»");
    expect(ru).toHaveTextContent("«Ставка»");
    expect(kk).toHaveTextContent("«Қызметкердің аты-жөні»");
    expect(kk).toHaveTextContent("«Лауазым»");
    expect(kk).toHaveTextContent("«Бөлімше»");
    expect(kk).toHaveTextContent("«Жұмысқа шығу күні»");
    expect(kk).toHaveTextContent("«Мөлшерлеме»");
    expect(`${ru.textContent} ${kk.textContent}`).not.toMatch(/15 января 2026|2026 жылғы 15 қаңтар|1\.0/);
    expect(ru).toHaveTextContent("Основание: Личное заявление.");
    expect(kk).toHaveTextContent("Негіз: Жеке өтініші.");
    expect(ru).toHaveTextContent("«___» ______________ 20___ г.");
    expect(kk).toHaveTextContent("«___» ______________ 20___ ж.");
    expect(ru).toHaveTextContent("Исполнитель: [Инициалы и фамилия исполнителя]");
    expect(kk).toHaveTextContent("Орындаушы: [Орындаушының аты-жөні]");
    expect(ru.textContent?.match(/Основание:/g)).toHaveLength(1);
    expect(kk.textContent?.match(/Негіз:/g)).toHaveLength(1);
    expect(`${ru.textContent} ${kk.textContent}`).not.toMatch(/стаж|контроль|docx/i);
    expect(ru).not.toHaveTextContent("сотруднику Сотрудник");
    expect(kk).not.toHaveTextContent("Сотрудникға");
    expect(screen.getByRole("heading", { name: "Реквизиты этого шаблона" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Переменные шаблона" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Предварительный просмотр" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Состав документа" })).not.toBeInTheDocument();
    const variableLine = screen.getByText("employee.full_name:").parentElement;
    expect(variableLine).toHaveTextContent("employee.full_name: ФИО сотрудника");
    expect(variableLine).toHaveClass("flex", "flex-wrap");
  });

  it("renders the unpaid leave detail with one separate basis and no closing block", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    render(<TemplatesPageClient />);

    const detail = await screen.findByTestId("personnel-order-template-detail");
    expect(detail).toHaveTextContent("Реквизиты этого шаблона");
    expect(detail).toHaveTextContent("Дата заявления (если известна)");
    const ru = screen.getByTestId("pilot-preview-ru");
    const kk = screen.getByTestId("pilot-preview-kk");
    expect(ru).toHaveTextContent("ПРИКАЗЫВАЮ:");
    expect(kk).toHaveTextContent("БҰЙЫРАМЫН:");
    expect(ru).toHaveTextContent("Основание: личное заявление от 10 января 2026 года № 15.");
    expect(kk).toHaveTextContent("Негіз: 2026 жылғы 10 қаңтар күнгі жеке өтініш № 15.");
    expect(kk).toHaveTextContent("17 қаңтар аралығындағы 3 күнтізбелік күнге");
    expect(ru.textContent?.match(/Основание:/g)).toHaveLength(1);
    expect(kk.textContent?.match(/Негіз:/g)).toHaveLength(1);
    expect(`${ru.textContent} ${kk.textContent}`).not.toMatch(/контроль|ставка|специальность|ребён/i);
    expect(screen.queryByRole("button", { name: /опубликовать|архивировать/i })).not.toBeInTheDocument();
  });

  it("writes the selected section to the URL while preserving other query parameters", () => {
    currentSearch = new URLSearchParams("view=compact&section=tasks");
    render(<TemplatesPageClient />);

    fireEvent.click(screen.getByRole("button", { name: "Шаблоны кадровых приказов" }));

    expect(push).toHaveBeenCalledWith("/admin/templates?view=compact&section=personnel-orders");
  });

  it("restores the active section when browser navigation changes search params", () => {
    const { rerender } = render(<TemplatesPageClient />);
    expect(screen.getByTestId("task-templates-section")).toBeInTheDocument();

    currentSearch = new URLSearchParams("section=personnel-orders");
    rerender(<TemplatesPageClient />);
    expect(screen.getByTestId("personnel-order-templates-catalog")).toBeInTheDocument();

    currentSearch = new URLSearchParams("section=tasks");
    rerender(<TemplatesPageClient />);
    expect(screen.getByTestId("task-templates-section")).toBeInTheDocument();
  });

  it("offers the draft editor for the childcare-return template", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=RETURN_FROM_CHILDCARE_LEAVE");
    vi.mocked(createPersonnelOrderTemplateDraft).mockResolvedValue({ ...unpaidDraft, item_type_code: "RETURN_FROM_CHILDCARE_LEAVE" });
    render(<TemplatesPageClient />);
    await screen.findByTestId("personnel-order-template-detail");
    const button = screen.getByRole("button", { name: "Редактировать шаблон" });
    expect(button).toHaveClass("bg-blue-700", "text-white", "rounded-lg");
    fireEvent.click(button);
    await waitFor(() => expect(createPersonnelOrderTemplateDraft).toHaveBeenCalledWith("RETURN_FROM_CHILDCARE_LEAVE"));
    const editor = await screen.findByTestId("template-draft-editor");
    expect(editor).toHaveTextContent("Русский");
    expect(editor).toHaveTextContent("Қазақша");
  });

  it("does not offer the editor button for an unsupported template", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=HIRE");
    render(<TemplatesPageClient />);
    await screen.findByTestId("personnel-order-template-detail");
    expect(screen.queryByRole("button", { name: "Редактировать шаблон" })).not.toBeInTheDocument();
  });

  it("offers the draft editor only for unpaid leave and preserves unsaved bilingual text through preview", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    expect(screen.getByRole("button", { name: "Редактировать шаблон" })).toHaveClass("bg-blue-700", "text-white", "rounded-lg");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    await waitFor(() => expect(createPersonnelOrderTemplateDraft).toHaveBeenCalledWith("LEAVE.UNPAID.GRANT"));

    expect(await screen.findByTestId("template-draft-editor")).toHaveTextContent("Черновик не применяется к кадровым приказам.");
    expect(screen.getByLabelText("Заголовок RU")).toHaveValue("Заголовок RU");
    expect(screen.getByLabelText("Заголовок KK")).toHaveValue("Тақырып KK");
    expect(screen.getByTestId("template-draft-language-ru")).toHaveTextContent("Русский");
    expect(screen.getByTestId("template-draft-language-kk")).toHaveTextContent("Қазақша");
    const bilingualFields = screen.getByTestId("template-draft-fields");
    expect(bilingualFields).toHaveClass("grid-cols-1", "md:grid-cols-2");
    expect(Array.from(bilingualFields.children).map((child) => child.getAttribute("data-testid"))).toEqual([
      "template-draft-language-ru", "template-draft-language-kk",
      "template-draft-field-title_ru", "template-draft-field-title_kk",
      "template-draft-field-preamble_ru", "template-draft-field-preamble_kk",
      "template-draft-field-body_template_ru", "template-draft-field-body_template_kk",
      "template-draft-field-basis_template_ru", "template-draft-field-basis_template_kk",
    ]);
    ([
      ["title_ru", "title_kk", "h-16"],
      ["preamble_ru", "preamble_kk", "h-28"],
      ["body_template_ru", "body_template_kk", "h-48"],
      ["basis_template_ru", "basis_template_kk", "h-28"],
    ] as const).forEach(([ru, kk, heightClass]) => {
      const ruField = screen.getByTestId(`template-draft-field-${ru}`);
      const kkField = screen.getByTestId(`template-draft-field-${kk}`);
      expect(ruField).toHaveClass("min-w-0");
      expect(kkField).toHaveClass("min-w-0");
      expect(ruField.querySelector("textarea")).toHaveClass(heightClass, "resize-y");
      expect(kkField.querySelector("textarea")).toHaveClass(heightClass, "resize-none");
    });
    expect(screen.getByLabelText("Преамбула RU")).toHaveValue(unpaidDraft.preamble_ru);
    expect(screen.getByLabelText("Преамбула KK")).toHaveValue(unpaidDraft.preamble_kk);
    expect(screen.getByLabelText("Распорядительный текст RU")).toHaveValue(unpaidDraft.body_template_ru);
    expect(screen.getByLabelText("Распорядительный текст KK")).toHaveValue(unpaidDraft.body_template_kk);
    expect(screen.getByLabelText("Основание RU")).toHaveValue(unpaidDraft.basis_template_ru);
    expect(screen.getByLabelText("Основание KK")).toHaveValue(unpaidDraft.basis_template_kk);
    expect(screen.queryByRole("button", { name: /Опубликовать/i })).not.toBeInTheDocument();
    expect(screen.getByTestId("template-draft-actions")).toHaveClass("border-t", "pt-3");
    expect(screen.getByRole("button", { name: "Предварительный просмотр" })).toHaveClass("border", "bg-white");
    expect(screen.getByRole("button", { name: "Сохранить черновик" })).toHaveClass("bg-blue-700", "text-white", "rounded-lg");

    fireEvent.change(screen.getByLabelText("Заголовок RU"), { target: { value: "Несохранённый текст" } });
    fireEvent.click(screen.getByRole("button", { name: "Предварительный просмотр" }));
    expect(previewPersonnelOrderTemplateDraft).toHaveBeenCalledWith("LEAVE.UNPAID.GRANT", expect.objectContaining({ title_ru: "Несохранённый текст" }));
    const previewBody = vi.mocked(previewPersonnelOrderTemplateDraft).mock.calls.at(-1)?.[1];
    expect(Object.keys(previewBody ?? {}).sort()).toEqual([
      "basis_template_kk", "basis_template_ru", "body_template_kk", "body_template_ru",
      "preamble_kk", "preamble_ru", "title_kk", "title_ru",
    ]);
    expect(previewBody).not.toHaveProperty("template_version_id");
    expect(previewBody).not.toHaveProperty("revision");
    expect(previewBody).not.toHaveProperty("status");
    expect(await screen.findByTestId("template-draft-preview")).toHaveTextContent("ПРИКАЗЫВАЮ:");
    expect(screen.getByTestId("template-draft-preview")).toHaveTextContent("БҰЙЫРАМЫН:");
    expect(screen.getByLabelText("Заголовок RU")).toHaveValue("Несохранённый текст");
    expect(screen.getByLabelText("Распорядительный текст RU")).toHaveValue(unpaidDraft.body_template_ru);
    expect(screen.getByLabelText("Распорядительный текст KK")).toHaveValue(unpaidDraft.body_template_kk);

    fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));
    await waitFor(() => expect(savePersonnelOrderTemplateDraft).toHaveBeenCalledWith("LEAVE.UNPAID.GRANT", expect.objectContaining({ title_ru: "Несохранённый текст", expected_revision: 1 })));
  });

  it("synchronizes each resized RU textarea only with its paired KK textarea", async () => {
    let resizeCallback: ResizeObserverCallback | undefined;
    class ResizeObserverMock {
      constructor(callback: ResizeObserverCallback) { resizeCallback = callback; }
      observe() {}
      unobserve() {}
      disconnect() {}
    }
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    await screen.findByTestId("template-draft-editor");
    const ruBody = screen.getByLabelText("Распорядительный текст RU");
    const kkBody = screen.getByLabelText("Распорядительный текст KK");
    const kkTitle = screen.getByLabelText("Заголовок KK");
    vi.spyOn(ruBody, "getBoundingClientRect").mockReturnValue({ height: 276 } as DOMRect);

    resizeCallback?.([{ target: ruBody } as ResizeObserverEntry], {} as ResizeObserver);

    expect(kkBody).toHaveStyle({ height: "276px" });
    expect(kkTitle).not.toHaveStyle({ height: "276px" });
    expect(screen.getByTestId("template-draft-fields")).toHaveClass("grid-cols-1", "md:grid-cols-2");
  });

  it("saves the changed RU directive text, advances revision, and refreshes preview automatically", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    const savedDraft = { ...unpaidDraft, body_template_ru: "Сохранённый распорядительный текст RU", revision: 2 };
    vi.mocked(savePersonnelOrderTemplateDraft).mockResolvedValueOnce(savedDraft);
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    await screen.findByTestId("template-draft-editor");
    await screen.findByTestId("template-draft-preview");
    fireEvent.change(screen.getByLabelText("Распорядительный текст RU"), { target: { value: savedDraft.body_template_ru } });
    vi.mocked(previewPersonnelOrderTemplateDraft).mockResolvedValueOnce({ previews: { ...draftPreview.previews, ru: { ...draftPreview.previews.ru, body: savedDraft.body_template_ru } } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));

    await waitFor(() => expect(savePersonnelOrderTemplateDraft).toHaveBeenCalledWith("LEAVE.UNPAID.GRANT", {
      title_ru: unpaidDraft.title_ru, title_kk: unpaidDraft.title_kk,
      preamble_ru: unpaidDraft.preamble_ru, preamble_kk: unpaidDraft.preamble_kk,
      body_template_ru: savedDraft.body_template_ru, body_template_kk: unpaidDraft.body_template_kk,
      basis_template_ru: unpaidDraft.basis_template_ru, basis_template_kk: unpaidDraft.basis_template_kk,
      expected_revision: 1,
    }));
    expect(await screen.findByTestId("template-draft-preview")).toHaveTextContent(savedDraft.body_template_ru);
    expect(screen.getByRole("status")).toHaveTextContent("Черновик сохранён");
    expect(screen.getByTestId("template-draft-editor")).toHaveTextContent("revision 2");
    const saveBody = vi.mocked(savePersonnelOrderTemplateDraft).mock.calls.at(-1)?.[1];
    expect(saveBody).not.toHaveProperty("template_version_id");
    expect(saveBody).not.toHaveProperty("revision");
    expect(saveBody).not.toHaveProperty("status");
  });

  it("saves the changed KK directive text and refreshes the childcare-return preview automatically", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=RETURN_FROM_CHILDCARE_LEAVE");
    const savedDraft = { ...unpaidDraft, item_type_code: "RETURN_FROM_CHILDCARE_LEAVE", body_template_kk: "Сақталған қазақша өкімдік мәтін", revision: 2 };
    vi.mocked(createPersonnelOrderTemplateDraft).mockResolvedValueOnce(savedDraft);
    vi.mocked(savePersonnelOrderTemplateDraft).mockResolvedValueOnce(savedDraft);
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    await screen.findByTestId("template-draft-editor");
    await screen.findByTestId("template-draft-preview");
    fireEvent.change(screen.getByLabelText("Распорядительный текст KK"), { target: { value: savedDraft.body_template_kk } });
    vi.mocked(previewPersonnelOrderTemplateDraft).mockResolvedValueOnce({ previews: { ...draftPreview.previews, kk: { ...draftPreview.previews.kk, body: savedDraft.body_template_kk } } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));

    await waitFor(() => expect(savePersonnelOrderTemplateDraft).toHaveBeenCalledWith("RETURN_FROM_CHILDCARE_LEAVE", expect.objectContaining({ body_template_kk: savedDraft.body_template_kk, expected_revision: 2 })));
    expect(await screen.findByTestId("template-draft-preview")).toHaveTextContent(savedDraft.body_template_kk);
  });

  it("loads an existing draft through the editor action without creating another one", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(unpaidDraft);
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByTestId("template-draft-editor")).toBeInTheDocument();
    expect(screen.getByLabelText("Распорядительный текст RU")).toHaveValue(unpaidDraft.body_template_ru);
    expect(await screen.findByTestId("template-draft-preview")).toHaveTextContent(draftPreview.previews.ru.body);
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("shows preview progress and an API error beside the actions without clearing fields", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    let resolvePreview: (value: typeof draftPreview) => void = () => undefined;
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(unpaidDraft);
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    await screen.findByTestId("template-draft-editor");
    await screen.findByTestId("template-draft-preview");
    vi.mocked(previewPersonnelOrderTemplateDraft).mockImplementationOnce(() => new Promise((resolve) => { resolvePreview = resolve; }));
    fireEvent.change(screen.getByLabelText("Заголовок RU"), { target: { value: "Мой preview" } });
    fireEvent.click(screen.getByRole("button", { name: "Предварительный просмотр" }));
    const generating = screen.getByRole("button", { name: "Формирование…" });
    expect(generating).toBeDisabled();
    resolvePreview(draftPreview);
    expect(await screen.findByTestId("template-draft-preview")).toHaveTextContent("ПРИКАЗЫВАЮ:");
    expect(screen.getByLabelText("Заголовок RU")).toHaveValue("Мой preview");

    vi.mocked(previewPersonnelOrderTemplateDraft).mockRejectedValueOnce({ details: { detail: [{ loc: ["body", "title_ru"], msg: "Field required" }] } });
    fireEvent.click(screen.getByRole("button", { name: "Предварительный просмотр" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Поле «title_ru»: Field required");
    expect(screen.getByTestId("template-draft-actions")).toContainElement(alert);
  });

  it("shows the opening state once and does not create another draft while it is loading", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    let resolveLookup: (draft: typeof unpaidDraft | null) => void = () => undefined;
    vi.mocked(getPersonnelOrderTemplateDraft).mockImplementationOnce(() => new Promise((resolve) => { resolveLookup = resolve; }));
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    const opening = screen.getByRole("button", { name: "Открытие…" });
    expect(opening).toBeDisabled();
    fireEvent.click(opening);
    expect(getPersonnelOrderTemplateDraft).toHaveBeenCalledTimes(1);
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
    resolveLookup(null);
    expect(await screen.findByTestId("template-draft-editor")).toBeInTheDocument();
    expect(createPersonnelOrderTemplateDraft).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: "Редактировать шаблон" })).not.toBeInTheDocument();
  });

  it("disables the primary save action and shows its loading label while saving", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    let resolveSave: (next: typeof unpaidDraft) => void = () => undefined;
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(unpaidDraft);
    vi.mocked(savePersonnelOrderTemplateDraft).mockImplementationOnce(() => new Promise((resolve) => { resolveSave = resolve; }));
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByTestId("template-draft-editor")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));
    const saving = screen.getByRole("button", { name: "Сохранение…" });
    expect(saving).toBeDisabled();
    expect(saving).toHaveClass("disabled:cursor-not-allowed", "disabled:opacity-60");
    resolveSave({ ...unpaidDraft, revision: 2 });
    await waitFor(() => expect(screen.getByRole("button", { name: "Сохранить черновик" })).toBeEnabled());
  });

  it("shows the server conflict message without resetting the entered draft", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(unpaidDraft);
    vi.mocked(savePersonnelOrderTemplateDraft).mockRejectedValue({ status: 409, message: "Черновик изменён другим пользователем." });
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByTestId("template-draft-editor")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Заголовок RU"), { target: { value: "Мой текст" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Черновик изменён другим пользователем.");
    expect(screen.getByLabelText("Заголовок RU")).toHaveValue("Мой текст");
    expect(screen.queryByTestId("template-draft-preview")).not.toBeInTheDocument();
  });
});
