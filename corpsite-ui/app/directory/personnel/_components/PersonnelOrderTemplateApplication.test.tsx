import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PersonnelOrderTemplateApplication from "./PersonnelOrderTemplateApplication";
import { applyPersonnelOrderTemplateApplication, previewPersonnelOrderTemplateApplication } from "../_lib/personnelOrdersApi.client";

vi.mock("../_lib/personnelOrdersApi.client", () => ({
  previewPersonnelOrderTemplateApplication: vi.fn(),
  applyPersonnelOrderTemplateApplication: vi.fn(),
}));

const preview = (overrides = false, prior = false) => ({
  available: true,
  template: { template_version_id: 9, version_number: 3, item_type_code: "TERMINATION" },
  has_overrides: overrides,
  override_blocks: overrides ? [{ block_id: 3, scope: "ORDER" as const, block_type: "TITLE" as const, language: "RU" as const, order_item_id: null }] : [],
  has_prior_application: prior,
  last_application: prior ? { application_id: 7, template_version_id: 9, template_version_number: 3, applied_at: "2026-01-01T10:00:00", applied_by_user_id: 4 } : null,
  current: Object.fromEntries(["ru", "kk"].flatMap((locale) => ["title", "preamble", "body", "basis"].map((block) => [`${locale}:${block}`, { generated_text: `current ${locale} ${block}`, override_text: null, revision: 1 }]))) as Record<string, { generated_text: string; override_text: null; revision: number }>,
  proposed: {
    ...Object.fromEntries(["ru", "kk"].flatMap((locale) => ["title", "preamble", "body_template"].map((block) => [`${block}_${locale}`, `proposed ${locale} ${block}`]))),
    basis_template_ru: "Личное заявление",
    basis_template_kk: "Жеке өтініш",
  } as Record<string, string>,
  order_revision: 5,
});
const editorial = { order_id: 42, order_status: "DRAFT", editable: true, order_blocks: [], items: [] };

describe("PersonnelOrderTemplateApplication", () => {
  beforeEach(() => {
    vi.mocked(previewPersonnelOrderTemplateApplication).mockReset();
    vi.mocked(applyPersonnelOrderTemplateApplication).mockReset();
    vi.mocked(previewPersonnelOrderTemplateApplication).mockResolvedValue(preview());
    vi.mocked(applyPersonnelOrderTemplateApplication).mockResolvedValue(editorial);
  });
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  it("renders the published version and bilingual comparison without applying on mount", async () => {
    render(<PersonnelOrderTemplateApplication orderId={42} onApplied={vi.fn()} />);
    expect(await screen.findByTestId("template-application-diff")).toHaveTextContent("proposed ru body_template");
    expect(screen.getByTestId("template-application-ru-basis-proposed")).toHaveTextContent("Личное заявление");
    expect(screen.getByTestId("template-application-kk-basis-proposed")).toHaveTextContent("Жеке өтініш");
    expect(screen.getByTestId("template-application-template-meta")).toHaveTextContent("TERMINATION · PUBLISHED · версия 3");
    for (const block of ["title", "preamble", "body", "basis"]) {
      const grid = screen.getByTestId(`template-application-grid-${block}`);
      expect(grid).toHaveClass("grid-cols-1", "md:grid-cols-4");
      for (const locale of ["ru", "kk"]) {
        expect(screen.getByTestId(`template-application-${locale}-${block}-proposed`)).toHaveTextContent(`${locale.toUpperCase()} · По шаблону`);
        expect(screen.getByTestId(`template-application-${locale}-${block}-current`)).toHaveTextContent(`${locale.toUpperCase()} · Было`);
        expect(screen.getByTestId(`template-application-${locale}-${block}-proposed`)).toHaveClass("h-full");
        expect(screen.getByTestId(`template-application-${locale}-${block}-current`)).toHaveClass("h-full");
      }
    }
    expect(applyPersonnelOrderTemplateApplication).not.toHaveBeenCalled();
  });

  it("reloads the read-only preview when item data has been saved", async () => {
    const { rerender } = render(<PersonnelOrderTemplateApplication orderId={42} refreshKey={0} onApplied={vi.fn()} />);
    await screen.findByTestId("template-application-diff");
    rerender(<PersonnelOrderTemplateApplication orderId={42} refreshKey={1} onApplied={vi.fn()} />);
    await waitFor(() => expect(previewPersonnelOrderTemplateApplication).toHaveBeenCalledTimes(2));
    expect(applyPersonnelOrderTemplateApplication).not.toHaveBeenCalled();
  });

  it("applies only after the operator clicks the action", async () => {
    const onApplied = vi.fn();
    render(<PersonnelOrderTemplateApplication orderId={42} onApplied={onApplied} />);
    fireEvent.click(await screen.findByRole("button", { name: "Применить шаблон" }));
    await waitFor(() => expect(applyPersonnelOrderTemplateApplication).toHaveBeenCalledWith(42, { expected_document_revision: 5, confirm_replace_overrides: true, confirm_reapply: true }));
    expect(onApplied).toHaveBeenCalledWith(editorial);
  });

  it("keeps the section visible and names the missing requisite for a validation error", async () => {
    vi.mocked(previewPersonnelOrderTemplateApplication).mockRejectedValue(new Error("Required template data is missing: termination.reason"));
    render(<PersonnelOrderTemplateApplication orderId={42} onApplied={vi.fn()} />);
    expect(await screen.findByTestId("personnel-order-template-application")).toHaveTextContent("Шаблон приказа");
    expect(screen.getByRole("alert")).toHaveTextContent("Не хватает реквизита: причина увольнения.");
    expect(applyPersonnelOrderTemplateApplication).not.toHaveBeenCalled();
  });

  it("reports a missing published template without hiding the section", async () => {
    vi.mocked(previewPersonnelOrderTemplateApplication).mockRejectedValue(new Error("No PUBLISHED template exists for this item type."));
    render(<PersonnelOrderTemplateApplication orderId={42} onApplied={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Опубликованный шаблон не найден.");
  });

  it("shows a safe diagnostic for an unexpected preview error", async () => {
    vi.mocked(previewPersonnelOrderTemplateApplication).mockRejectedValue(new Error("500 database password=secret"));
    render(<PersonnelOrderTemplateApplication orderId={42} onApplied={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Не удалось проверить шаблон приказа.");
    expect(screen.queryByText(/password=secret/)).not.toBeInTheDocument();
  });

  it("requires separate override and reapply confirmations", async () => {
    vi.mocked(previewPersonnelOrderTemplateApplication).mockResolvedValue(preview(true, true));
    render(<PersonnelOrderTemplateApplication orderId={42} onApplied={vi.fn()} />);
    expect(await screen.findByTestId("template-application-override-blocks")).toHaveTextContent("ORDER");
    expect(screen.getByRole("button", { name: "Применить шаблон" })).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Подтверждаю замену ручных правок"));
    fireEvent.click(screen.getByLabelText("Подтверждаю повторное применение"));
    expect(screen.getByRole("button", { name: "Применить шаблон" })).toBeEnabled();
  });
});
