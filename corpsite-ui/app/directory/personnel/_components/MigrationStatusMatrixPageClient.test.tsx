import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MigrationStatusMatrixPageClient from "./MigrationStatusMatrixPageClient";

const listMock = vi.fn(); const matrixMock = vi.fn(); const rebuildMock = vi.fn(); const replaceMock = vi.fn(); const router = { replace: replaceMock };
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({ useRouter: () => router, usePathname: () => "/directory/personnel/migration-status", useSearchParams: () => search }));
vi.mock("../_lib/migrationStatusApi.client", async () => {
  const actual = await vi.importActual<object>("../_lib/migrationStatusApi.client");
  return { ...actual, listMigrationStatusUniverses: () => listMock(), getMigrationStatusMatrix: (...args: unknown[]) => matrixMock(...args), rebuildMigrationStatusUniverse: (...args: unknown[]) => rebuildMock(...args) };
});

const universe = { universe_id: 7, base_cohort_run_id: 2, supplemental_cohort_run_ids: [], calculated_at: "2026-01-01T00:00:00Z" };
const calculatedAt = "2026-01-01T00:00:00Z";
const cell = (status_label: string, reason_label: string) => ({ status_code: status_label === "Не применимо" ? "NOT_APPLICABLE" : "NOT_STARTED", status_label, reason_code: "SECTION_PROCESSING_NOT_CONNECTED", reason_label, calculated_at: calculatedAt });
const report = {
  universe_id: 7, page: 1, page_size: 50, total: 2, counts: [],
  general_summary: { total_active_employees: 593, processed: 546, review_required: 47, updated_current_run: 0, skipped_already_filled: 546 },
  status_summary: {
    sections: [
      { code: "general", title: "Общие сведения", order: 10 },
      { code: "employment_biography", title: "Трудовая биография", order: 70 },
      { code: "employment_history", title: "Трудовая деятельность", order: 80 },
    ],
    statuses: [
      { code: "AUTO_READY", title: "Готово к согласованию / обработано автоматически", order: 10 },
      { code: "REVIEW_REQUIRED", title: "Требуется ручная проверка", order: 20 },
      { code: "NO_SOURCE_DATA", title: "Нет данных или не обработано", order: 60 },
    ],
    counts: [
      { section_code: "general", status_code: "AUTO_READY", count: 1 },
      { section_code: "general", status_code: "REVIEW_REQUIRED", count: 1 },
      { section_code: "general", status_code: "NO_SOURCE_DATA", count: 0 },
      { section_code: "employment_biography", status_code: "AUTO_READY", count: 0 },
      { section_code: "employment_biography", status_code: "REVIEW_REQUIRED", count: 0 },
      { section_code: "employment_biography", status_code: "NO_SOURCE_DATA", count: 2 },
      { section_code: "employment_history", status_code: "AUTO_READY", count: 0 },
      { section_code: "employment_history", status_code: "REVIEW_REQUIRED", count: 0 },
      { section_code: "employment_history", status_code: "NO_SOURCE_DATA", count: 2 },
    ],
  },
  items: [{ person_id: 9, employee_context_id: 1, org_unit_id: 2, full_name: "Иванов Иван", cells: {
    general: { ...cell("Согласовано", "Подтверждено"), status_code: "ACCEPTED" },
    education: cell("Не начато", "Нет результата"), training: cell("Ошибка", "Нужна проверка"),
    relatives: cell("Не начато", "Обработка раздела ещё не подключена"), military: cell("Не применимо", "Раздел не применяется"),
    employment_biography: cell("Не начато", "Обработка раздела ещё не подключена"), employment_history: cell("Не начато", "Обработка раздела ещё не подключена"),
    foreign_languages: cell("Не начато", "Обработка раздела ещё не подключена"), additional: cell("Не начато", "Обработка раздела ещё не подключена"), awards: cell("Не начато", "Обработка раздела ещё не подключена"), academic_degrees_titles: cell("Не начато", "Обработка раздела ещё не подключена"),
  } }],
};

describe("MigrationStatusMatrixPageClient", () => {
  beforeEach(() => { search = new URLSearchParams("universe_id=7&page=2&q=иванов"); listMock.mockReset(); matrixMock.mockReset(); rebuildMock.mockReset(); replaceMock.mockReset(); listMock.mockResolvedValue({ items: [universe] }); matrixMock.mockResolvedValue(report); rebuildMock.mockResolvedValue({ universe_id: 7, projection_rows: 20 }); });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("renders the separate language and additional-information columns in a horizontally scrolling table", async () => {
    render(<MigrationStatusMatrixPageClient />);
    expect(await screen.findByRole("heading", { name: "Сводка личных карточек" })).toBeInTheDocument();
    expect(screen.queryByText("Общие сведения: первый прогон")).not.toBeInTheDocument();
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

  it("shows the persisted first-pass general-information counters", async () => {
    render(<MigrationStatusMatrixPageClient />);
    const summary = await screen.findByTestId("migration-status-general-summary");
    expect(summary).toHaveTextContent("Всего сотрудников: 593");
    expect(summary).toHaveTextContent("Общие сведения обработаны: 546");
    expect(summary).toHaveTextContent("Требуется проверка ФИО: 47");
    expect(summary).toHaveTextContent("Обновлено текущим прогоном: 0");
    expect(summary).toHaveTextContent("Пропущено как уже заполненное: 546");
  });

  it("keeps filters before both aggregate blocks", async () => {
    render(<MigrationStatusMatrixPageClient />);
    const page = await screen.findByTestId("migration-status-page");
    const group = screen.getByLabelText("Группа отделений");
    const compact = await screen.findByTestId("migration-status-general-summary");
    const aggregate = screen.getByTestId("migration-status-summary");
    expect(page.compareDocumentPosition(group) & Node.DOCUMENT_POSITION_CONTAINED_BY).toBeTruthy();
    expect(group.compareDocumentPosition(compact) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(compact.compareDocumentPosition(aggregate) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("renders the server-side status summary independently of the page-sized detail rows", async () => {
    render(<MigrationStatusMatrixPageClient />);
    const summary = await screen.findByTestId("migration-status-summary-table");
    expect(screen.getByRole("heading", { name: "Сводка по статусам личных карточек" })).toBeInTheDocument();
    expect(summary).toHaveTextContent("Трудовая биография");
    expect(summary).toHaveTextContent("Трудовая деятельность");
    expect(summary).toHaveTextContent("Готово к согласованию / обработано автоматически");
    expect(summary).toHaveTextContent("Нет данных или не обработано");
  });

  it("adds an explicit total-card row that sums every displayed user status for each section", async () => {
    render(<MigrationStatusMatrixPageClient />);

    const total = await screen.findByTestId("migration-status-summary-total");
    expect(within(total).getByRole("rowheader", { name: "Итого карточек" })).toBeInTheDocument();
    expect(Array.from(total.querySelectorAll("td")).map((cell) => cell.textContent)).toEqual(["2", "2", "2"]);
    expect(total.className).toContain("font-semibold");
    expect(total.className).toContain("border-t-2");
  });

  it("recalculates total-card counts from the server-filtered report", async () => {
    search = new URLSearchParams("universe_id=7&org_unit_id=114");
    matrixMock.mockResolvedValue({
      ...report,
      total: 1,
      general_summary: { ...report.general_summary, total_active_employees: 1, processed: 1, review_required: 0 },
      status_summary: {
        ...report.status_summary,
        counts: report.status_summary.counts.map((item) => ({
          ...item,
          count: (item.section_code === "general" && item.status_code === "AUTO_READY")
            || (item.section_code !== "general" && item.status_code === "NO_SOURCE_DATA")
            ? 1
            : 0,
        })),
      },
    });

    render(<MigrationStatusMatrixPageClient />);

    const total = await screen.findByTestId("migration-status-summary-total");
    expect(Array.from(total.querySelectorAll("td")).map((cell) => cell.textContent)).toEqual(["1", "1", "1"]);
    await waitFor(() => expect(matrixMock).toHaveBeenCalledWith(expect.objectContaining({ org_unit_id: 114 })));
  });

  it("wraps long section headings without truncating them and keeps the summary horizontally scrollable", async () => {
    render(<MigrationStatusMatrixPageClient />);

    const summary = await screen.findByTestId("migration-status-summary-table");
    const longHeading = within(summary).getByRole("columnheader", { name: "Трудовая деятельность" });
    expect(longHeading).toHaveClass("whitespace-normal", "break-words", "min-w-28");
    expect(longHeading).toHaveTextContent("Трудовая деятельность");
    expect(screen.getByTestId("migration-status-summary-scroll")).toHaveClass("overflow-x-auto");
  });

  it("uses existing personal-card anchors and preserves the universe and full report return URL", async () => {
    render(<MigrationStatusMatrixPageClient />);
    const table = await screen.findByTestId("migration-status-matrix");
    const hrefFor = (label: string) => Array.from(table.querySelectorAll("a")).find((link) => link.getAttribute("aria-label")?.startsWith(label))?.getAttribute("href") ?? "";
    expect(hrefFor("Родственники")).toContain("section=family&migration_universe_id=7&return_to=");
    expect(hrefFor("Воинский учёт")).toContain("section=military&migration_universe_id=7&return_to=");
    expect(hrefFor("Трудовая деятельность / послужной список")).toContain("section=assignment&migration_universe_id=7&return_to=");
    expect(hrefFor("Знание иностранных языков")).toContain("section=languages&migration_universe_id=7&return_to=");
    expect(hrefFor("Награды")).toContain("section=additional&migration_universe_id=7&return_to=");
    expect(hrefFor("Учёные степени и звания")).toContain("section=additional&migration_universe_id=7&return_to=");
  });

  it("keeps a visible horizontal scrollbar control before pagination when the table overflows", async () => {
    vi.spyOn(HTMLElement.prototype, "scrollWidth", "get").mockReturnValue(3145);
    vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(1359);
    render(<MigrationStatusMatrixPageClient />);
    expect(await screen.findByTestId("migration-status-scrollbar-control")).toHaveAttribute("max", "1786");
  });

  it("keeps filters and rebuilds the selected persisted universe on refresh", async () => {
    render(<MigrationStatusMatrixPageClient />); await screen.findByTestId("migration-status-matrix");
    expect(screen.getByLabelText("Раздел")).toHaveTextContent("Учёные степени и звания");
    fireEvent.change(screen.getByLabelText("Статус"), { target: { value: "ACCEPTED" } });
    expect(replaceMock).toHaveBeenCalledWith("/directory/personnel/migration-status?universe_id=7&q=%D0%B8%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2&status=ACCEPTED");
    const before = listMock.mock.calls.length; fireEvent.click(screen.getByTestId("migration-status-refresh")); await waitFor(() => expect(rebuildMock).toHaveBeenCalledWith(7)); await waitFor(() => expect(listMock.mock.calls.length).toBeGreaterThan(before));
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
