import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TechnicalPersonnelOrdersPanel from "./TechnicalPersonnelOrdersPanel";
import { apiFetchJson } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiFetchJson: vi.fn() }));

const legacy = { order_id: 11, order_number: "PERSONNEL-IMPORT-2026-11", order_date: "2026-01-01", order_type_code: "HIRE", status: "SIGNED", classification: "LEGACY_TECHNICAL_CANDIDATE", employees: ["Тест"] };
const confirmed = { ...legacy, order_id: 12, classification: "CONFIRMED_TECHNICAL" };
const provenancePreview = { classification: "LEGACY_TECHNICAL_CANDIDATE", can_delete: false, can_confirm_provenance: true, confirmation_phrase: "CONFIRM TECHNICAL ORDER 11", planned_deletions: [{ table: "personnel_orders", count: 1 }], blocking_dependencies: [] };
const blockedPreview = { classification: "CONFIRMED_TECHNICAL", can_delete: false, confirmation_phrase: "DELETE TECHNICAL ORDER 12", planned_deletions: [], blocking_dependencies: [{ table: "employee_events", count: 1 }] };
const isolatedPreview = { classification: "CONFIRMED_TECHNICAL", can_delete: true, confirmation_phrase: "DELETE TECHNICAL ORDER 12", planned_deletions: [{ table: "personnel_orders", count: 1 }], blocking_dependencies: [] };

function search() { return screen.getByRole("button", { name: "Найти" }); }

beforeEach(() => vi.mocked(apiFetchJson).mockReset());
afterEach(cleanup);

describe("TechnicalPersonnelOrdersPanel", () => {
  it("searches legacy candidates, requires provenance reason/phrase, then refreshes as confirmed", async () => {
    vi.mocked(apiFetchJson)
      .mockResolvedValueOnce({ items: [legacy] })
      .mockResolvedValueOnce(provenancePreview)
      .mockResolvedValueOnce({ status: "COMPLETED" })
      .mockResolvedValueOnce({ items: [{ ...legacy, classification: "CONFIRMED_TECHNICAL" }] });
    render(<TechnicalPersonnelOrdersPanel />);
    fireEvent.change(screen.getByLabelText("Поиск технического приказа"), { target: { value: "PERSONNEL-IMPORT-2026-11" } });
    fireEvent.click(search());
    await waitFor(() => expect(screen.getAllByText(/LEGACY_TECHNICAL_CANDIDATE/).length).toBeGreaterThan(0));
    expect(screen.queryByRole("button", { name: "Удалить один приказ" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить техническое происхождение" }));
    await screen.findByText("Preview #11");
    expect(apiFetchJson).toHaveBeenCalledWith("/directory/technical-personnel-order-cleanup/11/provenance-preview");
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить происхождение" }));
    expect(screen.getByRole("status")).toHaveTextContent("Укажите причину");
    expect(apiFetchJson).toHaveBeenCalledTimes(2);
    fireEvent.change(screen.getByLabelText("Причина операции"), { target: { value: "legacy import verified" } });
    fireEvent.change(screen.getByLabelText("Фраза подтверждения"), { target: { value: "CONFIRM TECHNICAL ORDER 11" } });
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить происхождение" }));
    await waitFor(() => expect(apiFetchJson).toHaveBeenCalledWith("/directory/technical-personnel-order-cleanup/11/confirm-provenance", expect.objectContaining({ method: "POST" })));
    await waitFor(() => expect(screen.getAllByText(/CONFIRMED_TECHNICAL/).length).toBeGreaterThan(0));
  });

  it("shows delete blockers, permits an isolated delete only after its own phrase, and displays one API error safely", async () => {
    vi.mocked(apiFetchJson)
      .mockResolvedValueOnce({ items: [confirmed] })
      .mockResolvedValueOnce(blockedPreview)
      .mockResolvedValueOnce(isolatedPreview)
      .mockRejectedValueOnce(new Error("API unavailable"));
    render(<TechnicalPersonnelOrdersPanel />);
    fireEvent.click(search());
    await waitFor(() => expect(screen.getAllByText(/CONFIRMED_TECHNICAL/).length).toBeGreaterThan(0));
    fireEvent.click(screen.getByRole("button", { name: "Preview удаления" }));
    expect(await screen.findByText(/employee_events/)).toBeInTheDocument();
    expect(screen.getByText("Операция заблокирована.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Preview удаления" }));
    await screen.findByRole("button", { name: "Удалить один приказ" });
    fireEvent.change(screen.getByLabelText("Причина операции"), { target: { value: "isolated test" } });
    fireEvent.click(screen.getByRole("button", { name: "Удалить один приказ" }));
    expect(screen.getByRole("status")).toHaveTextContent("Укажите причину");
    fireEvent.change(screen.getByLabelText("Фраза подтверждения"), { target: { value: "DELETE TECHNICAL ORDER 12" } });
    fireEvent.click(screen.getByRole("button", { name: "Удалить один приказ" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("API unavailable"));
    expect(apiFetchJson).toHaveBeenCalledTimes(4);
  });
});
