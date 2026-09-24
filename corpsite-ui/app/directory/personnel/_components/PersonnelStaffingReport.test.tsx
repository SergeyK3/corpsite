import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PersonnelStaffingReport from "./PersonnelStaffingReport";

const { getPersonnelReportOptions, getStaffingReport } = vi.hoisted(() => ({
  getPersonnelReportOptions: vi.fn().mockResolvedValue({ groups: [{ group_id: 1, group_name: "Группа A" }], departments: [{ unit_id: 10, unit_name: "Отдел A", group_id: 1 }] }),
  getStaffingReport: vi.fn().mockResolvedValue({ data_quality: { requires_review: true, message: "Данные требуют проверки" }, metrics: { current_headcount: 4, hired: 2, terminated: 1, average_headcount: 3.5, average_formula: "Сумма / дни", turnover_numerator: 1, turnover_percent: 28.57, turnover_reasons: [{ reason: "Увольнение по собственному желанию", count: 1 }] }, hired_items: [{ full_name: "Иванов И.И.", date: "2026-01-02", org_unit_id: 10 }], terminated_items: [{ full_name: "Петров П.П.", date: "2026-01-03", reason: "Причина не классифицирована", org_unit_id: 10 }], breakdown: [] }),
}));
vi.mock("../_lib/personnelReportsApi.client", () => ({ getPersonnelReportOptions, getStaffingReport }));

describe("PersonnelStaffingReport", () => {
  it("renders filters, quality warning and turnover calculation details", async () => {
    render(<PersonnelStaffingReport />);
    expect(await screen.findByRole("heading", { name: "Отчёты по кадровому составу" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Период" })).toHaveValue("ytd");
    expect(await screen.findByText("Данные требуют проверки")).toBeInTheDocument();
    expect(screen.getByText(/1 \/ 3.5 × 100% = 28.57%/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Дата с"), { target: { value: "2026-01-02" } });
    await waitFor(() => expect(screen.getByRole("combobox", { name: "Период" })).toHaveValue("custom"));
    fireEvent.click(screen.getAllByRole("button", { name: "Открыть список" })[0]);
    expect(screen.getByText(/Иванов И\.И\./)).toBeInTheDocument();
  });
});
