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

describe("TemplatesPageClient", () => {
  beforeEach(() => {
    currentSearch = new URLSearchParams();
    push.mockReset();
    vi.mocked(listPersonnelOrderTemplateCatalog).mockResolvedValue({ items: [{ type_code: "RETURN_FROM_CHILDCARE_LEAVE", title_ru: "О выходе на работу из отпуска по уходу за ребёнком", title_kk: "Бала күтіміне байланысты демалыстан жұмысқа шығу туралы", source: "BUILT_IN", support_level: "SUPPORTED", supported_locales: ["ru", "kk"], uses_specialized_generator: true, is_pilot: true, required_fields: [], notes: "Не формализованы" }] });
  });

  afterEach(cleanup);

  it("opens task templates by default and reuses the regular task component", () => {
    render(<TemplatesPageClient />);

    expect(screen.getByRole("heading", { name: "Шаблоны" })).toBeInTheDocument();
    expect(screen.getByTestId("task-templates-section")).toBeInTheDocument();
    expect(screen.getByTestId("reused-regular-task-templates")).toHaveAttribute("data-embedded", "true");
    expect(screen.queryByTestId("personnel-order-templates-empty-state")).not.toBeInTheDocument();
  });

  it("shows the personnel order templates catalogue for its direct URL", async () => {
    currentSearch = new URLSearchParams("section=personnel-orders");
    render(<TemplatesPageClient />);

    expect(await screen.findByTestId("personnel-order-templates-catalog")).toHaveTextContent("RETURN_FROM_CHILDCARE_LEAVE");
    expect(screen.queryByTestId("reused-regular-task-templates")).not.toBeInTheDocument();
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
