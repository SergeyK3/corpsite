import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MigrationStatusMatrixPageClient from "./MigrationStatusMatrixPageClient";

const listMock = vi.fn(); const matrixMock = vi.fn(); const replaceMock = vi.fn(); const router = { replace: replaceMock };
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/directory/personnel/migration-status", useSearchParams: () => search }));
vi.mock("../_lib/migrationStatusApi.client", async () => {
  const actual = await vi.importActual<object>("../_lib/migrationStatusApi.client");
  return { ...actual, listMigrationStatusUniverses: () => listMock(), getMigrationStatusMatrix: (...args: unknown[]) => matrixMock(...args) };
});

const universe = { universe_id: 7, base_cohort_run_id: 2, supplemental_cohort_run_ids: [], calculated_at: "2026-01-01T00:00:00Z" };
const calculatedAt = "2026-01-01T00:00:00Z";
const cell = (status_label: string, reason_label: string) => ({ status_code: status_label === "Не применимо" ? "NOT_APPLICABLE" : "NOT_STARTED", status_label, reason_code: "SECTION_PROCESSING_NOT_CONNECTED", reason_label, calculated_at: calculatedAt });
const report = {
  universe_id: 7, page: 1, page_size: 50, total: 2, counts: [], items: [{ person_id: 9, employee_context_id: 1, org_unit_id: 2, full_name: "Иванов Иван", cells: {
    general: { ...cell("Согласовано", "Подтверждено"), status_code: "ACCEPTED" },
    education: cell("Не начато", "Нет результата"), training: cell("Ошибка", "Нужна проверка"),
    relatives: cell("Не начато", "Обработка раздела ещё не подключена"), military: cell("Не применимо", "Раздел не применяется"),
    employment_biography: cell("Не начато", "Обработка раздела ещё не подключена"), employment_history: cell("Не начато", "Обработка раздела ещё не подключена"),
    foreign_languages: cell("Не начато", "Обработка раздела ещё не подключена"), awards: cell("Не начато", "Обработка раздела ещё не подключена"), academic_degrees_titles: cell("Не начато", "Обработка раздела ещё не подключена"),
  } }],
};

describe("MigrationStatusMatrixPageClient", () => {
  beforeEach(() => { search = new URLSearchParams("universe_id=7&page=2&q=иванов"); listMock.mockReset(); matrixMock.mockReset(); replaceMock.mockReset(); listMock.mockResolvedValue({ items: [universe] }); matrixMock.mockResolvedValue(report); });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("renders the ten API-ordered text-first columns in a horizontally scrolling table with a sticky employee column", async () => {
    render(<MigrationStatusMatrixPageClient />);
    const table = await screen.findByTestId("migration-status-matrix");
    expect(Array.from(table.querySelectorAll("thead th")).map((header) => header.textContent)).toEqual([
      "Сотрудник", "Общие сведения", "Образование", "Обучение и повышение квалификации", "Родственники", "Воинский учёт", "Трудовая биография", "Трудовая деятельность / послужной список", "Знание иностранных языков", "Награды", "Учёные степени и звания",
    ]);
    expect(table.querySelectorAll("tbody td")).toHaveLength(10);
    expect(screen.getByTestId("migration-status-table-scroll").className).toContain("overflow-x-scroll");
    expect(screen.getByTestId("migration-status-table-scroll").className).toContain("w-full");
    expect(table.className).toContain("min-w-[2200px]");
    expect(screen.getByTestId("migration-status-employee-header").className).toContain("sticky");
    expect(screen.getByTestId("migration-status-employee-cell").className).toContain("sticky");
    expect(table).toHaveTextContent("Не начато");
    expect(table).toHaveTextContent("Не применимо");
  });

  it("uses existing personal-card anchors and preserves the universe and full report return URL", async () => {
    render(<MigrationStatusMatrixPageClient />);
    const table = await screen.findByTestId("migration-status-matrix");
    const hrefFor = (label: string) => Array.from(table.querySelectorAll("a")).find((link) => link.getAttribute("aria-label")?.startsWith(label))?.getAttribute("href") ?? "";
    expect(hrefFor("Родственники")).toContain("section=family&migration_universe_id=7&return_to=");
    expect(hrefFor("Воинский учёт")).toContain("section=military&migration_universe_id=7&return_to=");
    expect(hrefFor("Трудовая деятельность / послужной список")).toContain("section=assignment&migration_universe_id=7&return_to=");
    expect(hrefFor("Знание иностранных языков")).toContain("section=additional&migration_universe_id=7&return_to=");
    expect(hrefFor("Награды")).toContain("section=additional&migration_universe_id=7&return_to=");
    expect(hrefFor("Учёные степени и звания")).toContain("section=additional&migration_universe_id=7&return_to=");
  });

  it("keeps a visible horizontal scrollbar control before pagination when the table overflows", async () => {
    vi.spyOn(HTMLElement.prototype, "scrollWidth", "get").mockReturnValue(3145);
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(1359);
    render(<MigrationStatusMatrixPageClient />);
    expect(await screen.findByTestId("migration-status-scrollbar-control")).toHaveAttribute("max", "1786");
  });

  it("keeps the filters, permission-gated universe selection and GET refresh behavior", async () => {
    render(<MigrationStatusMatrixPageClient />); await screen.findByTestId("migration-status-matrix");
    expect(screen.getByLabelText("Раздел")).toHaveTextContent("Учёные степени и звания");
    fireEvent.change(screen.getByLabelText("Статус"), { target: { value: "ACCEPTED" } });
    expect(replaceMock).toHaveBeenCalledWith("/directory/personnel/migration-status?universe_id=7&q=%D0%B8%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2&status=ACCEPTED");
    const before = listMock.mock.calls.length; fireEvent.click(screen.getByTestId("migration-status-refresh")); await waitFor(() => expect(listMock.mock.calls.length).toBeGreaterThan(before));
  });

  it("auto-selects one accessible universe and requires a selection when several are accessible", async () => {
    search = new URLSearchParams(); render(<MigrationStatusMatrixPageClient />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/directory/personnel/migration-status?universe_id=7")); cleanup();
    listMock.mockResolvedValue({ items: [universe, { ...universe, universe_id: 8 }] }); render(<MigrationStatusMatrixPageClient />);
    await waitFor(() => expect(screen.getByTestId("migration-status-choose-universe")).toBeInTheDocument());
  });

  it("keeps the existing permission gate when the report API denies access", async () => {
    listMock.mockRejectedValue({ status: 403 });
    render(<MigrationStatusMatrixPageClient />);
    expect(await screen.findByTestId("migration-status-forbidden")).toHaveTextContent("Недостаточно прав");
  });
});
