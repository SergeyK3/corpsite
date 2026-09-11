import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MigrationStatusMatrixPageClient from "./MigrationStatusMatrixPageClient";

const listMock = vi.fn(); const matrixMock = vi.fn(); const replaceMock = vi.fn();
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: replaceMock }), usePathname: () => "/directory/personnel/migration-status", useSearchParams: () => search }));
vi.mock("../_lib/migrationStatusApi.client", async () => {
  const actual = await vi.importActual<object>("../_lib/migrationStatusApi.client");
  return { ...actual, listMigrationStatusUniverses: () => listMock(), getMigrationStatusMatrix: (...args: unknown[]) => matrixMock(...args) };
});

const universe = { universe_id: 7, base_cohort_run_id: 2, supplemental_cohort_run_ids: [], calculated_at: "2026-01-01T00:00:00Z" };
const report = { universe_id: 7, page: 1, page_size: 50, total: 2, counts: [], items: [{ person_id: 9, employee_context_id: 1, org_unit_id: 2, full_name: "Иванов Иван", cells: { general: { status_code: "ACCEPTED", status_label: "Согласовано", reason_code: "RUN_PARTICIPANT_ACCEPTED", reason_label: "Подтверждено", calculated_at: "2026-01-01T00:00:00Z" }, education: { status_code: "NOT_STARTED", status_label: "Не начато", reason_code: "RUN_NO_SECTION_RESULT", reason_label: "Нет результата", calculated_at: "2026-01-01T00:00:00Z" }, training: { status_code: "ERROR", status_label: "Ошибка", reason_code: "RUN_ERROR", reason_label: "Нужна проверка", calculated_at: "2026-01-01T00:00:00Z" } } }] };

describe("MigrationStatusMatrixPageClient", () => {
  beforeEach(() => { search = new URLSearchParams("universe_id=7&page=2&q=иванов"); listMock.mockReset(); matrixMock.mockReset(); replaceMock.mockReset(); listMock.mockResolvedValue({ items: [universe] }); matrixMock.mockResolvedValue(report); });
  afterEach(cleanup);
  it("renders three text-first columns and safe card links", async () => {
    render(<MigrationStatusMatrixPageClient />);
    const table = await screen.findByTestId("migration-status-matrix");
    expect(table.querySelectorAll("th")).toHaveLength(5);
    expect(table.querySelectorAll("strong")).toHaveLength(3);
    expect(table.querySelectorAll("td span")).toHaveLength(3);
    expect(table.querySelector("a")?.getAttribute("href")).toContain("section=general&migration_universe_id=7&return_to=");
  });
  it("auto-selects one universe and requires selection for several", async () => {
    search = new URLSearchParams(); render(<MigrationStatusMatrixPageClient />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/directory/personnel/migration-status?universe_id=7")); cleanup();
    listMock.mockResolvedValue({ items: [universe, { ...universe, universe_id: 8 }] }); render(<MigrationStatusMatrixPageClient />);
    await waitFor(() => expect(screen.getByTestId("migration-status-choose-universe")).toBeInTheDocument());
  });
  it("resets page for filters and refreshes through GET clients", async () => {
    render(<MigrationStatusMatrixPageClient />); await screen.findByTestId("migration-status-matrix");
    expect(screen.getByLabelText("Статус")).toHaveTextContent("Согласовано");
    expect(screen.getByLabelText("Причина")).toHaveTextContent("Конфликт разбора ФИО");
    fireEvent.change(screen.getByLabelText("Статус"), { target: { value: "ACCEPTED" } });
    expect(replaceMock).toHaveBeenCalledWith("/directory/personnel/migration-status?universe_id=7&q=%D0%B8%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2&status=ACCEPTED");
    const before = listMock.mock.calls.length; fireEvent.click(screen.getByTestId("migration-status-refresh")); await waitFor(() => expect(listMock.mock.calls.length).toBeGreaterThan(before));
  });
});
