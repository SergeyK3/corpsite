import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TechnicalPersonnelOrdersPanel from "./TechnicalPersonnelOrdersPanel";
import { apiFetchJson } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiFetchJson: vi.fn() }));

const confirmed = { order_id: 12, order_number: "TECH-12", order_date: "2026-01-02", order_type_code: "HIRE", status: "DRAFT", classification: "CONFIRMED_TECHNICAL", employees: ["Тест"], employee_details: [] };
const legacy = { order_id: 11, order_number: "PERSONNEL-IMPORT-2026-11", order_date: "2026-01-01", order_type_code: "HIRE", status: "SIGNED", classification: "LEGACY_TECHNICAL_CANDIDATE", employees: ["Тест"], employee_details: [] };
const listing = { items: [confirmed, legacy], page: 1, page_size: 25, total: 26 };
const fiftyConfirmed = Array.from({ length: 50 }, (_, index) => ({ ...confirmed, order_id: index + 1, order_number: `TECH-${index + 1}` }));

beforeEach(() => vi.mocked(apiFetchJson).mockReset());
afterEach(cleanup);

describe("TechnicalPersonnelOrdersPanel", () => {
  it("loads the first page automatically, keeps legacy out of selection, and prepares an exact batch preview", async () => {
    vi.mocked(apiFetchJson).mockResolvedValueOnce(listing).mockResolvedValueOnce({ ready: [{ order_id: 12 }], legacy: [], blocked: [], planned_deletions: [], confirmation_phrase: "DELETE TECHNICAL ORDERS 1", can_execute: true });
    render(<TechnicalPersonnelOrdersPanel />);
    await waitFor(() => expect(apiFetchJson).toHaveBeenCalledWith(expect.stringContaining("/search?page=1&page_size=25")));
    expect(screen.getByText("Техническая запись прежнего формата")).toBeInTheDocument();
    expect(screen.getByLabelText("Выбрать приказ 11")).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Выбрать доступные на странице"));
    expect(screen.getByLabelText("Выбрать приказ 12")).toBeChecked();
    expect(screen.getByLabelText("Выбрать приказ 11")).not.toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Подготовить удаление выбранных" }));
    await waitFor(() => expect(apiFetchJson).toHaveBeenCalledWith("/directory/technical-personnel-order-cleanup/batch-preview", expect.objectContaining({ method: "POST", body: JSON.stringify({ order_ids: [12] }) })));
    expect(await screen.findByText("Batch preview")).toBeInTheDocument();
  });

  it("uses page controls and preserves explicit search fields", async () => {
    vi.mocked(apiFetchJson).mockResolvedValueOnce(listing).mockResolvedValueOnce({ ...listing, page: 2, items: [confirmed] });
    render(<TechnicalPersonnelOrdersPanel />);
    await screen.findByText("TECH-12");
    fireEvent.change(screen.getByLabelText("Поле поиска технического приказа"), { target: { value: "employee_name" } });
    fireEvent.change(screen.getByLabelText("Поиск технического приказа"), { target: { value: "Ильясова" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    await waitFor(() => expect(apiFetchJson).toHaveBeenLastCalledWith(expect.stringContaining("employee_name=%D0%98%D0%BB%D1%8C%D1%8F%D1%81%D0%BE%D0%B2%D0%B0")));
  });

  it("caps a 50-row page at 25 selections, unlocks the next box after removal, and clears selection on search and page changes", async () => {
    vi.mocked(apiFetchJson)
      .mockResolvedValueOnce(listing)
      .mockResolvedValueOnce({ items: fiftyConfirmed, page: 1, page_size: 50, total: 100 })
      .mockResolvedValueOnce({ items: fiftyConfirmed, page: 1, page_size: 50, total: 100 })
      .mockResolvedValueOnce({ items: fiftyConfirmed, page: 2, page_size: 50, total: 100 });
    render(<TechnicalPersonnelOrdersPanel />);
    await screen.findByText("TECH-12");
    fireEvent.change(screen.getByLabelText("Размер страницы"), { target: { value: "50" } });
    await screen.findByText("TECH-50");
    fireEvent.click(screen.getByLabelText("Выбрать доступные на странице"));
    expect(screen.getByRole("status")).toHaveTextContent("Выбрано: 25 из 25");
    expect(screen.getByText("Выбрано 25 — максимальный размер одной операции")).toBeInTheDocument();
    expect(screen.getByLabelText("Выбрать приказ 26")).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Выбрать приказ 1"));
    expect(screen.getByLabelText("Выбрать приказ 26")).not.toBeDisabled();
    fireEvent.click(screen.getByLabelText("Выбрать приказ 26"));
    expect(screen.getByRole("status")).toHaveTextContent("Выбрано: 25 из 25");
    fireEvent.change(screen.getByLabelText("Поиск технического приказа"), { target: { value: "TECH" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    expect(screen.getByRole("status")).toHaveTextContent("Выбрано: 0 из 25");
    await waitFor(() => expect(apiFetchJson).toHaveBeenLastCalledWith(expect.stringContaining("q=TECH")));
    fireEvent.click(screen.getByLabelText("Выбрать приказ 1"));
    fireEvent.click(screen.getByRole("button", { name: "Вперёд" }));
    expect(screen.getByRole("status")).toHaveTextContent("Выбрано: 0 из 25");
  });
});
