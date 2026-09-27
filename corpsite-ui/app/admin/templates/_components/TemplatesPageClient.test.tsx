import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TemplatesPageClient from "./TemplatesPageClient";
import { listPersonnelOrderTemplateCatalog } from "../_lib/personnelOrderTemplatesApi.client";

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
vi.mock("../_lib/personnelOrderTemplatesApi.client", () => ({ listPersonnelOrderTemplateCatalog: vi.fn() }));

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
      body: "Сотруднику приступить к работе 15 января 2026 года.",
      basis: "Основание: Личное заявление.",
      footer: "С приказом ознакомлен(а): ___________________ [Фамилия И.]\n«___» ______________ 20___ г.\nИсполнитель: [Инициалы и фамилия исполнителя]",
    },
    kk: {
      title: "Бала күтіміне байланысты демалыстан жұмысқа шығу туралы",
      preamble: "Қазақстан Республикасының заңнамасына сәйкес",
      directive: "БҰЙЫРАМЫН:",
      body: "Қызметкер 2026 жылғы 15 қаңтардан бастап жұмысқа кіріссін.",
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

describe("TemplatesPageClient", () => {
  beforeEach(() => {
    currentSearch = new URLSearchParams();
    push.mockReset();
    vi.mocked(listPersonnelOrderTemplateCatalog).mockResolvedValue({ items: [{
      type_code: "RETURN_FROM_CHILDCARE_LEAVE",
      title_ru: "О выходе на работу из отпуска по уходу за ребёнком",
      title_kk: "Бала күтіміне байланысты демалыстан жұмысқа шығу туралы",
      source: "BUILT_IN",
      support_level: "SUPPORTED",
      supported_locales: ["ru", "kk"],
      uses_specialized_generator: true,
      is_pilot: true,
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
      required_fields: unpaidDetail.required_fields,
      notes: "Формализованный read-only шаблон.",
      pilot_detail: null,
      template_detail: unpaidDetail,
    }] });
  });

  afterEach(cleanup);

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
    expect(screen.queryByRole("button", { name: /редактировать|опубликовать|архивировать/i })).not.toBeInTheDocument();
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
});
