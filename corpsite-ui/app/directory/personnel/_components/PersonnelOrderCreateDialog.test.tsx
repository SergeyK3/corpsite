import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import PersonnelOrderCreateDialog from "./PersonnelOrderCreateDialog";

vi.mock("../_lib/personnelOrdersApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelOrdersApi.client")>("../_lib/personnelOrdersApi.client");
  return { ...actual, previewPersonnelOrderHeaderDuplicate: vi.fn(), createManualPersonnelOrderDraft: vi.fn() };
});
import { createManualPersonnelOrderDraft, previewPersonnelOrderHeaderDuplicate } from "../_lib/personnelOrdersApi.client";

afterEach(() => { cleanup(); vi.clearAllMocks(); });
function fill() { fireEvent.change(screen.getByLabelText("Номер приказа"), { target: { value: "M-1" } }); fireEvent.change(screen.getByLabelText("Дата приказа"), { target: { value: "2026-09-25" } }); fireEvent.change(screen.getByLabelText("Исходное название"), { target: { value: "Атауы" } }); fireEvent.change(screen.getByLabelText("Сотрудник"), { target: { value: "7" } }); fireEvent.change(screen.getByLabelText("Дата действия"), { target: { value: "2026-10-01" } }); }

it("validates fields, previews duplicates, confirms warning, and opens the created order", async () => {
  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({ blocking: false, warnings: ["SAME_NUMBER_DIFFERENT_DATE"], candidates: [] });
  vi.mocked(createManualPersonnelOrderDraft).mockResolvedValue({ order_id: 77, order_number: "M-1", order_type_code: "HIRE", status: "DRAFT", source_mode: "MANUAL", document_revision: 1, document_review_state: "NEEDS_REVIEW" });
  const onCreated = vi.fn(); const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
  render(<PersonnelOrderCreateDialog open onClose={vi.fn()} onCreated={onCreated} />);
  expect(screen.getByTestId("personnel-order-create-dialog")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Создать приказ" }));
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
  fill(); fireEvent.click(screen.getByRole("button", { name: "Создать приказ" }));
  await waitFor(() => expect(previewPersonnelOrderHeaderDuplicate).toHaveBeenCalled());
  await waitFor(() => expect(confirm).toHaveBeenCalled());
  await waitFor(() => expect(createManualPersonnelOrderDraft).toHaveBeenCalledWith(expect.objectContaining({ order_number: "M-1", employee_id: 7, effective_date: "2026-10-01" })));
  expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ order_id: 77 })); confirm.mockRestore();
});

it("blocks save when duplicate preview is blocking", async () => {
  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({ blocking: true, warnings: [], candidates: [] });
  render(<PersonnelOrderCreateDialog open onClose={vi.fn()} onCreated={vi.fn()} />); fill(); fireEvent.click(screen.getByRole("button", { name: "Создать приказ" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("таким же номером и датой"); expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});
