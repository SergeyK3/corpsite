import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { listHREventRegistryMock, listPersonnelEventsMock, replaceMock, pushMock } = vi.hoisted(() => ({
  listHREventRegistryMock: vi.fn(),
  listPersonnelEventsMock: vi.fn(),
  replaceMock: vi.fn(),
  pushMock: vi.fn(),
}));

let currentSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: pushMock }),
  useSearchParams: () => currentSearchParams,
}));

vi.mock("@/components/TaskOrgFiltersBar", () => ({ default: () => null }));
vi.mock("@/lib/taskOrgFilters", () => ({
  readTaskOrgFiltersFromSearchParams: () => ({}),
}));
vi.mock("../_lib/personnelJournalApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelJournalApi.client")>("../_lib/personnelJournalApi.client");
  return {
    ...actual,
    listHREventRegistry: listHREventRegistryMock,
    listPersonnelEvents: listPersonnelEventsMock,
  };
});

describe("PersonnelJournalPageClient search submit", () => {
  beforeEach(() => {
    currentSearchParams = new URLSearchParams();
    replaceMock.mockReset();
    pushMock.mockReset();
    listHREventRegistryMock.mockReset().mockResolvedValue({ version: "1.1", items: registryItems });
    listPersonnelEventsMock.mockReset().mockResolvedValue({ items: [], total: 0 });
  });

  afterEach(() => cleanup());

  it("repeats the current filtered request when Enter is pressed in an empty employee search", async () => {
    currentSearchParams = new URLSearchParams("event_category=LEAVE&date_from=2026-04-01");
    render(<PersonnelJournalPageClient />);

    await waitFor(() => expect(listPersonnelEventsMock).toHaveBeenCalledTimes(1));
    fireEvent.submit(screen.getByRole("searchbox").closest("form")!);

    await waitFor(() => expect(listPersonnelEventsMock).toHaveBeenCalledTimes(2));
    expect(listPersonnelEventsMock).toHaveBeenLastCalledWith(expect.objectContaining({
      event_category: "LEAVE",
      date_from: "2026-04-01",
      limit: 200,
      offset: 0,
    }));
  });

  it("repeats the request and keeps local employee filtering when Enter is pressed with text", async () => {
    currentSearchParams = new URLSearchParams("q=ivan");
    listPersonnelEventsMock.mockResolvedValue({
      total: 2,
      items: [
        { event_id: 1, employee_id: 2, employee_name: "Ivanov I.I.", event_type: "HIRE", effective_date: "2026-08-24", from_org_unit_id: null, from_org_unit_name: null, to_org_unit_id: null, to_position_id: null, to_position_name: null, from_position_id: null, from_position_name: null, from_rate: null, to_rate: null, order_ref: null, comment: null },
        { event_id: 2, employee_id: 3, employee_name: "Petrov P.P.", event_type: "HIRE", effective_date: "2026-08-24", from_org_unit_id: null, from_org_unit_name: null, to_org_unit_id: null, to_position_id: null, to_position_name: null, from_position_id: null, from_position_name: null, from_rate: null, to_rate: null, order_ref: null, comment: null },
      ],
    });
    render(<PersonnelJournalPageClient />);

    expect(await screen.findByText("Ivanov I.I.")).toBeInTheDocument();
    expect(screen.queryByText("Petrov P.P.")).not.toBeInTheDocument();
    fireEvent.submit(screen.getByRole("searchbox").closest("form")!);

    await waitFor(() => expect(listPersonnelEventsMock).toHaveBeenCalledTimes(2));
    expect(screen.getByText("Ivanov I.I.")).toBeInTheDocument();
    expect(screen.queryByText("Petrov P.P.")).not.toBeInTheDocument();
  });
});

import PersonnelJournalPageClient from "./PersonnelJournalPageClient";

const registryItems = [
  { code: "HIRE", label_ru: "Приём", label_kk: "Жұмысқа қабылдау", category: "EMPLOYMENT", category_label_ru: "Трудовые отношения", category_label_kk: "Еңбек қатынастары", event_class: "EMPLOYMENT", leave_kind: null, operation: null, leave_kind_label_ru: null, leave_kind_label_kk: null, operation_label_ru: null, operation_label_kk: null, automatic_effect: "AUTOMATIC_EFFECT", journal_filterable: true },
  { code: "LEAVE.ANNUAL.GRANT", label_ru: "Ежегодный оплачиваемый отпуск", label_kk: "Жыл сайынғы ақылы демалыс", category: "LEAVE", category_label_ru: "Отпуска", category_label_kk: "Демалыстар", event_class: "EMPLOYMENT", leave_kind: "ANNUAL", operation: "GRANT", leave_kind_label_ru: "Ежегодный оплачиваемый отпуск", leave_kind_label_kk: "Жыл сайынғы ақылы демалыс", operation_label_ru: "Предоставление", operation_label_kk: "Берілетін", automatic_effect: "AUTOMATIC_EFFECT", journal_filterable: true },
  { code: "LEAVE.ANNUAL.RECALL", label_ru: "Отзыв из ежегодного отпуска", label_kk: "Жыл сайынғы демалыстан кері шақыру", category: "LEAVE", category_label_ru: "Отпуска", category_label_kk: "Демалыстар", event_class: "EMPLOYMENT", leave_kind: "ANNUAL", operation: "RECALL", leave_kind_label_ru: "Ежегодный оплачиваемый отпуск", leave_kind_label_kk: "Жыл сайынғы ақылы демалыс", operation_label_ru: "Отзыв", operation_label_kk: "Кері шақыру", automatic_effect: "AUTOMATIC_EFFECT", journal_filterable: true },
  { code: "LEAVE.ANNUAL.POSTPONE", label_ru: "Перенос", label_kk: "", category: "LEAVE", category_label_ru: "Отпуска", category_label_kk: "Демалыстар", event_class: "EMPLOYMENT", leave_kind: "ANNUAL", operation: "POSTPONE", leave_kind_label_ru: "Ежегодный оплачиваемый отпуск", leave_kind_label_kk: "", operation_label_ru: "Перенос", operation_label_kk: "", automatic_effect: "AUTOMATIC_EFFECT", journal_filterable: true },
  { code: "LEAVE.ANNUAL.EXTEND", label_ru: "Продление", label_kk: "", category: "LEAVE", category_label_ru: "Отпуска", category_label_kk: "Демалыстар", event_class: "EMPLOYMENT", leave_kind: "ANNUAL", operation: "EXTEND", leave_kind_label_ru: "Ежегодный оплачиваемый отпуск", leave_kind_label_kk: "", operation_label_ru: "Продление", operation_label_kk: "", automatic_effect: "AUTOMATIC_EFFECT", journal_filterable: true },
  { code: "LEAVE.UNPAID.EARLY_RETURN", label_ru: "Досрочный выход", label_kk: "Мерзімінен бұрын шығу", category: "LEAVE", category_label_ru: "Отпуска", category_label_kk: "Демалыстар", event_class: "EMPLOYMENT", leave_kind: "UNPAID", operation: "EARLY_RETURN", leave_kind_label_ru: "Отпуск без сохранения заработной платы", leave_kind_label_kk: "Жалақы сақталмайтын демалыс", operation_label_ru: "Досрочный выход", operation_label_kk: "Мерзімінен бұрын шығу", automatic_effect: "AUTOMATIC_EFFECT", journal_filterable: true },
];

describe("PersonnelJournalPageClient", () => {
  beforeEach(() => {
    currentSearchParams = new URLSearchParams();
    replaceMock.mockReset();
    pushMock.mockReset();
    listHREventRegistryMock.mockReset().mockResolvedValue({ version: "1.1", items: registryItems });
    listPersonnelEventsMock.mockReset().mockResolvedValue({ items: [], total: 0 });
  });

  afterEach(() => cleanup());

  it("uses registry-driven leave filters and renders an empty leave result", async () => {
    render(<PersonnelJournalPageClient />);
    const category = await screen.findByLabelText("Категория события");
    expect(within(category).getByRole("option", { name: "Отпуска" })).toBeInTheDocument();
    expect(within(screen.getByLabelText("Событие")).getByRole("option", { name: "Приём" })).toBeInTheDocument();
    fireEvent.change(category, { target: { value: "LEAVE" } });

    await waitFor(() => expect(replaceMock).toHaveBeenCalled());
    expect(screen.getByRole("option", { name: "Отпуска" })).toBeInTheDocument();
  });

  it("shows dependent leave controls when Leave is selected", async () => {
    currentSearchParams = new URLSearchParams("event_category=LEAVE&event_type=LEAVE.ANNUAL.GRANT&leave_kind=ANNUAL&leave_operation=GRANT");
    render(<PersonnelJournalPageClient />);

    expect(await screen.findByLabelText("Вид отпуска")).toBeInTheDocument();
    expect(screen.getByLabelText("Операция отпуска")).toBeInTheDocument();
    expect(screen.queryByLabelText("Событие")).not.toBeInTheDocument();
    expect(within(screen.getByLabelText("Вид отпуска")).getByRole("option", { name: "Ежегодный оплачиваемый отпуск" })).toBeInTheDocument();
    expect(within(screen.getByLabelText("Операция отпуска")).getByRole("option", { name: "Предоставление" })).toBeInTheDocument();
    expect(screen.getByText("Кадровые события не найдены")).toBeInTheDocument();
    await waitFor(() => expect(listPersonnelEventsMock).toHaveBeenCalledWith(expect.objectContaining({
      event_category: "LEAVE",
      leave_kind: "ANNUAL",
      leave_operation: "GRANT",
      event_type: undefined,
    })));
  });

  it("keeps all leave kinds and Annual operations available after selections", async () => {
    currentSearchParams = new URLSearchParams("event_category=LEAVE&leave_kind=ANNUAL&leave_operation=GRANT");
    render(<PersonnelJournalPageClient />);

    const leaveKindSelect = await screen.findByLabelText("Вид отпуска");
    const operationSelect = screen.getByLabelText("Операция отпуска");
    expect(Array.from((leaveKindSelect as HTMLSelectElement).options).map((option) => option.value)).toEqual(expect.arrayContaining(["ANNUAL", "UNPAID"]));
    expect(Array.from((operationSelect as HTMLSelectElement).options).map((option) => option.value)).toEqual(expect.arrayContaining(["GRANT", "POSTPONE", "EXTEND", "RECALL"]));
  });

  it("keeps only the event filter for a non-leave category", async () => {
    currentSearchParams = new URLSearchParams("event_category=EMPLOYMENT&event_type=HIRE&leave_kind=ANNUAL&leave_operation=GRANT");
    render(<PersonnelJournalPageClient />);

    expect(await screen.findByLabelText("Событие")).toBeInTheDocument();
    expect(within(screen.getByLabelText("Событие")).getByRole("option", { name: "Приём" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Вид отпуска")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Операция отпуска")).not.toBeInTheDocument();
    await waitFor(() => expect(listPersonnelEventsMock).toHaveBeenCalledWith(expect.objectContaining({
      event_category: "EMPLOYMENT",
      event_type: "HIRE",
      leave_kind: undefined,
      leave_operation: undefined,
    })));
  });

  it("clears incompatible category filters from the URL", async () => {
    currentSearchParams = new URLSearchParams("event_category=EMPLOYMENT&event_type=HIRE&leave_kind=ANNUAL&leave_operation=GRANT");
    render(<PersonnelJournalPageClient />);

    const category = await screen.findByLabelText("Категория события");
    fireEvent.change(category, { target: { value: "LEAVE" } });

    expect(replaceMock).toHaveBeenLastCalledWith("?event_category=LEAVE");

    cleanup();
    replaceMock.mockReset();
    currentSearchParams = new URLSearchParams("event_category=LEAVE&leave_kind=ANNUAL&leave_operation=GRANT");
    render(<PersonnelJournalPageClient />);

    fireEvent.change(await screen.findByLabelText("Категория события"), { target: { value: "EMPLOYMENT" } });
    expect(replaceMock).toHaveBeenLastCalledWith("?event_category=EMPLOYMENT");
  });

  it("shows a registry load error without hiding the journal table", async () => {
    listHREventRegistryMock.mockRejectedValueOnce(new Error("HTTP 403: Forbidden."));
    listPersonnelEventsMock.mockResolvedValueOnce({
      total: 1,
      items: [{ event_id: 1, employee_id: 2, employee_name: "Иванов И.И.", event_type: "HIRE", effective_date: "2026-08-24", from_org_unit_id: null, from_org_unit_name: null, to_org_unit_id: null, to_position_id: null, to_position_name: null, from_position_id: null, from_position_name: null, from_rate: null, to_rate: null, order_ref: null, comment: null }],
    });

    render(<PersonnelJournalPageClient />);

    expect(await screen.findByText("Не удалось загрузить классификатор кадровых событий")).toBeInTheDocument();
    expect(screen.getByText("Иванов И.И.")).toBeInTheDocument();
  });

  it("shows the linked order number as a deep link without displaying its technical ID", async () => {
    listPersonnelEventsMock.mockResolvedValue({
      total: 1,
      items: [{ event_id: 51, employee_id: 7, employee_name: "Aliyev A.A.", event_type: "HIRE", effective_date: "2026-08-24", from_org_unit_id: null, from_org_unit_name: null, to_org_unit_id: null, to_org_unit_name: null, from_position_id: null, from_position_name: null, to_position_id: null, to_position_name: null, from_rate: null, to_rate: null, order_ref: "legacy reference", order_id: 42, order_number: "51-К", comment: null }],
    });

    render(<PersonnelJournalPageClient />);

    const orderLink = await screen.findByRole("link", { name: "51-К" });
    expect(orderLink).toHaveAttribute("href", "/directory/personnel/orders?order_id=42&tab=data");
    expect(screen.queryByText("42")).not.toBeInTheDocument();
    expect(screen.queryByText("legacy reference")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("personnel-journal-row-51"));
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("opens the employee card, not the order, when the employee name is clicked", async () => {
    listPersonnelEventsMock.mockResolvedValue({
      total: 1,
      items: [{ event_id: 52, employee_id: 8, employee_name: "Bayeva B.B.", event_type: "HIRE", effective_date: "2026-08-24", from_org_unit_id: null, from_org_unit_name: null, to_org_unit_id: null, to_position_id: null, to_position_name: null, from_position_id: null, from_position_name: null, from_rate: null, to_rate: null, order_ref: null, order_id: 43, order_number: "52-К", comment: null }],
    });

    render(<PersonnelJournalPageClient />);

    fireEvent.click(await screen.findByTestId("personnel-journal-employee-8"));
    expect(pushMock).toHaveBeenCalledWith("/directory/personnel/employees/8/card?section=history");
    expect(screen.getByRole("link", { name: "52-К" })).toHaveAttribute("href", "/directory/personnel/orders?order_id=43&tab=data");
  });

  it("shows an unprepared import event and keeps the draft order separate", async () => {
    listPersonnelEventsMock.mockResolvedValue({
      total: 2,
      items: [
        { event_id: 7, employee_id: 9, employee_name: "Employee", event_type: "EMPLOYEE_ENROLLED_FROM_IMPORT", event_label: "Added from HR import", effective_date: "2026-09-01", from_org_unit_id: null, from_org_unit_name: null, to_org_unit_id: null, to_org_unit_name: null, from_position_id: null, from_position_name: null, to_position_id: null, to_position_name: null, from_rate: null, to_rate: null, order_ref: null, order_id: null, comment: null },
        { event_id: "draft-order-item-19", is_temporary: true, order_item_id: 19, order_status: "DRAFT", employee_id: 9, employee_name: "Employee", event_type: "LEAVE.CHILDCARE.RETURN", event_label: "Return from childcare leave", lifecycle_status: "PENDING_APPLY", effective_date: "2026-09-02", from_org_unit_id: null, from_org_unit_name: null, to_org_unit_id: null, to_org_unit_name: null, from_position_id: null, from_position_name: null, to_position_id: null, to_position_name: null, from_rate: null, to_rate: null, order_ref: null, order_id: 19, order_number: "19-K", comment: null },
      ],
    });

    render(<PersonnelJournalPageClient />);

    const imported = await screen.findByTestId("personnel-journal-row-7");
    const importOrderLink = within(imported).getByRole("link", { name: "Приказ не подготовлен" });
    expect(importOrderLink).toHaveAttribute("href", "/directory/personnel/orders?employee_id=9");
    expect(importOrderLink.getAttribute("href")).not.toContain("order_id");
    const draft = screen.getByTestId("personnel-journal-row-draft-order-item-19");
    expect(within(draft).getByText("Черновик")).toBeInTheDocument();
    expect(within(draft).getByRole("link", { name: "19-K" })).toHaveAttribute(
      "href", "/directory/personnel/orders?order_id=19&tab=data",
    );
    fireEvent.click(within(draft).getByTestId("personnel-journal-employee-9"));
    expect(pushMock).toHaveBeenCalledWith("/directory/personnel/employees/9/card?section=history");
  });

  it("renders factual order-preparation states for unlinked import events", async () => {
    const importRow = (event_id: number, employee_id: number, import_order_preparation: unknown) => ({
      event_id,
      employee_id,
      employee_name: `Employee ${employee_id}`,
      event_type: "EMPLOYEE_ENROLLED_FROM_IMPORT",
      effective_date: "2026-09-01",
      from_org_unit_id: null,
      from_org_unit_name: null,
      to_org_unit_id: null,
      to_org_unit_name: null,
      from_position_id: null,
      from_position_name: null,
      to_position_id: null,
      to_position_name: null,
      from_rate: null,
      to_rate: null,
      order_ref: null,
      order_id: null,
      order_number: null,
      comment: null,
      import_order_preparation,
    });
    listPersonnelEventsMock.mockResolvedValue({
      total: 4,
      items: [
        importRow(61, 11, { state: "DRAFT", candidate_order_id: 101, candidate_order_number: "101-К" }),
        importRow(62, 12, { state: "PENDING_APPLY", candidate_order_id: 102, candidate_order_number: "1321/1" }),
        importRow(63, 13, { state: "APPLIED", candidate_order_id: 103, candidate_order_number: "Приказ 1321/1" }),
        importRow(64, 14, { state: "AMBIGUOUS" }),
      ],
    });

    render(<PersonnelJournalPageClient />);

    const draft = await screen.findByTestId("personnel-journal-row-61");
    expect(within(draft).getByRole("link", { name: "№ 101-К — требуется регистрация" })).toHaveAttribute(
      "href", "/directory/personnel/orders?order_id=101&tab=data",
    );
    const registered = screen.getByTestId("personnel-journal-row-62");
    expect(within(registered).getByRole("link", { name: "№ 1321/1 — требуется применить" })).toHaveAttribute(
      "href", "/directory/personnel/orders?order_id=102&tab=data",
    );
    const applied = screen.getByTestId("personnel-journal-row-63");
    expect(within(applied).getByRole("link", { name: "Приказ 1321/1 — приказ оформлен" })).toHaveAttribute(
      "href", "/directory/personnel/orders?order_id=103&tab=data",
    );
    expect(screen.queryByRole("link", { name: "№ Приказ 1321/1 — приказ оформлен" })).not.toBeInTheDocument();
    const ambiguous = screen.getByTestId("personnel-journal-row-64");
    expect(within(ambiguous).getByRole("link", { name: "Приказы сотрудника" })).toHaveAttribute(
      "href", "/directory/personnel/orders?employee_id=14",
    );
  });

  it("does not open a guessed order for a journal row without a canonical relation", async () => {
    listPersonnelEventsMock.mockResolvedValue({
      total: 1,
      items: [{ event_id: 53, employee_id: 9, employee_name: "Unlinked employee", event_type: "HIRE", effective_date: "2026-08-24", from_org_unit_id: null, from_org_unit_name: null, to_org_unit_id: null, to_org_unit_name: null, from_position_id: null, from_position_name: null, to_position_id: null, to_position_name: null, from_rate: null, to_rate: null, order_ref: null, order_id: null, comment: null }],
    });

    render(<PersonnelJournalPageClient />);

    fireEvent.click(await screen.findByTestId("personnel-journal-row-53"));
    expect(screen.getByText("Приказ не связан")).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("continues to render existing journal rows", async () => {
    listPersonnelEventsMock.mockResolvedValue({
      total: 1,
      items: [{ event_id: 1, employee_id: 2, employee_name: "Иванов И.И.", event_type: "HIRE", event_label: "Приём", effective_date: "2026-08-24", from_org_unit_id: null, from_org_unit_name: null, to_org_unit_id: null, to_org_unit_name: null, from_position_id: null, from_position_name: null, to_position_id: null, to_position_name: null, from_rate: null, to_rate: null, order_ref: null, comment: null }],
    });
    render(<PersonnelJournalPageClient />);
    expect(await screen.findByText("Иванов И.И.")).toBeInTheDocument();
    expect(screen.getAllByText("Приём").length).toBeGreaterThan(0);
  });
});
