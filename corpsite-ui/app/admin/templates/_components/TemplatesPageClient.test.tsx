import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TemplatesPageClient from "./TemplatesPageClient";
import { createPersonnelOrderTemplateDraft, getPersonnelOrderTemplateDraft, getPersonnelOrderTemplatePublished, getPersonnelOrderTemplateEditorBase, listPersonnelOrderTemplateCatalog, previewPersonnelOrderTemplateDraft, publishPersonnelOrderTemplateDraft, savePersonnelOrderTemplateDraft } from "../_lib/personnelOrderTemplatesApi.client";

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
vi.mock("../_lib/personnelOrderTemplatesApi.client", () => ({ listPersonnelOrderTemplateCatalog: vi.fn(), getPersonnelOrderTemplateDraft: vi.fn(), getPersonnelOrderTemplatePublished: vi.fn(), getPersonnelOrderTemplateEditorBase: vi.fn(), createPersonnelOrderTemplateDraft: vi.fn(), savePersonnelOrderTemplateDraft: vi.fn(), previewPersonnelOrderTemplateDraft: vi.fn(), publishPersonnelOrderTemplateDraft: vi.fn() }));

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
      body: "[[ФИО сотрудника]] приступить к работе в должности [[Должность]] подразделения [[Подразделение]] на [[Ставка]] ставки с [[Дата выхода]].",
      basis: "Основание: Личное заявление.",
      footer: "С приказом ознакомлен(а): ___________________ [Фамилия И.]\n«___» ______________ 20___ г.\nИсполнитель: [Инициалы и фамилия исполнителя]",
    },
    kk: {
      title: "Бала күтіміне байланысты демалыстан жұмысқа шығу туралы",
      preamble: "Қазақстан Республикасының заңнамасына сәйкес",
      directive: "БҰЙЫРАМЫН:",
      body: "[[Қызметкердің аты-жөні]] [[Лауазым]] лауазымында [[Бөлімше]] бөлімшесінде [[Мөлшерлеме]] мөлшерлемемен [[Жұмысқа шығу күні]] бастап жұмысқа кіріссін.",
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
      body: "Предоставить [[ФИО сотрудника]], [[Должность]] подразделения «[[Подразделение]]», отпуск без сохранения заработной платы с [[Дата начала отпуска]] по [[Дата окончания отпуска]] включительно продолжительностью [[Количество дней]] календарных дней.",
      basis: "Основание: личное заявление от [[Дата заявления]] № [[Номер заявления]].",
      footer: "С приказом ознакомлен(а): ___________________ [Фамилия И.]\n«___» ______________ 20___ г.\nИсполнитель: [Инициалы и фамилия исполнителя]",
    },
    kk: {
      title: "Жалақы сақталмайтын демалыс беру туралы",
      preamble: "Қазақстан Республикасының Еңбек кодексіне сәйкес",
      directive: "БҰЙЫРАМЫН:",
      body: "[[Қызметкердің аты-жөні]], «[[Бөлімше]]» бөлімшесінің «[[Лауазым]]» қызметкеріне [[Демалыстың басталу күні]] мен [[Демалыстың аяқталу күні]] аралығындағы [[Күн саны]] күнтізбелік күнге жалақы сақталмайтын демалыс берілсін.",
      basis: "Негіз: [[Өтініш күні]] күнгі жеке өтініш № [[Өтініш нөмірі]].",
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

const legacyTerminationDraft = {
  ...unpaidDraft,
  template_version_id: 3,
  item_type_code: "TERMINATION",
  revision: 1,
  body_template_ru: "Старый текст увольнения RU {{employee.full_name}} {{effective_date}}.",
  body_template_kk: "Ескі мәтін KK {{employee.full_name}} {{effective_date}}.",
};

describe("TemplatesPageClient", () => {
  afterEach(() => { vi.unstubAllGlobals(); });
  beforeEach(() => {
    window.localStorage.clear();
    currentSearch = new URLSearchParams();
    push.mockReset();
    vi.mocked(getPersonnelOrderTemplateDraft).mockReset();
    vi.mocked(getPersonnelOrderTemplatePublished).mockReset();
    vi.mocked(getPersonnelOrderTemplateEditorBase).mockReset();
    vi.mocked(createPersonnelOrderTemplateDraft).mockReset();
    vi.mocked(savePersonnelOrderTemplateDraft).mockReset();
    vi.mocked(previewPersonnelOrderTemplateDraft).mockReset();
    vi.mocked(publishPersonnelOrderTemplateDraft).mockReset();
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(unpaidDraft);
    vi.mocked(getPersonnelOrderTemplatePublished).mockResolvedValue(null);
    vi.mocked(getPersonnelOrderTemplateEditorBase).mockResolvedValue({ ...unpaidDraft, source: "INITIAL", template_version_id: null, version_number: null, revision: null });
    vi.mocked(createPersonnelOrderTemplateDraft).mockResolvedValue(unpaidDraft);
    vi.mocked(savePersonnelOrderTemplateDraft).mockResolvedValue({ ...unpaidDraft, revision: 2 });
    vi.mocked(previewPersonnelOrderTemplateDraft).mockResolvedValue(draftPreview);
    vi.mocked(publishPersonnelOrderTemplateDraft).mockResolvedValue({ ...unpaidDraft, status: "PUBLISHED", published_at: "2026-01-01T00:00:00", published_by_user_id: 1 });
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
      type_code: "TERMINATION",
      title_ru: "Об увольнении",
      title_kk: "Жұмыстан босату туралы",
      source: "BUILT_IN",
      support_level: "SUPPORTED",
      supported_locales: ["ru", "kk"],
      uses_specialized_generator: true,
      is_pilot: false,
      editor_available: true,
      required_fields: [],
      notes: "Формализованный read-only шаблон.",
      pilot_detail: null,
      template_detail: {
        required_fields: ["ФИО сотрудника", "Дата увольнения", "Причина увольнения", "Основание"],
        additional_fields: [],
        document_parts: ["Заголовок", "Преамбула", "ПРИКАЗЫВАЮ: / БҰЙЫРАМЫН:", "Распорядительный текст", "Основание", "Печатный подвал"],
        variables: [{ code: "employee.full_name", label: "ФИО сотрудника" }, { code: "effective_date", label: "Дата увольнения" }, { code: "termination.reason", label: "Причина увольнения" }, { code: "basis", label: "Основание" }],
        specialty_note: "Должность, подразделение и ставка в текст этого приказа не включаются.",
        previews: {
          ru: { title: "Об увольнении", preamble: "В соответствии с Трудовым кодексом Республики Казахстан", directive: "ПРИКАЗЫВАЮ:", body: "Уволить [[ФИО сотрудника]] с [[Дата увольнения]]. Основание: [[Причина увольнения]].", basis: "[[Основание]]", footer: "" },
          kk: { title: "Жұмыстан босату туралы", preamble: "Қазақстан Республикасының Еңбек кодексіне сәйкес", directive: "БҰЙЫРАМЫН:", body: "[[Қызметкердің аты-жөні]] [[Жұмыстан босату күні]] бастап жұмыстан босатылсын. Негіздеме: [[Жұмыстан босату себебі]].", basis: "[[Негіз]]", footer: "" },
        },
      },
    }, {
      type_code: "HIRE",
      title_ru: "Приём на работу",
      title_kk: "Жұмысқа қабылдау",
      source: "BUILT_IN",
      support_level: "SUPPORTED",
      supported_locales: ["ru", "kk"],
      uses_specialized_generator: true,
      is_pilot: false,
      editor_available: true,
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
    expect(screen.queryByTestId("pilot-preview-ru")).not.toBeInTheDocument();
    expect(screen.queryByTestId("pilot-preview-kk")).not.toBeInTheDocument();

  });

  it("renders the unpaid leave detail with one separate basis and no closing block", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    render(<TemplatesPageClient />);

    const detail = await screen.findByTestId("personnel-order-template-detail");
    expect(detail).toHaveTextContent("Реквизиты этого шаблона");
    expect(detail).toHaveTextContent("Дата заявления (если известна)");
    expect(screen.queryByTestId("pilot-preview-ru")).not.toBeInTheDocument();
    expect(screen.queryByTestId("pilot-preview-kk")).not.toBeInTheDocument();

  });

  it("renders the termination preview and offers the common edit action", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=TERMINATION");
    render(<TemplatesPageClient />);

    const detail = await screen.findByTestId("personnel-order-template-detail");
    expect(detail).toHaveTextContent("ФИО сотрудника");
    expect(detail).toHaveTextContent("Дата увольнения");
    expect(detail).toHaveTextContent("Причина увольнения");
    expect(detail).toHaveTextContent("Основание");
    expect(screen.queryByTestId("pilot-preview-ru")).not.toBeInTheDocument();
    expect(screen.queryByTestId("pilot-preview-kk")).not.toBeInTheDocument();

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
    await waitFor(() => expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled());
    const editor = await screen.findByTestId("template-draft-editor");
    expect(editor).toHaveTextContent("Русский");
    expect(editor).toHaveTextContent("Қазақша");
  });

  it("offers the editor button for every registered standalone template", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=HIRE");
    render(<TemplatesPageClient />);
    await screen.findByTestId("personnel-order-template-detail");
    expect(screen.getByRole("button", { name: "Редактировать шаблон" })).toBeInTheDocument();
  });

  it("offers the draft editor only for unpaid leave and preserves unsaved bilingual text through preview", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    expect(screen.getByRole("button", { name: "Редактировать шаблон" })).toHaveClass("bg-blue-700", "text-white", "rounded-lg");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    await waitFor(() => expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled());

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
    expect(screen.getByRole("button", { name: /Опубликовать/i })).toBeInTheDocument();
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

  it("previews the current eight fields of an existing TERMINATION draft and clears stale output", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=TERMINATION");
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(legacyTerminationDraft);
    let resolvePreview!: (value: typeof draftPreview) => void;
    vi.mocked(previewPersonnelOrderTemplateDraft).mockImplementationOnce(() => new Promise((resolve) => { resolvePreview = resolve; }));
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByTestId("template-draft-editor")).toBeInTheDocument();
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Распорядительный текст RU"), { target: { value: "Новый текст RU" } });
    fireEvent.change(screen.getByLabelText("Распорядительный текст KK"), { target: { value: "Жаңа мәтін KK" } });
    fireEvent.click(screen.getByRole("button", { name: "Предварительный просмотр" }));
    expect(screen.getByRole("button", { name: "Формирование…" })).toBeDisabled();

    const [typeCode, body] = vi.mocked(previewPersonnelOrderTemplateDraft).mock.calls[0];
    expect(typeCode).toBe("TERMINATION");
    expect(Object.keys(body).sort()).toEqual([
      "basis_template_kk", "basis_template_ru", "body_template_kk", "body_template_ru",
      "preamble_kk", "preamble_ru", "title_kk", "title_ru",
    ]);
    expect(body).toMatchObject({ body_template_ru: "Новый текст RU", body_template_kk: "Жаңа мәтін KK" });
    expect(body).not.toHaveProperty("template_version_id");
    expect(body).not.toHaveProperty("revision");
    expect(body).not.toHaveProperty("status");

    resolvePreview({ previews: {
      ru: { ...draftPreview.previews.ru, body: "Обновлённый RU preview" },
      kk: { ...draftPreview.previews.kk, body: "Жаңартылған KK preview" },
    } });
    expect(await screen.findByTestId("template-draft-preview")).toHaveTextContent("Обновлённый RU preview");
    expect(screen.getByTestId("template-draft-preview")).toHaveTextContent("Жаңартылған KK preview");

    fireEvent.change(screen.getByLabelText("Распорядительный текст RU"), { target: { value: "Текст после preview" } });
    expect(screen.queryByTestId("template-draft-preview")).not.toBeInTheDocument();
    vi.mocked(previewPersonnelOrderTemplateDraft).mockRejectedValueOnce(new Error("Preview backend rejected body_template_kk"));
    fireEvent.click(screen.getByRole("button", { name: "Предварительный просмотр" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Preview backend rejected body_template_kk");
    expect(screen.queryByTestId("template-draft-preview")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Распорядительный текст RU")).toHaveValue("Текст после preview");
    expect(screen.getByLabelText("Распорядительный текст KK")).toHaveValue("Жаңа мәтін KK");
  });

  it("saves and reopens TERMINATION as one confirmed eight-field snapshot", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=TERMINATION");
    const confirmed = {
      ...legacyTerminationDraft,
      revision: 2,
      title_ru: "Сохранённый заголовок RU", title_kk: "Сақталған тақырып KK",
      preamble_ru: "Сохранённая преамбула RU", preamble_kk: "Сақталған кіріспе KK",
      body_template_ru: "Сохранённый body RU", body_template_kk: "Сақталған body KK",
      basis_template_ru: "Сохранённое основание RU", basis_template_kk: "Сақталған негіз KK",
    };
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValueOnce(legacyTerminationDraft).mockResolvedValueOnce(confirmed);
    vi.mocked(savePersonnelOrderTemplateDraft).mockResolvedValueOnce(confirmed);
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    await screen.findByTestId("template-draft-editor");
    const fields = [
      ["Заголовок RU", confirmed.title_ru], ["Заголовок KK", confirmed.title_kk],
      ["Преамбула RU", confirmed.preamble_ru], ["Преамбула KK", confirmed.preamble_kk],
      ["Распорядительный текст RU", confirmed.body_template_ru], ["Распорядительный текст KK", confirmed.body_template_kk],
      ["Основание RU", confirmed.basis_template_ru], ["Основание KK", confirmed.basis_template_kk],
    ] as const;
    fields.forEach(([label, value]) => fireEvent.change(screen.getByLabelText(label), { target: { value } }));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));

    await waitFor(() => expect(savePersonnelOrderTemplateDraft).toHaveBeenCalledWith("TERMINATION", {
      title_ru: confirmed.title_ru, title_kk: confirmed.title_kk,
      preamble_ru: confirmed.preamble_ru, preamble_kk: confirmed.preamble_kk,
      body_template_ru: confirmed.body_template_ru, body_template_kk: confirmed.body_template_kk,
      basis_template_ru: confirmed.basis_template_ru, basis_template_kk: confirmed.basis_template_kk,
      expected_revision: 1,
    }));
    expect(screen.getByRole("status")).toHaveTextContent("Черновик сохранён");
    expect(screen.getByTestId("template-draft-editor")).toHaveTextContent("revision 2");
    fields.forEach(([label, value]) => expect(screen.getByLabelText(label)).toHaveValue(value));

    cleanup();
    render(<TemplatesPageClient />);
    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByTestId("template-draft-editor")).toHaveTextContent("revision 2");
    fields.forEach(([label, value]) => expect(screen.getByLabelText(label)).toHaveValue(value));
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
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

    resizeCallback?.([{ target: ruBody } as unknown as ResizeObserverEntry], {} as ResizeObserver);

    expect(kkBody).toHaveStyle({ height: "276px" });
    expect(kkTitle).not.toHaveStyle({ height: "276px" });
    expect(JSON.parse(window.localStorage.getItem("corpsite.personnel-order-template-draft-heights.v1:LEAVE.UNPAID.GRANT") || "{}")).toEqual({ body_template: 276 });
    expect(screen.getByTestId("template-draft-fields")).toHaveClass("grid-cols-1", "md:grid-cols-2");
  });

  it("restores saved paired heights when the editor is opened again", async () => {
    window.localStorage.setItem("corpsite.personnel-order-template-draft-heights.v1:LEAVE.UNPAID.GRANT", JSON.stringify({ title: 126, body_template: 320 }));
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    await screen.findByTestId("template-draft-editor");
    await waitFor(() => {
      expect(screen.getByLabelText("Заголовок RU")).toHaveStyle({ height: "126px" });
      expect(screen.getByLabelText("Заголовок KK")).toHaveStyle({ height: "126px" });
      expect(screen.getByLabelText("Распорядительный текст RU")).toHaveStyle({ height: "320px" });
      expect(screen.getByLabelText("Распорядительный текст KK")).toHaveStyle({ height: "320px" });
    });
  });

  it("keeps independently saved heights while switching template types and returning", async () => {
    window.localStorage.setItem("corpsite.personnel-order-template-draft-heights.v1:LEAVE.UNPAID.GRANT", JSON.stringify({ body_template: 220 }));
    window.localStorage.setItem("corpsite.personnel-order-template-draft-heights.v1:TERMINATION", JSON.stringify({ body_template: 360 }));
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    const view = render(<TemplatesPageClient />);
    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    await waitFor(() => expect(screen.getByLabelText("Распорядительный текст RU")).toHaveStyle({ height: "220px" }));

    currentSearch = new URLSearchParams("section=personnel-orders&type=TERMINATION");
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValueOnce(legacyTerminationDraft);
    view.rerender(<TemplatesPageClient />);
    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    await waitFor(() => expect(screen.getByLabelText("Распорядительный текст RU")).toHaveStyle({ height: "360px" }));

    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValueOnce(unpaidDraft);
    view.rerender(<TemplatesPageClient />);
    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    await waitFor(() => expect(screen.getByLabelText("Распорядительный текст RU")).toHaveStyle({ height: "220px" }));
  });

  it("resets only the current template's saved field heights", async () => {
    const currentKey = "corpsite.personnel-order-template-draft-heights.v1:LEAVE.UNPAID.GRANT";
    const otherKey = "corpsite.personnel-order-template-draft-heights.v1:TERMINATION";
    window.localStorage.setItem(currentKey, JSON.stringify({ body_template: 280 }));
    window.localStorage.setItem(otherKey, JSON.stringify({ body_template: 380 }));
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    await waitFor(() => expect(screen.getByLabelText("Распорядительный текст RU")).toHaveStyle({ height: "280px" }));
    fireEvent.click(screen.getByRole("button", { name: "Сбросить высоту полей" }));
    expect(window.localStorage.getItem(currentKey)).toBeNull();
    expect(window.localStorage.getItem(otherKey)).toBe(JSON.stringify({ body_template: 380 }));
    expect(screen.getByLabelText("Распорядительный текст RU")).not.toHaveStyle({ height: "280px" });
  });

  it("tolerates missing or corrupted localStorage height preferences", async () => {
    window.localStorage.setItem("corpsite.personnel-order-template-draft-heights.v1:LEAVE.UNPAID.GRANT", "not-json");
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByTestId("template-draft-editor")).toBeInTheDocument();
    expect(screen.getByLabelText("Распорядительный текст RU")).not.toHaveStyle({ height: "900px" });
  });

  it("saves the changed RU directive text, advances revision, and refreshes preview automatically", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    const savedDraft = { ...unpaidDraft, body_template_ru: "Сохранённый распорядительный текст RU", revision: 2 };
    vi.mocked(savePersonnelOrderTemplateDraft).mockResolvedValueOnce(savedDraft);
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    await screen.findByTestId("template-draft-editor");
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
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue({ ...unpaidDraft, item_type_code: "RETURN_FROM_CHILDCARE_LEAVE", revision: 2 });
    vi.mocked(createPersonnelOrderTemplateDraft).mockResolvedValueOnce(savedDraft);
    vi.mocked(savePersonnelOrderTemplateDraft).mockResolvedValueOnce(savedDraft);
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    await screen.findByTestId("template-draft-editor");
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
    fireEvent.click(screen.getByRole("button", { name: "Предварительный просмотр" }));
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
    resolveLookup(unpaidDraft);
    expect(await screen.findByTestId("template-draft-editor")).toBeInTheDocument();
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
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
    expect(screen.getByRole("button", { name: "Загрузить актуальную версию" })).toBeInTheDocument();
    expect(screen.getByLabelText("Заголовок RU")).toHaveValue("Мой текст");
    expect(screen.queryByTestId("template-draft-preview")).not.toBeInTheDocument();
  });

  it("clears a previous editor immediately, ignores its late response, and reloads the latest draft after switching back", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=TERMINATION");
    const latestTermination = { ...legacyTerminationDraft, revision: 9, body_template_ru: "Последняя серверная версия TERMINATION" };
    let resolveStaleTermination!: (draft: typeof legacyTerminationDraft) => void;
    vi.mocked(getPersonnelOrderTemplateDraft)
      .mockResolvedValueOnce(legacyTerminationDraft)
      .mockResolvedValueOnce(unpaidDraft)
      .mockImplementationOnce(() => new Promise((resolve) => { resolveStaleTermination = resolve; }))
      .mockResolvedValueOnce(unpaidDraft)
      .mockResolvedValueOnce(latestTermination);
    render(<TemplatesPageClient />);

    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByTestId("template-draft-editor")).toHaveTextContent("Старый текст увольнения RU");
    fireEvent.click(screen.getByRole("button", { name: "Предварительный просмотр" }));
    expect(await screen.findByTestId("template-draft-preview")).toBeInTheDocument();
    vi.mocked(previewPersonnelOrderTemplateDraft).mockRejectedValueOnce(new Error("Ошибка TERMINATION"));
    fireEvent.click(screen.getByRole("button", { name: "Предварительный просмотр" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Ошибка TERMINATION");

    fireEvent.click(screen.getByTestId("personnel-order-template-LEAVE.UNPAID.GRANT"));
    expect(push).toHaveBeenLastCalledWith("/admin/templates?section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    expect(screen.queryByTestId("template-draft-editor")).not.toBeInTheDocument();
    expect(screen.queryByTestId("template-draft-preview")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(screen.getByTestId("template-editor-opening")).toHaveTextContent("Открытие редактора…");
    expect(await screen.findByTestId("template-draft-editor")).toHaveTextContent(unpaidDraft.body_template_ru);

    fireEvent.click(screen.getByTestId("personnel-order-template-TERMINATION"));
    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(screen.getByTestId("template-editor-opening")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("personnel-order-template-LEAVE.UNPAID.GRANT"));
    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByTestId("template-draft-editor")).toHaveTextContent(unpaidDraft.body_template_ru);
    resolveStaleTermination(legacyTerminationDraft);
    await waitFor(() => expect(screen.getByTestId("template-draft-editor")).toHaveTextContent(unpaidDraft.body_template_ru));
    expect(screen.getByTestId("personnel-order-template-detail")).not.toHaveTextContent("Старый текст увольнения RU");

    fireEvent.click(screen.getByTestId("personnel-order-template-TERMINATION"));
    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByTestId("template-draft-editor")).toHaveTextContent("Последняя серверная версия TERMINATION");
    expect(screen.getByTestId("template-draft-editor")).toHaveTextContent("revision 9");
  });

  it("uses only the saved TERMINATION draft after opening, saving, and switching back", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=TERMINATION");
    const serverDraft = {
      ...legacyTerminationDraft,
      revision: 3,
      title_ru: "Новый title RU", title_kk: "Жаңа title KK",
      preamble_ru: "Новая preamble RU", preamble_kk: "Жаңа preamble KK",
      body_template_ru: "Новый body RU {{employee.full_name}} {{effective_date}}", body_template_kk: "Жаңа body KK {{employee.full_name}} {{effective_date}}",
      basis_template_ru: "Новое basis RU {{basis}}", basis_template_kk: "Жаңа basis KK {{basis}}",
    };
    const savedDraft = { ...serverDraft, revision: 4, title_ru: "Последний title RU" };
    vi.mocked(getPersonnelOrderTemplateDraft)
      .mockResolvedValueOnce(serverDraft)
      .mockResolvedValueOnce(unpaidDraft)
      .mockResolvedValueOnce(savedDraft);
    vi.mocked(savePersonnelOrderTemplateDraft).mockResolvedValueOnce(savedDraft);
    render(<TemplatesPageClient />);

    const detail = await screen.findByTestId("personnel-order-template-detail");
    expect(detail).not.toHaveTextContent(serverDraft.title_ru);
    expect(screen.queryByTestId("pilot-preview-ru")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    const editor = await screen.findByTestId("template-draft-editor");
    expect(screen.queryByTestId("pilot-preview-ru")).not.toBeInTheDocument();
    expect(screen.queryByTestId("template-draft-preview")).not.toBeInTheDocument();
    const fields = [
      ["Заголовок RU", serverDraft.title_ru], ["Заголовок KK", serverDraft.title_kk],
      ["Преамбула RU", serverDraft.preamble_ru], ["Преамбула KK", serverDraft.preamble_kk],
      ["Распорядительный текст RU", serverDraft.body_template_ru], ["Распорядительный текст KK", serverDraft.body_template_kk],
      ["Основание RU", serverDraft.basis_template_ru], ["Основание KK", serverDraft.basis_template_kk],
    ] as const;
    fields.forEach(([label, value]) => expect(screen.getByLabelText(label)).toHaveValue(value));
    fireEvent.change(screen.getByLabelText("Заголовок RU"), { target: { value: savedDraft.title_ru } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить черновик" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Черновик сохранён");
    expect(editor).toHaveTextContent("revision 4");

    fireEvent.click(screen.getByTestId("personnel-order-template-LEAVE.UNPAID.GRANT"));
    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByTestId("template-draft-editor")).toHaveTextContent(unpaidDraft.body_template_ru);
    fireEvent.click(screen.getByTestId("personnel-order-template-TERMINATION"));
    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByTestId("template-draft-editor")).toHaveTextContent("Последний title RU");
    expect(screen.getByLabelText("Заголовок RU")).toHaveValue(savedDraft.title_ru);
    expect(screen.getByLabelText("Заголовок KK")).toHaveValue(savedDraft.title_kk);
    expect(screen.getByLabelText("Преамбула RU")).toHaveValue(savedDraft.preamble_ru);
    expect(screen.getByLabelText("Преамбула KK")).toHaveValue(savedDraft.preamble_kk);
    expect(screen.getByLabelText("Распорядительный текст RU")).toHaveValue(savedDraft.body_template_ru);
    expect(screen.getByLabelText("Распорядительный текст KK")).toHaveValue(savedDraft.body_template_kk);
    expect(screen.getByLabelText("Основание RU")).toHaveValue(savedDraft.basis_template_ru);
    expect(screen.getByLabelText("Основание KK")).toHaveValue(savedDraft.basis_template_kk);
    expect(screen.queryByTestId("pilot-preview-ru")).not.toBeInTheDocument();
    expect(screen.queryByTestId("template-draft-preview")).not.toBeInTheDocument();
  });

  it("publishes only after explicit confirmation and keeps the published version read-only", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    const published = { ...unpaidDraft, status: "PUBLISHED", published_at: "2026-01-01T00:00:00", published_by_user_id: 1 };
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValueOnce(unpaidDraft).mockResolvedValueOnce(unpaidDraft).mockResolvedValue(null);
    vi.mocked(getPersonnelOrderTemplatePublished).mockResolvedValue(published);
    vi.mocked(publishPersonnelOrderTemplateDraft).mockResolvedValue(published);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<TemplatesPageClient />);
    fireEvent.click(await screen.findByRole("button", { name: "Редактировать шаблон" }));
    await screen.findByTestId("template-draft-editor");
    fireEvent.click(screen.getByRole("button", { name: "Опубликовать версию" }));
    await waitFor(() => expect(publishPersonnelOrderTemplateDraft).toHaveBeenCalledWith("LEAVE.UNPAID.GRANT", 1));
    expect(await screen.findByTestId("template-published-read-only")).toHaveTextContent("PUBLISHED");
    expect(screen.queryByTestId("template-draft-editor")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Опубликовать версию" })).not.toBeInTheDocument();
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
    expect(getPersonnelOrderTemplateDraft).toHaveBeenCalledTimes(3);
    confirm.mockRestore();
  });

  it("does not call publish when the confirmation is cancelled", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=LEAVE.UNPAID.GRANT");
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(unpaidDraft);
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<TemplatesPageClient />);
    fireEvent.click(await screen.findByRole("button", { name: "Редактировать шаблон" }));
    await screen.findByTestId("template-draft-editor");
    fireEvent.click(screen.getByRole("button", { name: "Опубликовать версию" }));
    expect(publishPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
    confirm.mockRestore();
  });

  it("uses only GET on mount and opens an unsaved working copy after an explicit edit click", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=TERMINATION");
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(null);
    vi.mocked(getPersonnelOrderTemplatePublished).mockResolvedValue({ ...legacyTerminationDraft, status: "PUBLISHED", version_number: 1 });
    render(<TemplatesPageClient />);
    await screen.findByTestId("template-published-read-only");
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
    expect(screen.queryByTestId("template-draft-editor")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByTestId("template-draft-editor")).toHaveTextContent("Несохранённая рабочая копия");
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("does not create a draft on reload or while switching template types", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=TERMINATION");
    vi.mocked(getPersonnelOrderTemplatePublished).mockResolvedValue(null);
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(null);
    const view = render(<TemplatesPageClient />);
    await screen.findByTestId("personnel-order-template-detail");
    view.rerender(<TemplatesPageClient />);
    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByTestId("personnel-order-template-LEAVE.UNPAID.GRANT"));
    await screen.findByTestId("personnel-order-template-detail");
    fireEvent.click(screen.getByTestId("personnel-order-template-TERMINATION"));
    await screen.findByTestId("personnel-order-template-detail");
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("does not recreate a missing TERMINATION draft on production-style mount or reload", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=TERMINATION");
    const publishedV2 = { ...legacyTerminationDraft, template_version_id: 902, version_number: 2, status: "PUBLISHED" };
    vi.mocked(getPersonnelOrderTemplatePublished).mockResolvedValue(publishedV2);
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(null);

    const view = render(<TemplatesPageClient />);
    await screen.findByTestId("template-published-read-only");
    view.rerender(<TemplatesPageClient />);
    await screen.findByTestId("template-published-read-only");

    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
    expect(screen.queryByTestId("template-draft-editor")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByTestId("template-draft-editor")).toHaveTextContent("Несохранённая рабочая копия");
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });

  it("opens an existing saved draft without creating a duplicate", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders&type=TERMINATION");
    vi.mocked(getPersonnelOrderTemplateDraft).mockResolvedValue(legacyTerminationDraft);
    vi.mocked(getPersonnelOrderTemplatePublished).mockResolvedValue({ ...legacyTerminationDraft, status: "PUBLISHED", version_number: 1 });
    render(<TemplatesPageClient />);
    expect(await screen.findByText("Редактировать шаблон")).toBeInTheDocument();
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
    expect(screen.queryByTestId("template-draft-editor")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Редактировать шаблон" }));
    expect(await screen.findByTestId("template-draft-editor")).toBeInTheDocument();
    expect(createPersonnelOrderTemplateDraft).not.toHaveBeenCalled();
  });
});
