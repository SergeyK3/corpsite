import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelOrdersPageClient from "./PersonnelOrdersPageClient";

const navigation = vi.hoisted(() => ({
  params: "",
  replace: vi.fn(),
}));
const api = vi.hoisted(() => ({
  getEmployees: vi.fn(),
  getEmployee: vi.fn(),
  listPersonnelOrders: vi.fn(),
  deletePersonnelOrderAsHrHead: vi.fn(),
}));
const currentUser = vi.hoisted(() => ({ value: null as { role_code?: string } | null }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: navigation.replace }),
  useSearchParams: () => new URLSearchParams(navigation.params),
}));

vi.mock("@/components/TaskOrgFiltersBar", () => ({ default: () => null }));
vi.mock("@/lib/currentUser", () => ({ useCurrentUser: () => currentUser.value }));
vi.mock("@/app/directory/employees/_lib/api.client", () => ({ getEmployees: api.getEmployees, getEmployee: api.getEmployee }));
vi.mock("./PersonnelOrderCreateDialog", () => ({
  default: ({ onCreated }: { onCreated: (detail: { order_id: number; order_number: string }) => void }) => (
    <button type="button" data-testid="simulate-draft-created" onClick={() => onCreated({ order_id: 77, order_number: "ТЕСТ-77" })}>Создать тестовый черновик</button>
  ),
}));
vi.mock("./PersonnelOrderDetailDrawer", () => ({
  default: ({ onClose, open, orderId }: { onClose: () => void; open: boolean; orderId: number | null }) => open ? <div data-testid="personnel-order-drawer">Черновик {orderId}<button type="button" onClick={onClose}>Закрыть карточку</button></div> : null,
}));

vi.mock("../_lib/personnelOrdersApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelOrdersApi.client")>(
    "../_lib/personnelOrdersApi.client",
  );
  return { ...actual, listPersonnelOrders: api.listPersonnelOrders, deletePersonnelOrderAsHrHead: api.deletePersonnelOrderAsHrHead };
});

afterEach(() => {
  cleanup();
  navigation.params = "";
  navigation.replace.mockReset();
  api.getEmployees.mockReset();
  api.getEmployee.mockReset();
  api.listPersonnelOrders.mockReset();
  api.deletePersonnelOrderAsHrHead.mockReset();
  currentUser.value = null;
});

describe("PersonnelOrdersPageClient employee filter", () => {
  it("applies completed date boundaries while keeping other filters and resetting only the page", async () => {
    navigation.params = "status=DRAFT&order_type_code=HIRE&record_quality=WORKING&date_to=2020-01-31&offset=200";
    api.listPersonnelOrders.mockResolvedValue({items: [], total: 714, limit: 200, offset: 200});
    render(<PersonnelOrdersPageClient />);
    await waitFor(() => expect(api.listPersonnelOrders).toHaveBeenCalled());
    const input = screen.getByLabelText("Дата с"); input.focus();
    let value = "";
    for (const character of "05.01.2020") {
      value += character;
      fireEvent.change(input, {target: {value}});
      if (value.length < 10) expect(navigation.replace).not.toHaveBeenCalled();
    }
    const params = new URL(navigation.replace.mock.calls.at(-1)![0], "http://localhost").searchParams;
    expect(Object.fromEntries(params)).toEqual({status: "DRAFT", order_type_code: "HIRE", date_from: "2020-01-05", date_to: "2020-01-31", record_quality: "WORKING"});
    expect(input).toHaveFocus();
    fireEvent.click(screen.getByRole("button", {name: "Очистить: Дата по"}));
    const cleared = new URL(navigation.replace.mock.calls.at(-1)![0], "http://localhost").searchParams;
    expect(cleared.has("date_to")).toBe(false);
    expect(cleared.get("status")).toBe("DRAFT");
    expect(cleared.get("order_type_code")).toBe("HIRE");
  });
  it("preserves the space while typing 2, Space, then тест through URL updates", async () => {
    navigation.params = "record_quality=WORKING&offset=600";
    api.listPersonnelOrders.mockResolvedValue({items: [], total: 714, limit: 200, offset: 0});
    const view = render(<PersonnelOrdersPageClient />);
    await waitFor(() => expect(api.listPersonnelOrders).toHaveBeenCalled());
    const input = screen.getByPlaceholderText("№ приказа, название, ФИО");
    let expected = "";
    for (const character of ["2", " ", "т", "е", "с", "т"]) {
      fireEvent.change(input, {target: {value: (input as HTMLInputElement).value + character}});
      expected += character;
      navigation.params = new URL(navigation.replace.mock.calls.at(-1)![0], "http://localhost").search.slice(1);
      view.rerender(<PersonnelOrdersPageClient />);
      expect(input).toHaveValue(expected);
    }
    expect(navigation.replace).toHaveBeenLastCalledWith("/directory/personnel/orders?q=2+%D1%82%D0%B5%D1%81%D1%82&record_quality=WORKING");
  });

  it("keeps the current typed query when an older URL update arrives", async () => {
    api.listPersonnelOrders.mockResolvedValue({items: [], total: 714, limit: 200, offset: 0});
    const view = render(<PersonnelOrdersPageClient />);
    const input = screen.getByPlaceholderText("№ приказа, название, ФИО");
    for (const character of ["2", " ", "т", "е", "с", "т"]) {
      fireEvent.change(input, {target: {value: (input as HTMLInputElement).value + character}});
    }
    navigation.params = "q=2&record_quality=WORKING";
    view.rerender(<PersonnelOrdersPageClient />);
    expect(input).toHaveValue("2 тест");
    navigation.params = "q=2+%D1%82%D0%B5%D1%81%D1%82&record_quality=WORKING";
    view.rerender(<PersonnelOrdersPageClient />);
    expect(input).toHaveValue("2 тест");
    navigation.params = "q=another&record_quality=WORKING";
    view.rerender(<PersonnelOrdersPageClient />);
    expect(input).toHaveValue("another");
  });

  it("offers navigation beyond the first 200 journal records and preserves filters", async () => {
    navigation.params = "status=DRAFT&record_quality=WORKING";
    api.listPersonnelOrders.mockResolvedValue({items: Array.from({length: 200}, (_, i) => ({order_id: i + 1, order_number: String(i + 1), order_type_code: "HIRE", status: "DRAFT", item_count: 1, employee_ids: [], employee_names: [], storage_json: {}})), total: 714, limit: 200, offset: 0});
    render(<PersonnelOrdersPageClient />);
    await screen.findByText("Показано 1–200 из 714 приказов");
    fireEvent.click(screen.getByRole("button", {name: "Следующая страница"}));
    expect(navigation.replace).toHaveBeenLastCalledWith("/directory/personnel/orders?status=DRAFT&record_quality=WORKING&offset=200");
    fireEvent.click(screen.getByRole("button", {name: "Последняя страница"}));
    expect(navigation.replace).toHaveBeenLastCalledWith("/directory/personnel/orders?status=DRAFT&record_quality=WORKING&offset=600");
  });

  it("loads the saved page offset so an older composite order is reachable", async () => {
    navigation.params = "record_quality=WORKING&offset=600";
    api.listPersonnelOrders.mockResolvedValue({items: [{order_id: 5647, order_number: "2 тест", order_date: "2026-01-05", order_type_code: "COMPOSITE", status: "DRAFT", item_count: 2, employee_ids: [], employee_names: [], storage_json: {}}], total: 714, limit: 200, offset: 600});
    render(<PersonnelOrdersPageClient />);
    expect(await screen.findByTestId("personnel-order-row-5647")).toBeInTheDocument();
    expect(api.listPersonnelOrders).toHaveBeenCalledWith(expect.objectContaining({offset: 600, limit: 200}));
    expect(screen.getByText("Страница 4 из 4")).toBeInTheDocument();
  });

  it("resets the page when changing journal search filters", async () => {
    navigation.params = "record_quality=WORKING&offset=600";
    api.listPersonnelOrders.mockResolvedValue({items: [], total: 714, limit: 200, offset: 600});
    render(<PersonnelOrdersPageClient />);
    await waitFor(() => expect(api.listPersonnelOrders).toHaveBeenCalled());
    fireEvent.change(screen.getByPlaceholderText("№ приказа, название, ФИО"), {target: {value: "2 тест"}});
    expect(navigation.replace).toHaveBeenLastCalledWith("/directory/personnel/orders?q=2+%D1%82%D0%B5%D1%81%D1%82&record_quality=WORKING");
  });
  it("keeps the qualification category filter in the URL and accepts an empty result", async () => {
    navigation.params="order_type_code=QUALIFICATION_CATEGORY";
    api.listPersonnelOrders.mockResolvedValue({items:[],total:0,limit:200,offset:0});
    render(<PersonnelOrdersPageClient/>);
    expect(await screen.findByTestId("personnel-orders-empty")).toBeInTheDocument();
    expect(api.listPersonnelOrders).toHaveBeenCalledWith(expect.objectContaining({order_type_code:"QUALIFICATION_CATEGORY"}));
    const option=screen.getAllByRole("option").find(option=>(option as HTMLOptionElement).value==="QUALIFICATION_CATEGORY")!;
    expect(option).toHaveValue("QUALIFICATION_CATEGORY");
    expect(option.parentElement).toHaveValue("QUALIFICATION_CATEGORY");
    expect(screen.queryByText(/Invalid order_type_code/)).not.toBeInTheDocument();
  });
  it('sends the number query to the server so orders beyond the first 200 can be found',async()=>{
    navigation.params='q=1128&record_quality=WORKING';
    api.listPersonnelOrders.mockImplementation(async filters=>({items:filters.q==='1128'?[{order_id:5578,order_number:'1128',order_date:'2026-06-23',order_type_code:'CONCURRENT_DUTY_END',status:'DRAFT',item_count:2,employee_ids:[523,256],employee_names:['Руслан Әсем Нариманқызы','Алдиярова Айзада Ермекбайқызы'],storage_json:{}}]:[],total:filters.q==='1128'?1:693,limit:200,offset:0}));
    render(<PersonnelOrdersPageClient/>);
    expect(await screen.findByTestId('personnel-order-row-5578')).toBeInTheDocument();
    expect(api.listPersonnelOrders).toHaveBeenCalledWith(expect.objectContaining({q:'1128',record_quality:'WORKING',employee_id:undefined,limit:200,offset:0}));
  });
  it("opens a journal order in the drawer without replacing the page URL", async () => {
    api.listPersonnelOrders.mockResolvedValue({
      items: [{ order_id: 5018, order_number: "1192/1", order_date: "2026-07-06", order_type_code: "LEAVE.UNPAID.GRANT", status: "DRAFT", item_count: 1, employee_ids: [383], employee_names: ["Ильясова Ассель Адиловна"], storage_json: {} }],
      total: 1,
      limit: 200,
      offset: 0,
    });
    render(<PersonnelOrdersPageClient />);

    fireEvent.click(await screen.findByTestId("personnel-order-open-5018"));

    expect(screen.getByTestId("personnel-order-drawer")).toHaveTextContent("Черновик 5018");
    expect(navigation.replace).not.toHaveBeenCalled();
  });

  it("shows a success message, refreshes the journal and opens the created draft without changing the URL", async () => {
    api.listPersonnelOrders.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    render(<PersonnelOrdersPageClient />);
    await waitFor(() => expect(api.listPersonnelOrders).toHaveBeenCalled());
    const callsBeforeCreate = api.listPersonnelOrders.mock.calls.length;

    fireEvent.click(screen.getByTestId("simulate-draft-created"));

    expect(await screen.findByText("Черновик приказа создан: № ТЕСТ-77")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-drawer")).toHaveTextContent("Черновик 77");
    await waitFor(() => expect(api.listPersonnelOrders.mock.calls.length).toBeGreaterThan(callsBeforeCreate));
    expect(navigation.replace).not.toHaveBeenCalled();
  });

  it("shows the HR_HEAD all-status delete button in the journal and uses one confirmation", async () => {
    currentUser.value = { role_code: "HR_HEAD" };
    api.listPersonnelOrders.mockResolvedValue({ items: [{ order_id: 9, order_number: "SIGNED-9", order_date: "2026-10-03", order_type_code: "HIRE", status: "SIGNED", item_count: 0, employee_ids: [], employee_names: [], storage_json: {} }], total: 1, limit: 200, offset: 0 });
    api.deletePersonnelOrderAsHrHead.mockResolvedValue({ status: "SOFT_DELETED", order_id: 9 });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<PersonnelOrdersPageClient />);
    fireEvent.click(await screen.findByRole("button", { name: "Удалить" }));
    await waitFor(() => expect(api.deletePersonnelOrderAsHrHead).toHaveBeenCalledWith(9));
  });

  it("returns to an explicit quality-control return_to after a refreshed deep link is closed", async () => {
    navigation.params = "order_id=8&tab=data&return_to=%2Fadmin%2Fsystem%3Fsection%3Dquality-control";
    api.listPersonnelOrders.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });

    render(<PersonnelOrdersPageClient />);
    fireEvent.click(await screen.findByRole("button", { name: "Закрыть карточку" }));

    expect(navigation.replace).toHaveBeenCalledWith("/admin/system?section=quality-control");
  });

  it("keeps employee_id and its hydrated name when closing an order deep link", async () => {
    navigation.params = "employee_id=234&order_id=8&record_quality=WORKING";
    api.listPersonnelOrders.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    api.getEmployee.mockResolvedValue({ id: "234", fio: "Абдирова Роза", org_unit: null, position: null });

    render(<PersonnelOrdersPageClient />);
    await waitFor(() => expect(screen.getByRole("searchbox", { name: "Сотрудник" })).toHaveValue("Абдирова Роза"));
    fireEvent.click(screen.getByRole("button", { name: "Закрыть карточку" }));

    expect(navigation.replace).toHaveBeenCalledWith(
      "/directory/personnel/orders?employee_id=234&record_quality=WORKING",
    );
  });

  it("selects an employee by full name and applies employee_id filter", async () => {
    api.listPersonnelOrders.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    api.getEmployees.mockResolvedValue({
      items: [{
        id: "791",
        fio: "Райник Анастасия Николаевна",
        department: null,
        position: { id: 6, name: "Врач" },
        org_unit: { unit_id: 50, name: "Администрация", code: null, parent_unit_id: null, is_active: true },
        rate: 1,
        status: "active",
        date_from: null,
        date_to: null,
      }],
      total: 1,
    });

    render(<PersonnelOrdersPageClient />);

    fireEvent.change(screen.getByRole("searchbox", { name: "Сотрудник" }), {
      target: { value: "Райник" },
    });

    await waitFor(() => {
      expect(api.getEmployees).toHaveBeenCalledWith({ q: "Райник", limit: 20, status: "all" });
    });
    fireEvent.click(await screen.findByRole("button", { name: /Райник Анастасия Николаевна/ }));

    expect(navigation.replace).toHaveBeenCalledWith(
      "/directory/personnel/orders?employee_id=791&record_quality=WORKING",
    );
  });

  it("hydrates the employee name from employee_id in the URL and clears both values", async () => {
    navigation.params = "employee_id=234&record_quality=WORKING";
    api.listPersonnelOrders.mockResolvedValue({ items: [], total: 0, limit: 200, offset: 0 });
    api.getEmployee.mockResolvedValue({ id: "234", fio: "Абдирова Роза", org_unit: null, position: null });

    render(<PersonnelOrdersPageClient />);

    const input = screen.getByRole("searchbox", { name: "Сотрудник" });
    await waitFor(() => expect(input).toHaveValue("Абдирова Роза"));
    expect(api.getEmployee).toHaveBeenCalledWith("234");
    fireEvent.click(screen.getByRole("button", { name: "Очистить сотрудника" }));
    expect(input).toHaveValue("");
    expect(navigation.replace).toHaveBeenCalledWith("/directory/personnel/orders?record_quality=WORKING");
  });
});
