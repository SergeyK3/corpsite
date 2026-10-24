import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ComponentType } from "react";

const state = vi.hoisted(() => ({
  params: new URLSearchParams(), path: "", reads: [] as { source: string; query: Record<string, any> }[],
  rows: [] as any[], denied: false,
  positions: [] as any[], experts: [] as any[],
  router: { replace: vi.fn(), push: vi.fn() },
  download: vi.fn(),
  me: { user_id: 25, role_id: 2, role_code: "ADMIN", can_view_all_tasks: true, is_privileged: true, has_operational_orders_read: true },
}));

function page(source: string, query: Record<string, any> = {}) {
  state.reads.push({ source, query });
  if (state.denied) return Promise.reject(new Error("Доступ запрещён"));
  const offset = query.offset ?? 0;
  const limit = query.limit ?? 50;
  return Promise.resolve({ items: state.rows.slice(offset, offset + limit), total: state.rows.length, limit, offset });
}

vi.mock("next/navigation", () => ({ useRouter: () => state.router, useSearchParams: () => state.params, usePathname: () => state.path }));
vi.mock("@/lib/currentUser", () => ({ useCurrentUser: () => state.me }));
vi.mock("@/lib/auth", async (original) => ({ ...await original<object>(), isAuthed: () => true }));
vi.mock("@/components/TaskOrgFiltersBar", () => ({ default: () => null }));
vi.mock("@/components/OrgScopeFilter", () => ({ default: () => null }));
vi.mock("@/components/OrgUnitScopeFilter", () => ({ default: () => null }));
vi.mock("@/lib/tableExport", async (original) => ({ ...await original<object>(), downloadTableExcel: state.download }));
vi.mock("@/lib/api", async (original) => ({
  ...await original<object>(), apiAuthMe: async () => state.me,
  apiFetchJson: async (path: string, options?: { query?: Record<string, any> }) => {
    if (path === "/periods/current") return { period_id: 1 };
    if (path === "/tasks/manual/available-roles") return { items: [] };
    if (path === "/directory/positions" || path === "/directory/working-contacts") {
      const rows = path.endsWith("positions") ? state.positions : state.experts;
      const { offset = 0, limit = 50 } = options?.query ?? {};
      return { items: rows.slice(offset, offset + limit), total: rows.length };
    }
    const url = new URL(path, "http://localhost");
    const query = options?.query ?? Object.fromEntries(url.searchParams);
    return page(url.pathname, query);
  },
}));
vi.mock("@/app/admin/system/org-units/_lib/adminOrgUnitsApi.client", async (original) => ({ ...await original<object>(), fetchAdminOrgUnits: (args: any) => page("org-units", args) }));
vi.mock("@/lib/orgScope", async (original) => ({ ...await original<object>(), fetchDepartmentGroups: async () => [{ group_id: 2, group_name: "Группа" }] }));
vi.mock("@/app/directory/personnel/_lib/personnelJournalApi.client", async (original) => ({
  ...await original<object>(), listPersonnelEvents: (args: any) => page("journal", args), listHREventRegistry: async () => ({ items: [] }),
}));
vi.mock("@/app/directory/personnel/_lib/personnelLkApi.client", async (original) => ({ ...await original<object>(), listPersonnelLkRegistry: (args: any) => page("lk", args) }));
vi.mock("@/app/directory/employees/_lib/api.client", async (original) => ({ ...await original<object>(), getEmployee: async () => ({ id: "7", fio: "Иванов" }), getEmployees: async () => ({ items: [], total: 0 }) }));
vi.mock("@/app/directory/personnel/_lib/personnelOrdersApi.client", async (original) => ({ ...await original<object>(), listPersonnelOrders: (args: any) => page("orders", args) }));
vi.mock("@/app/directory/incoming-information/_lib/api.client", async (original) => ({ ...await original<object>(), listIncomingDocuments: (args: any) => page("incoming", args) }));
vi.mock("@/app/directory/operational-orders/_lib/api", async (original) => ({
  ...await original<object>(), listWorkspaces: (args: any) => page("workspaces", args), listDocuments: (args: any) => page("documents", args),
  listArchiveReview: async (args: any) => ({ ...await page("archive", args), sections: ["Раздел"], batch: { batch_id: 1 }, stats: { initial_quality: { total: 231, preconfirmed: 231, incomplete: 0 }, work_queue: { pending_review: 231, needs_clarification: 0, completed_review: 0 }, duplicate_sha_excel_rows: [], repeated_298_excel_rows: [] } }),
}));
vi.mock("@/app/directory/personnel/_components/PersonnelApplicationRegisterDrawer", () => ({ default: () => null }));
vi.mock("@/app/directory/personnel/_components/PersonnelApplicationDetailDrawer", () => ({ default: () => null }));
vi.mock("@/app/directory/personnel/_components/PersonnelOrderCreateDialog", () => ({ default: () => null }));
vi.mock("@/app/directory/personnel/_components/PersonnelOrderDetailDrawer", () => ({ default: () => null }));
vi.mock("@/app/tasks/_components/TaskDrawer", () => ({ default: () => null }));
vi.mock("@/app/tasks/_components/CreateManualTaskModal", () => ({ default: () => null }));

import OrgUnits from "@/app/admin/system/org-units/_components/OrgUnitsAdminClient";
import Tasks from "@/app/tasks/_components/TasksPageClient";
import Roles from "@/app/directory/roles/_components/RolesPageClient";
import Contacts from "@/app/directory/contacts/page";
import Journal from "@/app/directory/personnel/_components/PersonnelJournalPageClient";
import Lk from "@/app/directory/personnel/_components/PersonnelLkPageClient";
import Orders from "@/app/directory/personnel/_components/PersonnelOrdersPageClient";
import Operational from "@/app/directory/operational-orders/_components/OperationalOrdersPageClient";
import Incoming from "@/app/directory/incoming-information/_components/IncomingInformationPageClient";
import ArchiveReviewPanel from "@/app/directory/operational-orders/_components/ArchiveReviewPanel";

const cases: { name: string; Component: ComponentType; source: string; query: string; filtered: string; expected?: Record<string, any>; prepare?: () => Promise<void> }[] = [
  { name: "/admin/system/org-units", Component: OrgUnits, source: "org-units", query: "", filtered: "", expected: { q: "Иванов", status: "all", roots_only: true, without_employees: true, deletable_only: true }, prepare: async () => {
    fireEvent.change(screen.getByTestId("org-units-filter-search"), { target: { value: "Иванов" } });
    fireEvent.change(screen.getByTestId("org-units-filter-status"), { target: { value: "all" } });
    fireEvent.click(screen.getByLabelText("Только корневые"));
    fireEvent.click(screen.getByLabelText("Без сотрудников"));
    fireEvent.click(screen.getByTestId("org-units-filter-deletable"));
    await waitFor(() => expect(state.reads.at(-1)?.query.q).toBe("Иванов"));
  } },
  { name: "/tasks", Component: Tasks, source: "/tasks", query: "", filtered: "org_group_id=2&org_unit_id=3&position_id=4", expected: { search: "Иванов", org_group_id: 2, org_unit_id: "3", position_id: 4, task_kind: "regular" }, prepare: async () => {
    fireEvent.change(screen.getByPlaceholderText(/Поиск по задаче/), { target: { value: "Иванов" } });
    const select = screen.getAllByRole("combobox").find((node) => node.querySelector('option[value="regular"]'))!;
    fireEvent.change(select, { target: { value: "regular" } });
    await waitFor(() => expect(state.reads.at(-1)?.query.search).toBe("Иванов"));
  } },
  { name: "/directory/roles", Component: Roles, source: "/directory/roles", query: "", filtered: "q=Иванов&is_active=true&org_group_id=2&org_unit_id=3", expected: { q: "Иванов", is_active: true, org_group_id: 2, org_unit_id: 3 } },
  { name: "/directory/contacts", Component: Contacts, source: "/directory/contacts", query: "", filtered: "org_group_id=2&org_unit_id=3", expected: { q: "Иванов", org_group_id: 2, org_unit_id: 3 }, prepare: async () => {
    const input = screen.getByPlaceholderText(/Поиск по ID/);
    fireEvent.change(input, { target: { value: "Иванов" } });
    fireEvent.submit(input.closest("form")!);
  } },
  { name: "/directory/personnel/journal", Component: Journal, source: "journal", query: "", filtered: "q=Иванов&event_category=LEAVE&leave_kind=ANNUAL&leave_operation=GRANT&date_from=2026-01-01&date_to=2026-12-31&org_group_id=2&org_unit_id=3&position_id=4", expected: { event_category: "LEAVE", leave_kind: "ANNUAL", leave_operation: "GRANT", date_from: "2026-01-01", date_to: "2026-12-31", org_group_id: 2, org_unit_id: 3, position_id: 4 } },
  { name: "/directory/personnel/lk", Component: Lk, source: "lk", query: "offset=50", filtered: "q=Иванов&record_kind=employee&status=all&application_status=registered&org_group_id=2&org_unit_id=3&position_id=4&offset=50", expected: { q: "Иванов", record_kind: "employee", status: "all", application_status: "registered", org_group_id: 2, org_unit_id: 3, position_id: 4 } },
  { name: "/directory/personnel/orders", Component: Orders, source: "orders", query: "", filtered: "q=Иванов&status=DRAFT&employee_id=7&order_type_code=HIRE&org_unit_id=3&date_from=2026-01-01&date_to=2026-12-31&include_closed=true&record_quality=ALL", expected: { q: "Иванов", status: "DRAFT", employee_id: 7, order_type_code: "HIRE", org_unit_id: 3, include_closed: true, date_from: "2026-01-01", date_to: "2026-12-31" } },
  { name: "/directory/operational-orders", Component: Operational, source: "workspaces", query: "", filtered: "stage=SUBMITTED&scope=mine&promoted=no&lang=both&org_unit_id=3", expected: { stage: "SUBMITTED", record_creator_user_id: 25, promoted: false, submitting_org_unit_id: 3 } },
  // This page currently exposes pagination only: there are no search/filter controls.
  { name: "/directory/incoming-information", Component: Incoming, source: "incoming", query: "offset=25", filtered: "offset=50" },
  { name: "/directory/operational-orders documents", Component: Operational, source: "documents", query: "tab=documents", filtered: "tab=documents&doc_status=CREATED&org_unit_id=3", expected: { status: "CREATED", submitting_org_unit_id: 3 } },
  { name: "/directory/operational-orders archive-review", Component: () => <ArchiveReviewPanel canReview={false} />, source: "archive", query: "", filtered: "", expected: { search: "Иванов", only_duplicate_sha: true, only_order_298: true }, prepare: async () => {
    fireEvent.change(screen.getByPlaceholderText("Имя, номер, предмет или путь"), { target: { value: "Иванов" } });
    fireEvent.click(screen.getByLabelText("Дубликат файла"));
    fireEvent.click(screen.getByLabelText("Номер 298-ө"));
  } },
];

beforeEach(() => {
  state.params = new URLSearchParams();
  state.reads = [];
  state.positions = []; state.experts = [];
  state.denied = false;
  state.router.replace.mockReset(); state.router.push.mockReset(); state.download.mockReset();
  state.download.mockImplementation(async (table) => { if (!table.rows.length) throw new Error("Нет записей для выгрузки по текущим фильтрам."); });
  state.rows = Array.from({ length: 231 }, (_, i) => ({
    id: i + 1, unit_id: i + 1, name: `Иванов ${i}`, code: "U", group_id: 2, parent_unit_id: 10, is_active: true, child_count: 0,
    task_id: i + 1, title: `Иванов ${i}`, task_kind: "regular", status_code: "IN_PROGRESS",
    role_id: i + 1, role_code: `R${i}`, role_name: `Иванов ${i}`,
    contact_id: i + 1, full_name: `Иванов ${i}`, phone: "123",
    event_id: i + 1, employee_id: i + 1, employee_name: `Иванов ${i}`, event_type: "HIRE", effective_date: "2026-01-02",
    person_id: i + 1, fio: `Иванов ${i}`, iin: "001234567890", record_kind: "employee", rate: 1, status: "DRAFT",
    order_id: i + 1, order_number: String(i + 1), order_date: "2026-01-02", order_type_code: "HIRE", employee_names: [`Иванов ${i}`], item_count: 1, storage_json: {},
    document_id: i + 1, workspace_id: i + 1, proposed_title: `Иванов ${i}`, submitting_org_unit_id: 3, content_author_reference: "Автор", record_creator_user_id: 25, drafting_path: "SUBMITTED_TEXT", stage: "SUBMITTED", ru_present: true, kk_present: true, version: 1,
    incoming_document_id: i + 1, registration_number: `ВХ-${i}`, registered_at: "2026-01-02", document_type_label: "Письмо", sender_display: "Отправитель", summary: `Иванов ${i}`, primary_executor_display: "Исполнитель", due_date: null, status_label: "В работе",
    row_id: i + 1, excel_row: i + 1, archive_section: "Раздел", file_name: `Иванов ${i}.docx`, initial_review_state: "REQUISITES_PRECONFIRMED", source_status: "Найден", review_outcome: null,
  }));
});

it.each([
  { name: "journal", Component: Journal, query: "q=Иванов", change: (row: any, i: number) => ({ ...row, employee_name: i < 230 ? "Петров" : "Иванов" }) },
  { name: "orders", Component: Orders, query: "q=Иванов", change: (row: any, i: number) => ({ ...row, employee_names: [i < 230 ? "Петров" : "Иванов"] }) },
  { name: "workspaces", Component: Operational, query: "lang=both", change: (row: any, i: number) => ({ ...row, kk_present: i === 230 }) },
])("applies $name browser filtering to rows beyond the visible result", async ({ Component, query, change }) => {
  state.params = new URLSearchParams(query);
  state.rows = state.rows.map(change);
  render(<Component />);
  const button = await screen.findByRole("button", { name: "Выгрузить в Excel" });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  await waitFor(() => expect(state.download).toHaveBeenCalledTimes(1));
  expect(state.download.mock.calls[0][0].rows).toHaveLength(1);
});

it("exports the other task kind after collecting every page", async () => {
  state.rows = state.rows.map((row, i) => ({ ...row, task_kind: i === 230 ? "other" : "regular" }));
  render(<Tasks />);
  const button = await screen.findByRole("button", { name: "Выгрузить в Excel" });
  await waitFor(() => expect(button).toBeEnabled());
  const select = screen.getAllByRole("combobox").find((node) => node.querySelector('option[value="other"]'))!;
  fireEvent.change(select, { target: { value: "other" } });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  await waitFor(() => expect(state.download).toHaveBeenCalledTimes(1));
  expect(state.download.mock.calls[0][0].rows).toHaveLength(1);
});

it("builds contact slots and experts once using all contact pages", async () => {
  state.positions = [{ position_id: 1, name: "Иванов 230" }, { position_id: 2, name: "Свободный слот" }];
  state.experts = [{ user_id: 500, person_id: 231, full_name: "Иванов 230", role_name: "Эксперт" }, { user_id: 501, full_name: "Эксперт Петров", role_name: "Эксперт" }];
  render(<Contacts />);
  const button = await screen.findByRole("button", { name: "Выгрузить в Excel" });
  await waitFor(() => expect(button).toBeEnabled()); fireEvent.click(button);
  await waitFor(() => expect(state.download).toHaveBeenCalledTimes(1));
  const rows = state.download.mock.calls[0][0].rows;
  expect(rows).toHaveLength(233);
  expect(rows.filter((row: any[]) => row[0] === "слот")).toHaveLength(1);
  expect(rows.filter((row: any[]) => row[0] === "эксперт")).toHaveLength(1);
});
afterEach(cleanup);

describe.each(cases)("$name Excel", (testCase) => {
  it.each([false, true])("exports every page with applied filters=%s without navigation or mutations", async (filtered) => {
    state.path = testCase.name;
    state.params = new URLSearchParams(filtered ? testCase.filtered : testCase.query);
    const { Component } = testCase;
    render(<Component />);
    const button = await screen.findByRole("button", { name: "Выгрузить в Excel" });
    await waitFor(() => expect(button).toBeEnabled());
    if (filtered) await testCase.prepare?.();
    await waitFor(() => expect(button).toBeEnabled());
    const beforeUrl = state.params.toString();
    state.router.replace.mockClear(); state.router.push.mockClear(); state.reads = [];
    fireEvent.click(button);
    await waitFor(() => expect(state.download).toHaveBeenCalledTimes(1));
    const table = state.download.mock.calls[0][0];
    expect(table.rows).toHaveLength(231);
    expect(table.headers.length).toBeGreaterThan(3);
    expect(table.rows.every((row: unknown[]) => row.length === table.headers.length)).toBe(true);
    const visibleHeaders = screen.getAllByRole("columnheader").map((node) => node.textContent?.trim()).filter((label) => label && label !== "Действие" && label !== "Действия");
    expect(table.headers).toEqual(visibleHeaders);
    const reads = state.reads.filter((read) => read.source === testCase.source);
    expect(Number(reads[0].query.offset)).toBe(0);
    expect(reads.some((read) => Number(read.query.offset) >= 200)).toBe(true);
    if (filtered && testCase.expected) for (const read of reads) expect(read.query).toMatchObject(testCase.expected);
    expect(state.params.toString()).toBe(beforeUrl);
    expect(state.router.replace).not.toHaveBeenCalled(); expect(state.router.push).not.toHaveBeenCalled();
  });

  it("handles an empty result", async () => {
    state.path = testCase.name; state.params = new URLSearchParams(testCase.query); state.rows = [];
    const { Component } = testCase; render(<Component />);
    const button = await screen.findByRole("button", { name: "Выгрузить в Excel" });
    await waitFor(() => expect(button).toBeEnabled()); fireEvent.click(button);
    expect(await screen.findByRole("status")).toHaveTextContent("Нет записей для выгрузки");
  });

  it("does not offer a usable export when table access fails", async () => {
    state.denied = true; state.path = testCase.name; state.params = new URLSearchParams(testCase.query);
    const { Component } = testCase; render(<Component />);
    await waitFor(() => expect(state.reads.some((read) => read.source === testCase.source)).toBe(true));
    await waitFor(() => {
      const button = screen.queryByRole("button", { name: "Выгрузить в Excel" });
      if (button) expect(button).toBeDisabled();
    });
    expect(state.download).not.toHaveBeenCalled();
  });
});
