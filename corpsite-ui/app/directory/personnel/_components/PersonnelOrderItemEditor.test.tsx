import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as React from "react";

import { getEmployee, getEmployees } from "@/app/directory/employees/_lib/api.client";
import PersonnelOrderItemEditor from "./PersonnelOrderItemEditor";
import PersonnelOrderEditorialTextEditor from "./PersonnelOrderEditorialTextEditor";
import PersonnelOrderDocumentView from "./PersonnelOrderDocumentView";
import { generatePersonnelOrderEditorial, type PersonnelOrderDetailResponse, type PersonnelOrderEditorialState } from "../_lib/personnelOrdersApi.client";
import { createPersonnelOrderItem, deletePersonnelOrderItem, updatePersonnelOrderItem } from "../_lib/personnelOrdersApi.client";
import { loadScopedPositionOptions, loadGlobalPositionCatalogCached, resetGlobalPositionCatalogCache } from "@/lib/taskOrgFilters";
import { resolveEmployeeOrgScopePrefill } from "@/lib/userCreateOrgScope";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/directory/personnel/orders",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/lib/userCreateOrgScope", () => ({
  resolveEmployeeOrgScopePrefill: vi.fn(async (unitId: number) => ({
    org_group_id: unitId === 73 ? 2 : 1,
    org_unit_id: unitId,
  })),
}));

vi.mock("@/lib/orgScope", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/orgScope")>();
  return {
    ...actual,
    fetchDepartmentGroups: vi.fn(async () => [
      { group_id: 1, group_name: "Группа 1" },
      { group_id: 2, group_name: "Группа 2" },
    ]),
  };
});

vi.mock("@/app/directory/employees/_lib/api.client", () => ({
  getEmployees: vi.fn(async () => ({ items: [], total: 0 })),
  getEmployee: vi.fn(),
}));

vi.mock("@/lib/taskOrgFilters", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/taskOrgFilters")>();
  return {
    ...actual,
    loadScopedPositionOptions: vi.fn(async () => [
      { id: 77, label: "Врач" },
      { id: 78, label: "Заведующий" },
    ]),
    loadGlobalPositionCatalogCached: vi.fn(async () => [
      { id: 77, label: "Врач" },
      { id: 78, label: "Заведующий" },
      { id: 88, label: "Медсестра" },
      { id: 89, label: "Кадровый специалист" },
      { id: 90, label: "Врач" },
    ]),
  };
});

vi.mock("@/components/OrgScopeFilter", () => ({
  default: ({
    value,
    onChange,
    label,
  }: {
    value?: number | null;
    onChange?: (groupId: number | null) => void;
    label?: string;
  }) => (
    <div>
      <label htmlFor={`mock-org-group-${label}`}>{label}</label>
      <select
        id={`mock-org-group-${label}`}
        data-testid={`mock-org-group-${label}`}
        value={value != null ? String(value) : ""}
        onChange={(e) => onChange?.(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">Все</option>
        <option value="1">Группа 1</option>
        <option value="2">Группа 2</option>
      </select>
    </div>
  ),
}));

vi.mock("@/components/OrgUnitScopeFilter", () => ({
  default: ({
    value,
    onChange,
    orgGroupId,
    label,
  }: {
    value?: number | null;
    onChange?: (unitId: number | null) => void;
    orgGroupId?: number | null;
    label?: string;
  }) => (
    <div>
      <label htmlFor={`mock-org-unit-${label}`}>{label}</label>
      <select
        id={`mock-org-unit-${label}`}
        data-testid={`mock-org-unit-${label}`}
        value={value != null ? String(value) : ""}
        onChange={(e) => onChange?.(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">Выберите подразделение</option>
        {orgGroupId === 2 ? (
          <option value="20">Отделение B</option>
        ) : (
          <>
            <option value="10">Отделение A</option>
            <option value="11">Отделение C</option>
          </>
        )}
      </select>
    </div>
  ),
}));

vi.mock("../_lib/personnelOrdersApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/personnelOrdersApi.client")>();
  return {
    ...actual,
    getPersonnelOrderAddItemContext: vi.fn().mockResolvedValue({available: false, reason: "No bound template in legacy edit fixture"}),
    createPersonnelOrderItem: vi.fn(),
    deletePersonnelOrderItem: vi.fn(),
    updatePersonnelOrderItem: vi.fn(),
    generatePersonnelOrderEditorial: vi.fn(),
  };
});

const activeEmployee = {
  id: "138",
  fio: "Макибаева Акмарал Сабитовна",
  department: null,
  position: { id: 86, name: "Руководитель отдела кадров" },
  org_unit: {
    unit_id: 73,
    name: "Отдел кадров",
    code: null,
    parent_unit_id: null,
    is_active: true,
  },
  rate: "1",
  status: "active",
  date_from: null,
  date_to: null,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  resetGlobalPositionCatalogCache();
  vi.mocked(getEmployees).mockResolvedValue({ items: [], total: 0 });
  vi.mocked(getEmployee).mockResolvedValue(activeEmployee);
  vi.mocked(loadScopedPositionOptions).mockResolvedValue([
    { id: 77, label: "Врач" },
    { id: 78, label: "Заведующий" },
  ]);
  vi.mocked(loadGlobalPositionCatalogCached).mockResolvedValue([
    { id: 77, label: "Врач" },
    { id: 78, label: "Заведующий" },
    { id: 88, label: "Медсестра" },
    { id: 89, label: "Кадровый специалист" },
    { id: 90, label: "Врач" },
  ]);
  vi.mocked(createPersonnelOrderItem).mockResolvedValue({
    order: {
      order_id: 1,
      order_type_code: "TRANSFER",
      order_class: "SIMPLE",
      status: "DRAFT",
      source_mode: "PAPER",
      created_by: 1,
    },
    items: [],
    localized_texts: [],
    attachments: [],
    prints: [],
    events: [],
  });
  vi.mocked(updatePersonnelOrderItem).mockResolvedValue({
    order: {
      order_id: 1,
      order_type_code: "HIRE",
      order_class: "SIMPLE",
      status: "DRAFT",
      source_mode: "PAPER",
      created_by: 1,
    },
    items: [],
    localized_texts: [],
    attachments: [],
    prints: [],
    events: [],
  });
  vi.mocked(deletePersonnelOrderItem).mockResolvedValue({
    order: {
      order_id: 1,
      order_type_code: "HIRE",
      order_class: "SIMPLE",
      status: "DRAFT",
      source_mode: "PAPER",
      created_by: 1,
    },
    items: [],
    localized_texts: [],
    attachments: [],
    prints: [],
    events: [],
  });
});

async function selectEmployeeFromSearch() {
  vi.mocked(getEmployees).mockResolvedValue({
    items: [activeEmployee],
    total: 1,
  });
  fireEvent.change(screen.getByTestId("personnel-order-employee-search-input"), {
    target: { value: "Маки" },
  });
  fireEvent.click(await screen.findByTestId("personnel-order-employee-option-138"));
  await waitFor(() => {
    expect(screen.getByTestId("personnel-order-current-placement")).toBeInTheDocument();
  });
}

describe("item save → editorial generation integration", () => {
  function setup() {
    let persisted: PersonnelOrderDetailResponse = {
      order: { order_id: 1, order_type_code: "LEAVE.UNPAID.GRANT", order_class: "SIMPLE", status: "DRAFT", source_mode: "PAPER", created_by: 1 },
      items: [{ item_id: 51, order_id: 1, item_number: 1, item_type_code: "LEAVE.UNPAID.GRANT", item_status: "ACTIVE", employee_id: 138, employee_name: "Test employee", effective_date: "2026-07-01", payload: {
        leave: { period_type: "CONTINUOUS_RANGE", start: "2026-07-01", end: "2026-07-12", days: 12 }, basis: { kind: "PERSONAL_APPLICATION", date: "2026-06-29" }, document_forms_kk: { position_document_possessive_kk: "сестра-хозяйка" },
      } }], localized_texts: [], attachments: [], prints: [], events: [],
    };
    const snapshot = (): PersonnelOrderEditorialState => {
      const position = String((persisted.items[0].payload.document_forms_kk as Record<string, unknown>).position_document_possessive_kk);
      const block = (id: number, type: string, text: string) => ({ block_id: id, scope: "order", locale: "kk", block_type: type, generated_text: text, effective_text: text, editable: true, revision: 1, review_status: "CURRENT" });
      return { order_id: 1, order_status: "DRAFT", editable: true,
        order_blocks: [block(1, "title", "Демалыс туралы"), block(2, "preamble", "БҰЙЫРАМЫН:")],
        items: [{ order_item_id: 51, item_number: 1, item_type_code: "LEAVE.UNPAID.GRANT", basis_required: false, blocks: [{ ...block(3, "body", position), scope: "item", order_item_id: 51 }] }],
      };
    };
    vi.mocked(updatePersonnelOrderItem).mockImplementation(async (_order, _item, body) => {
      persisted = { ...persisted, items: [{ ...persisted.items[0], ...body }] };
      return persisted;
    });
    vi.mocked(generatePersonnelOrderEditorial).mockImplementation(async () => snapshot());
    vi.spyOn(window, "confirm").mockReturnValue(true);
    function Harness() {
      const [detail, setDetail] = React.useState(persisted);
      const [editorial, setEditorial] = React.useState(snapshot);
      const pending = React.useRef<(() => Promise<boolean>) | null>(null);
      return <>
        <PersonnelOrderItemEditor orderId={1} orderTypeCode="LEAVE.UNPAID.GRANT" items={detail.items} onChanged={setDetail} registerPendingSave={save => { pending.current = save; }} />
        <PersonnelOrderEditorialTextEditor orderId={1} order={detail.order} items={detail.items} editable editorialState={editorial} onEditorialChanged={setEditorial} beforeGenerate={async () => pending.current ? pending.current() : true} />
        <PersonnelOrderDocumentView detail={detail} language="kk" editorial={editorial} />
      </>;
    }
    render(<Harness />);
    const edit = () => fireEvent.click(within(screen.getByTestId("personnel-order-item-editor")).getByRole("button", { name: "Редактировать" }));
    edit();
    const position = () => within(screen.getByTestId("unpaid-leave-kk-document-forms")).getAllByRole("textbox")[1];
    const generate = () => fireEvent.click(screen.getByTestId("personnel-order-editorial-generate"));
    const save = () => fireEvent.click(screen.getByRole("button", { name: "Сохранить пункт" }));
    return { edit, position, generate, save };
  }

  it("changes, saves, confirms generation, renders the saved position and reopens the application date without a second PATCH", async () => {
    const ui = setup();
    fireEvent.change(ui.position(), { target: { value: "шаруа бикесі" } });
    ui.save();
    await screen.findByText("Пункт сохранён. Сформируйте / обновите текст приказа.");
    ui.generate();
    await waitFor(() => expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("шаруа бикесі"));
    expect(updatePersonnelOrderItem).toHaveBeenCalledTimes(1);
    expect(generatePersonnelOrderEditorial).toHaveBeenCalledTimes(1);
    ui.edit();
    expect(ui.position()).toHaveValue("шаруа бикесі");
    expect(screen.getByTestId("leave-application-date")).toHaveValue("2026-06-29");
    ui.generate();
    await waitFor(() => expect(generatePersonnelOrderEditorial).toHaveBeenCalledTimes(2));
    expect(updatePersonnelOrderItem).toHaveBeenCalledTimes(1);
  });

  it("waits for an already running save instead of issuing another PATCH", async () => {
    const ui = setup();
    const save = vi.mocked(updatePersonnelOrderItem).getMockImplementation()!;
    let release!: () => void;
    const gate = new Promise<void>(resolve => { release = resolve; });
    vi.mocked(updatePersonnelOrderItem).mockImplementation(async (...args) => { await gate; return save(...args); });
    fireEvent.change(ui.position(), { target: { value: "шаруа бикесі" } });
    ui.save();
    ui.generate();
    expect(updatePersonnelOrderItem).toHaveBeenCalledTimes(1);
    expect(generatePersonnelOrderEditorial).not.toHaveBeenCalled();
    release();
    await waitFor(() => expect(generatePersonnelOrderEditorial).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("шаруа бикесі");
  });

  it("saves a dirty item before generation; cancelling sends neither request", async () => {
    const ui = setup();
    fireEvent.change(ui.position(), { target: { value: "шаруа бикесі" } });
    vi.mocked(window.confirm).mockReturnValue(false);
    ui.generate();
    expect(updatePersonnelOrderItem).not.toHaveBeenCalled();
    expect(generatePersonnelOrderEditorial).not.toHaveBeenCalled();
    expect(ui.position()).toHaveValue("шаруа бикесі");
    vi.mocked(window.confirm).mockReturnValue(true);
    ui.generate();
    await waitFor(() => expect(generatePersonnelOrderEditorial).toHaveBeenCalledTimes(1));
    expect(updatePersonnelOrderItem).toHaveBeenCalledTimes(1);
    expect(vi.mocked(updatePersonnelOrderItem)).toHaveBeenCalledBefore(vi.mocked(generatePersonnelOrderEditorial));
  });

  it("retains input and stops generation if PATCH fails", async () => {
    const ui = setup();
    vi.mocked(updatePersonnelOrderItem).mockRejectedValueOnce(new Error("Тестовая ошибка сохранения"));
    fireEvent.change(ui.position(), { target: { value: "шаруа бикесі" } });
    ui.generate();
    await screen.findByText("Тестовая ошибка сохранения");
    expect(generatePersonnelOrderEditorial).not.toHaveBeenCalled();
    expect(ui.position()).toHaveValue("шаруа бикесі");
    expect(screen.getByTestId("leave-application-date")).toHaveValue("2026-06-29");
  });

  it("retries failed generation without saving the item again", async () => {
    const ui = setup();
    vi.mocked(generatePersonnelOrderEditorial).mockRejectedValueOnce(new Error("Тестовая ошибка генерации"));
    fireEvent.change(ui.position(), { target: { value: "шаруа бикесі" } });
    ui.generate();
    await screen.findByText("Тестовая ошибка генерации");
    expect(updatePersonnelOrderItem).toHaveBeenCalledTimes(1);
    ui.generate();
    await waitFor(() => expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("шаруа бикесі"));
    expect(updatePersonnelOrderItem).toHaveBeenCalledTimes(1);
    expect(generatePersonnelOrderEditorial).toHaveBeenCalledTimes(2);
  });
});

describe("PersonnelOrderItemEditor draft item deletion", () => {
  const draftItem = {
    item_id: 31,
    order_id: 1,
    item_number: 1,
    item_type_code: "LEAVE.UNPAID.GRANT",
    item_status: "ACTIVE",
    employee_id: 138,
    employee_name: "Макыбаева Акмарал Сабитовна",
    effective_date: "2026-08-03",
    payload: {},
  };

  it("confirms once, deletes the item and lets the parent refresh the list", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onChanged = vi.fn();
    render(<PersonnelOrderItemEditor orderId={1} items={[draftItem]} onChanged={onChanged} />);

    const button = screen.getByTestId("personnel-order-item-delete-31");
    fireEvent.click(button);
    fireEvent.click(button);

    await waitFor(() => {
      expect(deletePersonnelOrderItem).toHaveBeenCalledTimes(1);
      expect(deletePersonnelOrderItem).toHaveBeenCalledWith(1, 31);
      expect(onChanged).toHaveBeenCalledWith(expect.objectContaining({ items: [] }));
    });
  });

  it("does not delete when confirmation is cancelled", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<PersonnelOrderItemEditor orderId={1} items={[draftItem]} onChanged={vi.fn()} />);

    fireEvent.click(screen.getByTestId("personnel-order-item-delete-31"));

    expect(deletePersonnelOrderItem).not.toHaveBeenCalled();
  });
});

describe("PersonnelOrderItemEditor unpaid-leave period", () => {

  it("edits and reopens childcare grounds without inferring the leave end from certificate issuance", async () => {
    const item = { item_id: 54, order_id: 1, item_number: 1, item_type_code: "LEAVE.CHILDCARE.GRANT", item_status: "ACTIVE", employee_id: 138, employee_name: "Employee", effective_date: "2026-08-01", payload: {
      leave_start: "2026-08-01", leave_end: "2029-02-13", leave_days: 928,
      basis: { kind: "PERSONAL_APPLICATION", date: "2026-07-28", number: "APP-17", birth_certificate: { date: "2026-02-13", number: "9967264" } },
      document_forms_kk: { org_unit_document_genitive_kk: "Тест бөлімшесінің", position_document_possessive_kk: "мейіргері", employee_full_name_dative_kk: "Асем Бауыржановна Садырбаеваға", employee_full_name_genitive_kk: "Асем Бауыржановна Садырбаеваның" },
      document_forms_ru: { employee_full_name_dative_ru: "Садырбаевой Асем Бауыржановне", employee_full_name_genitive_ru: "Садырбаевой Асем Бауыржановны", position_document_nominative_ru: "медицинская сестра" },
    } } as any;
    const view = render(<PersonnelOrderItemEditor orderId={1} items={[item]} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));
    const certificate = screen.getByTestId("childcare-birth-certificate").querySelectorAll("input");
    expect(certificate[0]).toHaveValue("2026-02-13");
    expect(certificate[1]).toHaveValue("9967264");
    fireEvent.change(certificate[0], { target: { value: "2027-04-20" } });
    fireEvent.change(certificate[1], { target: { value: "NEW-45" } });
    expect(screen.getByTestId("leave-end")).toHaveValue("2029-02-13");
    fireEvent.click(screen.getByRole("button", { name: "Сохранить пункт" }));
    await waitFor(() => expect(updatePersonnelOrderItem).toHaveBeenCalled());
    const saved = vi.mocked(updatePersonnelOrderItem).mock.calls[0][2].payload;
    expect(saved).toMatchObject({ leave_end: "2029-02-13", basis: { date: "2026-07-28", number: "APP-17", birth_certificate: { date: "2027-04-20", number: "NEW-45" } }, document_forms_kk: item.payload.document_forms_kk, document_forms_ru: item.payload.document_forms_ru });
    view.unmount();
    render(<PersonnelOrderItemEditor orderId={1} items={[{ ...item, payload: saved }]} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));
    expect(screen.getByDisplayValue("NEW-45")).toBeInTheDocument();
    expect(screen.getByTestId("leave-application-date")).toHaveValue("2026-07-28");
    expect(screen.getByDisplayValue("мейіргері")).toBeInTheDocument();
  });
  it("marks a changed saved KK position and clears the marker after reverting", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[{
      item_id: 51, order_id: 1, item_number: 1, item_type_code: "LEAVE.UNPAID.GRANT", item_status: "ACTIVE",
      employee_id: 138, employee_name: "Employee", effective_date: "2026-07-02",
      payload: { leave: { period_type: "CONTINUOUS_RANGE", start: "2026-07-02", end: "2026-07-03", days: 2 }, application_date: "2026-06-29", document_forms_kk: { position_document_possessive_kk: "дәрігері" } },
    } as any]} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));
    const position = await screen.findByDisplayValue("дәрігері");
    fireEvent.change(position, { target: { value: "шаруа бикесі" } });
    expect(screen.getByText("Есть несохранённые изменения")).toBeInTheDocument();
    fireEvent.change(position, { target: { value: "дәрігері" } });
    expect(screen.queryByText("Есть несохранённые изменения")).not.toBeInTheDocument();
  });

  it("updates an existing unpaid-leave range with matching inclusive days", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[{
      item_id: 52, order_id: 1, item_number: 1, item_type_code: "LEAVE.UNPAID.GRANT", item_status: "ACTIVE",
      employee_id: 138, employee_name: "Employee", effective_date: "2026-07-02",
      payload: {
        leave: { period_type: "CONTINUOUS_RANGE", start: "2026-07-02", end: "2026-07-03", days: 2 },
        leave_start: "2026-07-02", leave_end: "2026-07-03", leave_days: 2,
        application_date: "2026-06-29",
      },
    } as any]} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));
    expect(await screen.findByTestId("leave-days")).toHaveValue("2");
    fireEvent.change(screen.getByTestId("leave-start"), { target: { value: "2026-07-01" } });
    fireEvent.change(screen.getByTestId("leave-end"), { target: { value: "2026-07-12" } });
    expect(screen.getByTestId("leave-days")).toHaveValue("12");
    fireEvent.click(screen.getByRole("button", { name: "Сохранить пункт" }));
    await waitFor(() => expect(updatePersonnelOrderItem).toHaveBeenCalledWith(1, 52, expect.objectContaining({
      effective_date: "2026-07-01", period_start: "2026-07-01", period_end: "2026-07-12",
      payload: expect.objectContaining({ leave: { period_type: "CONTINUOUS_RANGE", start: "2026-07-01", end: "2026-07-12", days: 12 } }),
    })));
    const body = vi.mocked(updatePersonnelOrderItem).mock.calls[0]?.[2] as { payload: Record<string, unknown> };
    expect(body.payload).not.toHaveProperty("leave_start");
    expect(body.payload).not.toHaveProperty("leave_end");
    expect(body.payload).not.toHaveProperty("leave_days");
  });

  it("shows the inclusive-days contract error in Russian", async () => {
    vi.mocked(updatePersonnelOrderItem).mockRejectedValueOnce(new Error("CONTINUOUS_RANGE leave.days must equal inclusive range days."));
    render(<PersonnelOrderItemEditor orderId={1} items={[{
      item_id: 53, order_id: 1, item_number: 1, item_type_code: "LEAVE.UNPAID.GRANT", item_status: "ACTIVE",
      employee_id: 138, employee_name: "Employee", effective_date: "2026-07-02",
      payload: { leave: { period_type: "CONTINUOUS_RANGE", start: "2026-07-02", end: "2026-07-03", days: 2 }, application_date: "2026-06-29" },
    } as any]} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));
    fireEvent.change(await screen.findByTestId("leave-start"), { target: { value: "2026-07-01" } });
    fireEvent.change(screen.getByTestId("leave-end"), { target: { value: "2026-07-12" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить пункт" }));
    expect(await screen.findByText("Количество календарных дней отпуска должно совпадать с выбранным периодом включительно.")).toBeInTheDocument();
  });
});

describe("PersonnelOrderItemEditor TERMINATION", () => {
  it("updates a historical TERMINATION employee without active search and preserves its item data", async () => {
    const originalPayload = {
      org_unit_id: 17,
      org_unit_name: "Архивное подразделение",
      position_id: 29,
      position_name: "Архивная должность",
      basis_ids: ["application-1"],
      source_reference: { file_id: "source-1" },
      legacy_flag: true,
    };
    const savedDetail = {
      order: { order_id: 1 },
      items: [{
        item_id: 12, order_id: 1, item_number: 1, item_type_code: "TERMINATION",
        item_status: "ACTIVE", employee_id: 999, employee_name: "Уволенный сотрудник",
        effective_date: "2026-09-30", payload: { ...originalPayload, termination_reason: "EMPLOYEE_INITIATIVE" },
      }], localized_texts: [], events: [], acknowledgements: [], applications: [],
    } as any;
    vi.mocked(updatePersonnelOrderItem).mockResolvedValue(savedDetail);
    const onChanged = vi.fn();
    const { rerender } = render(<PersonnelOrderItemEditor orderId={1} items={[{
      ...savedDetail.items[0], payload: originalPayload,
    }]} onChanged={onChanged} />);

    fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));
    await screen.findByTestId("personnel-order-termination-reason-input");
    expect(screen.getByTestId("personnel-order-linked-employee-card")).toHaveTextContent("Уволенный сотрудник");
    expect(screen.getByTestId("personnel-order-linked-employee-card")).toHaveTextContent("ID: 999");
    expect(screen.queryByTestId("personnel-order-employee-id-input")).not.toBeInTheDocument();
    expect(screen.getByDisplayValue("2026-09-30")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("personnel-order-termination-reason-input"), {
      target: { value: "EMPLOYEE_INITIATIVE" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить пункт" }));

    await waitFor(() => expect(updatePersonnelOrderItem).toHaveBeenCalledWith(1, 12, expect.objectContaining({
      employee_id: 999,
      effective_date: "2026-09-30",
      payload: expect.objectContaining({
        ...originalPayload,
        basis_ids: ["application-1"],
        termination_reason: "EMPLOYEE_INITIATIVE",
      }),
    })));
    expect(getEmployees).not.toHaveBeenCalled();
    await waitFor(() => expect(onChanged).toHaveBeenCalledWith(savedDetail));

    rerender(<PersonnelOrderItemEditor orderId={1} items={savedDetail.items} onChanged={onChanged} />);
    fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));
    expect(await screen.findByTestId("personnel-order-termination-reason-input")).toHaveValue("EMPLOYEE_INITIATIVE");
  });
  it("reveals active employee search only after explicit employee change", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[{
      item_id: 14, order_id: 1, item_number: 1, item_type_code: "TERMINATION", item_status: "ACTIVE",
      employee_id: 999, employee_name: "Уволенный сотрудник", effective_date: "2026-09-30", payload: {},
    } as any]} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));
    expect(screen.queryByTestId("personnel-order-employee-search-input")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Сменить сотрудника" }));
    expect(screen.getByTestId("personnel-order-employee-search-input")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-employee-id-input")).toBeInTheDocument();
  });
  it("proposes employee initiative from PERSONAL_APPLICATION without writing until save", async () => {
    const item = {
      item_id: 13, order_id: 1, item_number: 1, item_type_code: "TERMINATION", item_status: "ACTIVE",
      employee_id: 999, employee_name: "Уволенный сотрудник", effective_date: "2026-09-30",
      payload: { basis: { kind: "PERSONAL_APPLICATION" }, basis_ids: ["application-1"] },
    } as any;
    render(<PersonnelOrderItemEditor orderId={1} items={[item]} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));
    expect(await screen.findByTestId("personnel-order-termination-reason-input")).toHaveValue("EMPLOYEE_INITIATIVE");
    expect(screen.getByTestId("personnel-order-termination-reason-suggestion")).toHaveTextContent("Определено по основанию: личное заявление работника");
    expect(updatePersonnelOrderItem).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Сохранить пункт" }));
    await waitFor(() => expect(updatePersonnelOrderItem).toHaveBeenCalledWith(1, 13, expect.objectContaining({
      payload: expect.objectContaining({ termination_reason: "EMPLOYEE_INITIATIVE" }),
    })));
  });
});

describe("PersonnelOrderItemEditor HIRE", () => {

  it("disables pending-new-employee checkbox when editing saved HIRE with employee_id", async () => {
    render(
      <PersonnelOrderItemEditor
        orderId={1}
        orderTypeCode="HIRE"
        items={[
          {
            item_id: 21,
            order_id: 1,
            item_number: 1,
            item_type_code: "HIRE",
            item_status: "ACTIVE",
            employee_id: 138,
            employee_name: "Макибаева Акмарал Сабитовна",
            effective_date: "2026-03-01",
            payload: { org_unit_id: 10, position_id: 77, employment_rate: 1 },
          },
        ]}
        onChanged={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-pending-new-employee")).toBeDisabled();
    });
    expect(screen.getByTestId("personnel-order-pending-new-employee-reset-blocked")).toHaveTextContent(
      "Сброс сотрудника в сохранённом пункте пока не поддерживается.",
    );
    expect(screen.getByTestId("personnel-order-pending-new-employee")).not.toBeChecked();
    expect(screen.getByTestId("personnel-order-linked-employee-card")).toHaveTextContent("ID: 138");

    fireEvent.click(screen.getByTestId("personnel-order-pending-new-employee"));
    fireEvent.click(screen.getByRole("button", { name: "Сменить сотрудника" }));
    fireEvent.change(screen.getByTestId("personnel-order-employee-id-input"), { target: { value: "" } });
    fireEvent.change(screen.getByTestId("personnel-order-employee-search-input"), {
      target: { value: "" },
    });

    expect(screen.getByTestId("personnel-order-pending-new-employee")).toBeDisabled();
    expect(screen.getByTestId("personnel-order-pending-new-employee")).not.toBeChecked();
  });

  it("allows assigning employee when editing saved HIRE without employee_id", async () => {
    const onChanged = vi.fn();
    render(
      <PersonnelOrderItemEditor
        orderId={1}
        orderTypeCode="HIRE"
        items={[
          {
            item_id: 22,
            order_id: 1,
            item_number: 1,
            item_type_code: "HIRE",
            item_status: "ACTIVE",
            employee_id: null,
            employee_name: null,
            effective_date: "2026-03-01",
            payload: { org_unit_id: 10, position_id: 77, employment_rate: 1 },
          },
        ]}
        onChanged={onChanged}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-pending-new-employee")).toBeEnabled();
      expect(screen.getByTestId("personnel-order-pending-new-employee")).toBeChecked();
    });

    fireEvent.click(screen.getByTestId("personnel-order-pending-new-employee"));

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-pending-new-employee")).not.toBeChecked();
      expect(screen.getByTestId("personnel-order-employee-search-input")).toBeInTheDocument();
    });

    vi.mocked(getEmployees).mockResolvedValue({
      items: [activeEmployee],
      total: 1,
    });
    fireEvent.change(screen.getByTestId("personnel-order-employee-search-input"), {
      target: { value: "Маки" },
    });
    fireEvent.click(await screen.findByTestId("personnel-order-employee-option-138"));

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-pending-new-employee")).not.toBeChecked();
      expect(screen.getByTestId("personnel-order-employee-id-input")).toHaveValue("138");
    });

    fireEvent.click(screen.getByRole("button", { name: "Сохранить пункт" }));

    await waitFor(() => {
      expect(updatePersonnelOrderItem).toHaveBeenCalledWith(1, 22, expect.any(Object));
    });

    const body = vi.mocked(updatePersonnelOrderItem).mock.calls[0]?.[2] as {
      employee_id: number | null;
    };
    expect(body.employee_id).toBe(138);
  });

  it("keeps pending-new-employee disabled when item type changes to HIRE on saved employee", async () => {
    render(
      <PersonnelOrderItemEditor
        orderId={1}
        orderTypeCode="COMPOSITE"
        items={[
          {
            item_id: 23,
            order_id: 1,
            item_number: 1,
            item_type_code: "TRANSFER",
            item_status: "ACTIVE",
            employee_id: 138,
            employee_name: "Макибаева Акмарал Сабитовна",
            effective_date: "2026-01-01",
            payload: { to_org_unit_id: 73, to_position_id: 86, to_rate: 1 },
          },
        ]}
        onChanged={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));
    fireEvent.change(screen.getByTestId("personnel-order-item-type-select"), {
      target: { value: "HIRE" },
    });

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-pending-new-employee")).toBeDisabled();
    });
    expect(screen.getByTestId("personnel-order-pending-new-employee-reset-blocked")).toBeInTheDocument();
  });
});

describe("PersonnelOrderItemEditor non-HIRE pending guard", () => {
  it("does not show pending-new-employee checkbox for TRANSFER", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);
    expect(screen.queryByTestId("personnel-order-pending-new-employee")).not.toBeInTheDocument();
  });
});

describe("PersonnelOrderItemEditor startEdit org scope", () => {
  it("resolves target org group when editing a TRANSFER item", async () => {
    render(
      <PersonnelOrderItemEditor
        orderId={1}
        items={[
          {
            item_id: 9,
            order_id: 1,
            item_number: 1,
            item_type_code: "TRANSFER",
            item_status: "ACTIVE",
            employee_id: 138,
            employee_name: "Макибаева Акмарал Сабитовна",
            effective_date: "2026-01-01",
            payload: { to_org_unit_id: 73, to_position_id: 86, to_rate: 1 },
          },
        ]}
        onChanged={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));

    await waitFor(() => {
      expect(resolveEmployeeOrgScopePrefill).toHaveBeenCalledWith(73);
    });
    await waitFor(() => {
      expect(screen.getByTestId("mock-org-group-Группа отделений")).toHaveValue("2");
    });
    expect(screen.getByTestId("personnel-order-item-type-select")).toHaveValue("TRANSFER");
  });

  it("opens RATE_CHANGE form for TRANSFER item with to_rate only", async () => {
    render(
      <PersonnelOrderItemEditor
        orderId={1}
        items={[
          {
            item_id: 10,
            order_id: 1,
            item_number: 2,
            item_type_code: "TRANSFER",
            item_status: "ACTIVE",
            employee_id: 138,
            employee_name: "Макибаева Акмарал Сабитовна",
            effective_date: "2026-02-01",
            payload: { to_rate: 0.5 },
          },
        ]}
        onChanged={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Редактировать" }));

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-item-type-select")).toHaveValue("RATE_CHANGE");
    });
    expect(screen.getByTestId("personnel-order-new-rate-input")).toHaveValue("0.5");
  });
});
