import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import PersonnelOrderCreateDialog from "./PersonnelOrderCreateDialog";

vi.mock("../_lib/personnelOrdersApi.client", async () => ({
  ...(await vi.importActual<object>("../_lib/personnelOrdersApi.client")),
  getPersonnelOrderPublishedTemplateTitle: vi.fn(),
  previewPersonnelOrderHeaderDuplicate: vi.fn(),
  createManualPersonnelOrderDraft: vi.fn(),
}));
vi.mock("@/app/directory/employees/_lib/api.client", () => ({ getEmployee: vi.fn(), getEmployees: vi.fn() }));

import {
  createManualPersonnelOrderDraft,
  getPersonnelOrderPublishedTemplateTitle,
  previewPersonnelOrderHeaderDuplicate,
} from "../_lib/personnelOrdersApi.client";
import { getEmployee, getEmployees } from "@/app/directory/employees/_lib/api.client";

// Actual /directory/employees search item and /directory/employees/383 detail.
const employee = {
  id: "383",
  person_id: 720,
  fio: "Ильясова Ассель Адиловна",
  position: { id: 6, name: "Врач" },
  org_unit: { unit_id: 59, name: "Лучевая диагностика", code: "DIAG_IMG", parent_unit_id: 41, is_active: true },
  department: null,
  rate: "1.0",
  status: "active",
  date_from: "2026-05-15",
  date_to: null,
  termination: null,
  source: { relation: "employees" },
};
const employeeDetail = { ...employee, active_assignment_id: 361, user: null };

const unpaidTitles = {
  item_type_code: "LEAVE.UNPAID.GRANT",
  title_kk: "Еңбекақысы сақталмайтын демалыс туралы",
  title_ru: "О предоставлении отпуска без сохранения заработной платы",
};
const transferTitles = {
  item_type_code: "TRANSFER",
  title_kk: "Басқа лауазымға ауыстыру туралы",
  title_ru: "О переводе на другую должность",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function setup(onClose = vi.fn(), onCreated = vi.fn()) {
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockImplementation(async (type) =>
    type === "TRANSFER" ? transferTitles : unpaidTitles,
  );
  vi.mocked(getEmployees).mockResolvedValue({ items: [employee], total: 1 });
  vi.mocked(getEmployee).mockResolvedValue(employeeDetail);
  render(<PersonnelOrderCreateDialog open onClose={onClose} onCreated={onCreated} />);
  return { onClose, onCreated };
}

async function selectType(type: "LEAVE.UNPAID.GRANT" | "TRANSFER") {
  fireEvent.change(screen.getByLabelText("Тип кадрового приказа"), { target: { value: type } });
  await waitFor(() => expect(getPersonnelOrderPublishedTemplateTitle).toHaveBeenLastCalledWith(type));
}

async function selectUnpaid() {
  await selectType("LEAVE.UNPAID.GRANT");
  await waitFor(() => expect(screen.getByLabelText("Название приказа")).toHaveValue(unpaidTitles.title_kk));
}

async function selectEmployee() {
  fireEvent.change(screen.getByLabelText("Сотрудник"), { target: { value: "Иль" } });
  fireEvent.click(await screen.findByRole("option", { name: "Ильясова Ассель Адиловна" }));
  await waitFor(() => expect(screen.getByLabelText("Подразделение")).toBeInTheDocument());
}

async function fillValidUnpaid() {
  await selectUnpaid();
  await selectEmployee();
  fireEvent.change(screen.getByLabelText("Номер приказа"), { target: { value: "T-1" } });
  fireEvent.change(screen.getByLabelText("Дата приказа"), { target: { value: "2026-07-01" } });
  fireEvent.change(screen.getByLabelText("Дата начала"), { target: { value: "2026-07-17" } });
}

it("starts without a type, template request, title, employee fields, or enabled Create", () => {
  setup();
  expect(screen.getByLabelText("Тип кадрового приказа")).toHaveValue("");
  expect(screen.getByLabelText("Название приказа")).toHaveValue("");
  expect(screen.queryByLabelText("Сотрудник")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Создать приказ" })).toBeDisabled();
  expect(getPersonnelOrderPublishedTemplateTitle).not.toHaveBeenCalled();
  expect(getEmployees).not.toHaveBeenCalled();
  expect(getEmployee).not.toHaveBeenCalled();
});

it("renders a dialog with dedicated header, scrollable body, and sticky footer", async () => {
  setup();
  await selectUnpaid();
  expect(screen.getByRole("dialog", { name: "Создать приказ" })).toBeInTheDocument();
  expect(screen.getByTestId("personnel-order-create-header")).toHaveTextContent("Будет создан новый приказ в статусе DRAFT");
  expect(screen.getByTestId("personnel-order-create-body")).toHaveClass("overflow-y-auto");
  expect(screen.getByTestId("personnel-order-create-footer")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Отмена" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Создать приказ" })).toBeInTheDocument();
});

it("selecting unpaid shows only its current-language PUBLISHED title and unpaid fields", async () => {
  setup();
  await selectUnpaid();
  expect(screen.getByLabelText("Дата начала")).toBeInTheDocument();
  expect(screen.getByLabelText("Название приказа")).toHaveAttribute("readonly");
  expect(screen.queryByLabelText("Дата действия")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Язык"), { target: { value: "ru" } });
  await waitFor(() => expect(screen.getByLabelText("Название приказа")).toHaveValue(unpaidTitles.title_ru));
  expect(getPersonnelOrderPublishedTemplateTitle).toHaveBeenLastCalledWith("LEAVE.UNPAID.GRANT");
});

it("never displays the unpaid title after TRANSFER is selected", async () => {
  setup();
  await selectUnpaid();
  await selectType("TRANSFER");
  await waitFor(() => expect(screen.getByLabelText("Название приказа")).toHaveValue(transferTitles.title_kk));
  expect(screen.getByLabelText("Название приказа")).not.toHaveValue(unpaidTitles.title_kk);
  expect(screen.getByLabelText("Дата действия")).toBeInTheDocument();
  expect(screen.queryByLabelText("Дата начала")).not.toBeInTheDocument();
});

it("ignores an old unpaid response when type changes to TRANSFER before it resolves", async () => {
  let resolveUnpaid: ((value: typeof unpaidTitles) => void) | undefined;
  let resolveTransfer: ((value: typeof transferTitles) => void) | undefined;
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockImplementation((type) => new Promise((resolve) => {
    if (type === "LEAVE.UNPAID.GRANT") resolveUnpaid = resolve as (value: typeof unpaidTitles) => void;
    else resolveTransfer = resolve as (value: typeof transferTitles) => void;
  }));
  render(<PersonnelOrderCreateDialog open onClose={vi.fn()} onCreated={vi.fn()} />);
  await selectType("LEAVE.UNPAID.GRANT");
  await selectType("TRANSFER");
  resolveTransfer?.(transferTitles);
  await waitFor(() => expect(screen.getByLabelText("Название приказа")).toHaveValue(transferTitles.title_kk));
  resolveUnpaid?.(unpaidTitles);
  await waitFor(() => expect(screen.getByLabelText("Название приказа")).not.toHaveValue(unpaidTitles.title_kk));
});

it("clears previous leave dates and document forms when type changes", async () => {
  setup();
  await selectUnpaid();
  await selectEmployee();
  fireEvent.change(screen.getByLabelText("Дата начала"), { target: { value: "2026-07-17" } });
  fireEvent.change(screen.getByLabelText("ФИО сотрудника в дательном падеже (KK)"), { target: { value: "Тестоваға" } });
  await selectType("TRANSFER");
  await selectType("LEAVE.UNPAID.GRANT");
  expect(screen.getByLabelText("Дата начала")).toHaveValue("");
  expect(screen.getByLabelText("Дата окончания")).toHaveValue("");
  expect(screen.getByLabelText("ФИО сотрудника в дательном падеже (KK)")).toHaveValue("");
});

it("uses a canonical title when PUBLISHED template is absent", async () => {
  setup();
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockRejectedValueOnce(new Error("not found"));
  await selectType("TRANSFER");
  expect(await screen.findByRole("alert")).toHaveTextContent("отсутствует опубликованный шаблон");
  expect(screen.getByLabelText("Название приказа")).toHaveValue("Ауыстыру туралы");
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it("loads only a read-only template GET while the dialog is opened and a type is selected", async () => {
  setup();
  await selectUnpaid();
  expect(getPersonnelOrderPublishedTemplateTitle).toHaveBeenCalledTimes(1);
  expect(previewPersonnelOrderHeaderDuplicate).not.toHaveBeenCalled();
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it("loads the primary assignment and keeps the footer after the unpaid KK fields appear", async () => {
  setup();
  await selectUnpaid();
  await selectEmployee();
  expect(screen.getByLabelText("Подразделение")).toHaveValue("Лучевая диагностика");
  expect(screen.getByLabelText("Должность")).toHaveValue("Врач");
  fireEvent.change(screen.getByLabelText("Дата начала"), { target: { value: "2026-07-07" } });
  expect(screen.getByLabelText("Дата окончания")).toHaveValue("2026-07-07");
  expect(screen.getByLabelText("ФИО сотрудника в родительном падеже (KK)")).toBeInTheDocument();
  expect(screen.getByTestId("personnel-order-create-footer")).toContainElement(screen.getByRole("button", { name: "Создать приказ" }));
});

it("closes without saving through Cancel and keeps Create disabled while required data is missing", async () => {
  const { onClose } = setup();
  await selectUnpaid();
  expect(screen.getByRole("button", { name: "Создать приказ" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Отмена" }));
  expect(onClose).toHaveBeenCalledTimes(1);
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it("blocks an invalid reverse unpaid range before request submission", async () => {
  setup();
  await fillValidUnpaid();
  fireEvent.change(screen.getByLabelText("Дата окончания"), { target: { value: "2026-07-10" } });
  expect(screen.getByRole("button", { name: "Создать приказ" })).toBeDisabled();
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it("keeps Create disabled and names missing document forms", async () => {
  setup();
  vi.mocked(getEmployee).mockResolvedValueOnce({ ...employee, org_unit: { ...employee.org_unit, unit_id: 999 }, position: { ...employee.position, id: 999 } });
  await selectUnpaid();
  await selectEmployee();
  fireEvent.change(screen.getByLabelText("Номер приказа"), { target: { value: "T-1" } });
  fireEvent.change(screen.getByLabelText("Дата приказа"), { target: { value: "2026-07-01" } });
  fireEvent.change(screen.getByLabelText("Дата начала"), { target: { value: "2026-07-17" } });
  expect(screen.getByRole("button", { name: "Создать приказ" })).toBeDisabled();
  expect(screen.getByRole("alert")).toHaveTextContent("Подразделение в тексте приказа (KK)");
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

it("fills Ilyasova's actual active-assignment document forms from the API detail and keeps them collapsed", async () => {
  setup();
  await fillValidUnpaid();

  const forms = screen.getByTestId("personnel-order-text-forms");
  expect(forms).not.toHaveAttribute("open");
  expect(forms).toHaveTextContent("Формы для текста приказа заполнены автоматически");
  expect(screen.getByLabelText("Подразделение в тексте приказа (KK)")).toHaveValue("Сәулелік диагностика бөлімшесінің");
  expect(screen.getByLabelText("Должность в тексте приказа (KK)")).toHaveValue("дәрігері");
  expect(screen.getByLabelText("Должность в тексте приказа (RU)")).toHaveValue("врач");
  expect(screen.getByLabelText("ФИО сотрудника в дательном падеже (KK)")).toHaveValue("Ассель Адиловна Ильясоваға");
  expect(screen.getByLabelText("ФИО сотрудника в родительном падеже (KK)")).toHaveValue("Ассель Адиловна Ильясованың");
  expect(screen.getByLabelText("ФИО сотрудника в дательном падеже (RU)")).toHaveValue("Ильясовой Ассель Адиловне");
  expect(screen.getByRole("button", { name: "Создать приказ" })).toBeEnabled();

  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({ blocking: false, warnings: [], candidates: [] });
  vi.mocked(createManualPersonnelOrderDraft).mockResolvedValue({ order_id: 1 } as never);
  fireEvent.click(screen.getByRole("button", { name: "Создать приказ" }));
  await waitFor(() => expect(createManualPersonnelOrderDraft).toHaveBeenCalledWith(expect.objectContaining({
    item_payload: expect.objectContaining({
      document_forms_kk: expect.objectContaining({ position_document_possessive_kk: "дәрігері" }),
      document_forms_ru: expect.objectContaining({ position_document_nominative_ru: "врач", employee_full_name_dative_ru: "Ильясовой Ассель Адиловне" }),
    }),
  })));
});

it("keeps actual API document forms after asynchronous detail loading and a subsequent rerender", async () => {
  setup();
  let resolveDetail: ((value: typeof employeeDetail) => void) | undefined;
  vi.mocked(getEmployee).mockImplementationOnce(() => new Promise((resolve) => { resolveDetail = resolve as (value: typeof employeeDetail) => void; }));
  await selectUnpaid();
  fireEvent.change(screen.getByLabelText("Сотрудник"), { target: { value: "Иль" } });
  fireEvent.click(await screen.findByRole("option", { name: "Ильясова Ассель Адиловна" }));
  expect(screen.queryByTestId("personnel-order-text-forms")).not.toBeInTheDocument();

  resolveDetail?.(employeeDetail);
  const forms = await screen.findByTestId("personnel-order-text-forms");
  fireEvent.change(screen.getByLabelText("Язык"), { target: { value: "ru" } });

  expect(forms).not.toHaveAttribute("open");
  expect(screen.getByLabelText("Должность в тексте приказа (KK)")).toHaveValue("дәрігері");
  expect(screen.getByLabelText("Должность в тексте приказа (RU)")).toHaveValue("врач");
  expect(screen.getByLabelText("ФИО сотрудника в дательном падеже (RU)")).toHaveValue("Ильясовой Ассель Адиловне");
});

it("prevents a second request while the first create request is pending", async () => {
  setup();
  await fillValidUnpaid();
  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({ blocking: false, warnings: [], candidates: [] });
  let resolveCreate: ((value: never) => void) | undefined;
  vi.mocked(createManualPersonnelOrderDraft).mockImplementationOnce(() => new Promise((resolve) => { resolveCreate = resolve as (value: never) => void; }));
  const create = screen.getByRole("button", { name: "Создать приказ" });
  fireEvent.click(create);
  fireEvent.click(create);
  await waitFor(() => expect(createManualPersonnelOrderDraft).toHaveBeenCalledTimes(1));
  expect(screen.getByRole("button", { name: "Создание…" })).toBeDisabled();
  resolveCreate?.({ order_id: 1 } as never);
});
