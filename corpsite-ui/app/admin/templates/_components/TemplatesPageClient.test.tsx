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
