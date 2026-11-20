import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ listHireApprovals: vi.fn(), recordHireVisa: vi.fn() }));
vi.mock("../_lib/electronicHireApi.client", () => api);

import HireApprovalsClient from "./HireApprovalsClient";

const candidate = {
  application_id: 54,
  full_name: "Тестова Дана Ермековна",
  org_unit: "Тестовое отделение трансфузиологии",
  position: "Инженер",
  employment_rate: "0.50",
  planned_start_date: "2026-12-05",
};
const approved = {
  ...candidate,
  current_visa: {
    decision: "approved", is_current: true, explanation: null,
    decided_by_user_id: 6, decided_by_name: "Вымышленный Руководитель Нурлан",
    decided_at: "2026-11-20T06:22:56.939311+00:00",
  },
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.history.replaceState({}, "", "/");
});

describe("HireApprovalsClient", () => {
  it("separates pending from approved and rejected applications", async () => {
    api.listHireApprovals.mockResolvedValue({ items: [
      { ...candidate, application_id: 56, current_visa: null },
      approved,
      { ...approved, application_id: 25, current_visa: {
        ...approved.current_visa, decision: "rejected", explanation: "Изменить дату",
      } },
    ] });
    render(<HireApprovalsClient />);
    expect(await screen.findByText(/Заявление №56/)).toBeInTheDocument();
    expect(screen.queryByText(/Заявление №54/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Заявление №25/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Отработано" }));
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "№54" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "№25" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Тип заявления" })).toBeInTheDocument();
    expect(screen.getByText("Изменить дату")).toBeInTheDocument();
    expect(screen.queryByText(/Заявление №56/)).not.toBeInTheDocument();
  });

  it("shows a persisted visa with author and local time, and hides decision controls", async () => {
    api.listHireApprovals.mockResolvedValue({ items: [approved] });
    render(<HireApprovalsClient />);

    expect(await screen.findByText("Заявлений на согласование нет.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Отработано" }));
    expect(await screen.findByText(/Вымышленный Руководитель Нурлан/)).toBeInTheDocument();
    expect(screen.getByText("0,50")).toBeInTheDocument();
    expect(screen.getByText("05.12.2026")).toBeInTheDocument();
    expect(screen.getByText(/20\.11\.2026.*11:22/)).toBeInTheDocument();
    expect(screen.getByText("Тестовое отделение трансфузиологии")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Согласен" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Не согласен" })).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Пояснение при отказе" })).not.toBeInTheDocument();
  });

  it("confirms only after the server succeeds and blocks repeat clicks while saving", async () => {
    let finishVisa: (value: unknown) => void = () => {};
    api.recordHireVisa.mockImplementation(() => new Promise(resolve => { finishVisa = resolve; }));
    api.listHireApprovals.mockResolvedValueOnce({ items: [{ ...candidate, current_visa: null }] })
      .mockResolvedValueOnce({ items: [approved] });
    render(<HireApprovalsClient />);

    const approve = await screen.findByRole("button", { name: "Согласен" });
    fireEvent.click(approve);
    expect(api.recordHireVisa).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Заявление №54 согласовано")).not.toBeInTheDocument();
    const saving = screen.getByRole("button", { name: "Сохранение…" });
    expect(saving).toBeDisabled();
    fireEvent.click(saving);
    expect(api.recordHireVisa).toHaveBeenCalledTimes(1);

    finishVisa({ decision: "approved" });
    expect(await screen.findByRole("status")).toHaveTextContent("Заявление №54 согласовано");
    expect(screen.getByRole("button", { name: "Вернуться к ожидающим согласования" })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("button", { name: "Согласен" })).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Вернуться к ожидающим согласования" }));
    expect(screen.getByText("Заявлений на согласование нет.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Отработано" }));
    expect(screen.getAllByText(/Вымышленный Руководитель Нурлан/).length).toBeGreaterThan(0);
  });

  it("leaves the decision form available when the server rejects the save", async () => {
    api.listHireApprovals.mockResolvedValue({ items: [{ ...candidate, current_visa: null }] });
    api.recordHireVisa.mockRejectedValue(new Error("Сохранение не выполнено"));
    render(<HireApprovalsClient />);
    fireEvent.click(await screen.findByRole("button", { name: "Согласен" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Сохранение не выполнено");
    expect(screen.queryByText("Заявление №54 согласовано")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Согласен" })).toBeEnabled();
  });

  it("routes a completed task link to worked and returns a changed application to pending with history", async () => {
    window.history.replaceState({}, "", "/directory/personnel/hire-approvals?application_id=54#hire-approval-54");
    api.listHireApprovals.mockResolvedValueOnce({ items: [{ ...approved,
      current_visa: { ...approved.current_visa, visa_id: 9 }, visa_history: [
      { ...approved.current_visa, visa_id: 9 },
    ] }] }).mockResolvedValueOnce({ items: [{ ...approved, current_visa: {
      ...approved.current_visa, is_current: false, visa_id: 9,
    }, visa_history: [
      { ...approved.current_visa, is_current: false, visa_id: 9 },
      { ...approved.current_visa, is_current: false, visa_id: 8, decision: "rejected", explanation: "Старая дата" },
    ] }] });
    const { unmount } = render(<HireApprovalsClient />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Отработано" })).toHaveAttribute("aria-current", "page"));
    expect(screen.getAllByText(/Вымышленный Руководитель Нурлан/).length).toBeGreaterThan(0);
    unmount();

    render(<HireApprovalsClient />);
    await waitFor(() => expect(screen.getByRole("button", { name: "На согласовании" })).toHaveAttribute("aria-current", "page"));
    expect(screen.getByRole("button", { name: "Согласен" })).toBeInTheDocument();
    fireEvent.click(screen.getByText("История виз (2)"));
    expect(screen.getByText(/Старая дата/)).toBeInTheDocument();
    expect(api.listHireApprovals).toHaveBeenCalledWith(54);
  });

  it("shows paper consent as a recorded confirmation and expands a long note", async () => {
    const note = "Подписанный документ получен кадровиком. ".repeat(5);
    api.listHireApprovals.mockResolvedValue({items: [{...approved, application_id: 70,
      approval_mode: "paper", current_visa: {...approved.current_visa, kind: "paper",
        approved_on: "2026-11-20", recorded_by_name: "Вымышленный кадровик", explanation: note},
      paper_history: []}]});
    render(<HireApprovalsClient />);
    fireEvent.click(await screen.findByRole("button", {name: "Отработано"}));
    expect(screen.getByRole("cell", {name: "Согласовано на бумаге"})).toBeInTheDocument();
    expect(screen.getByText(/Внёс: Вымышленный кадровик/)).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Подписанный документ получен кадровиком.*…/));
    expect(screen.getByText(note.trim())).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", {name: "№70"}));
    expect(screen.getByText(/Кто внёс подтверждение:/)).toBeInTheDocument();
    expect(screen.queryByRole("button", {name: "Согласен"})).not.toBeInTheDocument();
  });
});
