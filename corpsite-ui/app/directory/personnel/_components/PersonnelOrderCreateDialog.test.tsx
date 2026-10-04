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
vi.mock("@/lib/orgUnitsSelect", () => ({ loadOrgUnitSelectOptions: vi.fn() }));

import {
  createManualPersonnelOrderDraft,
  getPersonnelOrderPublishedTemplateTitle,
  previewPersonnelOrderHeaderDuplicate,
} from "../_lib/personnelOrdersApi.client";
import { getEmployee, getEmployees } from "@/app/directory/employees/_lib/api.client";
import { loadOrgUnitSelectOptions } from "@/lib/orgUnitsSelect";

// Actual /directory/employees search item and /directory/employees/383 detail.
const employee = {
  id: "383",
  person_id: 720,
  fio: "Ильясова Ассель Адиловна",
  position: { id: 6, name: "Врач", name_kk: "дәрігер" },
  org_unit: { unit_id: 59, name: "Лучевая диагностика", code: "DIAG_IMG", parent_unit_id: 41, is_active: true },
  department: null,
  rate: "1.0",
  status: "active",
  date_from: "2026-05-15",
  date_to: null,
  termination: null,
  source: { relation: "employees" },
};
const employeeDetail = {
  ...employee,
  active_assignment_id: 361,
  org_unit: { ...employee.org_unit, document_genitive_kk: "Сәулелік диагностика бөлімшесінің" },
  user: null,
};

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
  vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue([
    { unit_id: 41, name: "Многопрофильный медицинский центр", group_id: null, name_kk: null, document_genitive_kk: null },
    { unit_id: 59, name: "Лучевая диагностика", group_id: 2, name_kk: "Сәулелік диагностика бөлімшесі", document_genitive_kk: "Сәулелік диагностика бөлімшесінің" },
  ]);
  const view = render(<PersonnelOrderCreateDialog open onClose={onClose} onCreated={onCreated} />);
  return { onClose, onCreated, ...view };
}

async function selectType(type: "LEAVE.UNPAID.GRANT" | "LEAVE.CHILDCARE.GRANT" | "TRANSFER") {
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

it.each(["LEAVE.CHILDCARE.GRANT", "LEAVE.UNPAID.GRANT"] as const)("autofills actual API Медсестра in create %s", async (type) => {
  setup();
  vi.mocked(getEmployee).mockResolvedValue({ ...employeeDetail, position: { id: 27, name: "Медсестра", name_kk: "мейіргер" } });
  await selectType(type);
  await selectEmployee();
  await waitFor(() => expect(screen.getByLabelText("Должность в тексте приказа (KK)")).toHaveValue("мейіргері"));
  expect(screen.getByLabelText("Должность в тексте приказа (RU)")).toHaveValue("медсестра");
  expect(screen.queryByText(/Необходимо заполнить:/)).not.toBeInTheDocument();
});

it.each(["LEAVE.CHILDCARE.GRANT", "LEAVE.UNPAID.GRANT"] as const)("uses arbitrary catalogue positions and warns only for missing KK in %s", async type => {
  setup();
  vi.mocked(getEmployee).mockResolvedValue({ ...employeeDetail, position: { id: 44, name: "сестра-хозяйка", name_kk: "шаруа бикесі" } });
  await selectType(type); await selectEmployee();
  expect(screen.getByLabelText("Должность в тексте приказа (KK)")).toHaveValue("шаруа бикесі");
  expect(screen.getByLabelText("Должность в тексте приказа (RU)")).toHaveValue("сестра-хозяйка");
  fireEvent.change(screen.getByLabelText("Должность в тексте приказа (KK)"), { target: { value: "Ручная форма первого сотрудника" } });
  fireEvent.click(screen.getByRole("button", { name: "Сменить сотрудника" }));
  const second = { ...employeeDetail, id: "777", fio: "Ильясова Анна Сергеевна", position: { id: 3, name: "Бухгалтер", name_kk: null } };
  vi.mocked(getEmployees).mockResolvedValue({ items: [employee, second], total: 2 });
  vi.mocked(getEmployee).mockResolvedValue(second);
  fireEvent.change(screen.getByLabelText("Сотрудник"), { target: { value: "Ильясова" } });
  fireEvent.click(await screen.findByRole("option", { name: second.fio }));
  await waitFor(() => expect(getEmployee).toHaveBeenLastCalledWith("777"));
  await waitFor(() => expect(screen.getByLabelText("Должность в тексте приказа (RU)")).toHaveValue("бухгалтер"));
  expect(screen.getByLabelText("Должность в тексте приказа (RU)")).toHaveValue("бухгалтер");
  expect(screen.getByLabelText("Должность в тексте приказа (KK)")).toHaveValue("");
  expect(screen.getByText(/В справочнике должности нет казахского названия/)).toBeInTheDocument();
});

it.each(["LEAVE.CHILDCARE.GRANT", "LEAVE.UNPAID.GRANT"] as const)("preserves manual position edits across late detail, then refreshes on employee change in %s", async (type) => {
  const { rerender, onClose, onCreated } = setup();
  await selectType(type);
  await selectEmployee();
  const nurse = { ...employeeDetail, id: "618", fio: "Адилова Жадыра Хабибуловна", position: { id: 27, name: "Медсестра", name_kk: "мейіргер" },
    document_forms_ru: { position_document_nominative_ru: "Сохранённая RU" },
    document_forms_kk: { position_document_possessive_kk: "Сохранённая KK" },
  };
  vi.mocked(getEmployees).mockResolvedValue({ items: [nurse], total: 1 });
  let resolveDetail!: (value: typeof nurse) => void;
  vi.mocked(getEmployee).mockResolvedValueOnce(nurse).mockReturnValueOnce(new Promise(resolve => { resolveDetail = resolve; }));
  rerender(<PersonnelOrderCreateDialog open onClose={onClose} onCreated={onCreated} initialEmployeeId={618} />);
  const ru = screen.getByLabelText("Должность в тексте приказа (RU)");
  const kk = screen.getByLabelText("Должность в тексте приказа (KK)");
  await waitFor(() => expect(ru).toHaveValue("")); expect(kk).toHaveValue("");
  fireEvent.change(ru, { target: { value: "Ручная RU" } });
  fireEvent.change(kk, { target: { value: "Ручная KK" } });
  const unit = screen.getByLabelText("Подразделение в тексте приказа (KK)");
  fireEvent.change(unit, { target: { value: "Ручное подразделение" } });
  resolveDetail(nurse);
  await waitFor(() => expect(screen.getByLabelText("Должность")).toHaveValue("Медсестра"));
  expect(ru).toHaveValue("Ручная RU"); expect(kk).toHaveValue("Ручная KK");
  expect(unit).toHaveValue("Ручное подразделение");
  fireEvent.change(screen.getByLabelText("Дата начала"), { target: { value: "2026-08-01" } });
  expect(ru).toHaveValue("Ручная RU"); expect(kk).toHaveValue("Ручная KK");
  vi.mocked(getEmployee).mockResolvedValue({ ...nurse, id: "619" });
  rerender(<PersonnelOrderCreateDialog open onClose={onClose} onCreated={onCreated} initialEmployeeId={619} />);
  await waitFor(() => expect(ru).toHaveValue("Сохранённая RU"));
  expect(kk).toHaveValue("Сохранённая KK");
  expect(createManualPersonnelOrderDraft).not.toHaveBeenCalled();
});

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

it("creates childcare leave with separate application/certificate and saved document forms", async () => {
  setup();
  vi.mocked(previewPersonnelOrderHeaderDuplicate).mockResolvedValue({ blocking: false } as any);
  vi.mocked(createManualPersonnelOrderDraft).mockResolvedValue({ order_id: 123 } as any);
  await selectType("LEAVE.CHILDCARE.GRANT");
  await selectEmployee();
  expect(screen.getByLabelText("ФИО сотрудника в родительном падеже (RU)")).toHaveValue("Ильясовой Ассель Адиловны");
  for (const [label, value] of Object.entries({
    "Номер приказа": "CHILD-TEST", "Дата приказа": "2026-07-28", "Дата начала": "2026-08-01", "Дата окончания": "2029-02-13",
    "Дата заявления": "2026-07-28", "Номер заявления": "APP-17", "Дата выдачи свидетельства о рождении": "2026-02-13", "Номер свидетельства о рождении": "9967264",
    "ФИО сотрудника в дательном падеже (RU)": "Ильясовой Ассель Адиловне",
  })) fireEvent.change(screen.getByLabelText(label), { target: { value } });
  expect(screen.getByLabelText("Дата окончания")).toHaveValue("2029-02-13");
  fireEvent.click(screen.getByRole("button", { name: "Создать приказ" }));
  await waitFor(() => expect(createManualPersonnelOrderDraft).toHaveBeenCalled());
  expect(vi.mocked(createManualPersonnelOrderDraft).mock.calls[0][0]).toMatchObject({ item_payload: {
    leave_start: "2026-08-01", leave_end: "2029-02-13",
    basis: { kind: "PERSONAL_APPLICATION", date: "2026-07-28", number: "APP-17", birth_certificate: { date: "2026-02-13", number: "9967264" } },
    document_forms_kk: { org_unit_document_genitive_kk: "Сәулелік диагностика бөлімшесінің" },
    document_forms_ru: { employee_full_name_genitive_ru: "Ильясовой Ассель Адиловны" },
  } });
});

it("prefers a saved RU genitive and preserves manual text across rerenders", async () => {
  setup();
  vi.mocked(getEmployee).mockResolvedValue({ ...employeeDetail, document_forms_ru: { employee_full_name_genitive_ru: "Сохранённая документная форма" } } as typeof employeeDetail);
  await selectType("LEAVE.CHILDCARE.GRANT");
  await selectEmployee();
  const field = screen.getByLabelText("ФИО сотрудника в родительном падеже (RU)");
  expect(field).toHaveValue("Сохранённая документная форма");
  fireEvent.change(field, { target: { value: "Ручная корректировка" } });
  fireEvent.change(screen.getByLabelText("Дата заявления"), { target: { value: "2026-07-29" } });
  fireEvent.change(screen.getByLabelText("Язык"), { target: { value: "ru" } });
  await waitFor(() => expect(screen.getByLabelText("Название приказа")).toHaveValue(unpaidTitles.title_ru));
  expect(field).toHaveValue("Ручная корректировка");
});

it("does not overwrite RU genitive typed while employee detail is pending", async () => {
  setup();
  let resolveDetail!: (value: typeof employeeDetail) => void;
  vi.mocked(getEmployee).mockReturnValue(new Promise(resolve => { resolveDetail = resolve; }));
  await selectType("LEAVE.CHILDCARE.GRANT");
  fireEvent.change(screen.getByLabelText("Сотрудник"), { target: { value: "Иль" } });
  fireEvent.click(await screen.findByRole("option", { name: employee.fio }));
  fireEvent.change(screen.getByLabelText("ФИО сотрудника в родительном падеже (RU)"), { target: { value: "Введено до ответа" } });
  resolveDetail(employeeDetail);
  await waitFor(() => expect(screen.getByLabelText("Подразделение")).toBeInTheDocument());
  expect(screen.getByLabelText("ФИО сотрудника в родительном падеже (RU)")).toHaveValue("Введено до ответа");
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
  expect(screen.getByLabelText("Подразделение")).toHaveValue("59");
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
  expect(screen.queryByText("В справочнике отсутствует казахское название выбранного подразделения.")).not.toBeInTheDocument();
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

it("uses the directory Kazakh name when its order-text form is absent and preserves a manual edit on rerender", async () => {
  setup();
  vi.mocked(getEmployee).mockResolvedValueOnce({
    ...employeeDetail,
    org_unit: { ...employee.org_unit, name_kk: "Сәулелік диагностика бөлімшесі", document_genitive_kk: null },
  });
  await selectUnpaid();
  await selectEmployee();
  const field = screen.getByLabelText("Подразделение в тексте приказа (KK)");
    expect(field).toHaveValue("Сәулелік диагностика бөлімшесінің");
  fireEvent.change(field, { target: { value: "Ручная форма" } });
  fireEvent.change(screen.getByLabelText("Язык"), { target: { value: "ru" } });
  expect(field).toHaveValue("Ручная форма");
});

it("replaces the order-text department form from the selected directory unit", async () => {
  setup();
  await selectUnpaid();
  await selectEmployee();
  const department = screen.getByLabelText("Подразделение");
  await waitFor(() => expect(screen.getByRole("option", { name: "Лучевая диагностика" })).toBeInTheDocument());
  fireEvent.change(department, { target: { value: "41" } });
  expect(screen.getByLabelText("Подразделение в тексте приказа (KK)")).toHaveValue("");
  expect(screen.getByText("В справочнике отсутствует казахское название выбранного подразделения.")).toBeInTheDocument();
  fireEvent.change(department, { target: { value: "59" } });
  expect(screen.getByLabelText("Подразделение в тексте приказа (KK)")).toHaveValue("Сәулелік диагностика бөлімшесінің");
  expect(screen.queryByText("В справочнике отсутствует казахское название выбранного подразделения.")).not.toBeInTheDocument();
});

it("keeps automatic employee-selected department text while the directory finishes loading", async () => {
  let resolveCatalog: ((items: Array<{ unit_id: number; name: string; group_id: number | null; name_kk?: string | null; document_genitive_kk?: string | null }>) => void) | undefined;
  vi.mocked(loadOrgUnitSelectOptions).mockImplementationOnce(() => new Promise((resolve) => { resolveCatalog = resolve; }));
  setup();
  await selectUnpaid();
  await selectEmployee();
  const field = screen.getByLabelText("Подразделение в тексте приказа (KK)");
  expect(field).toHaveValue("Сәулелік диагностика бөлімшесінің");
  resolveCatalog?.([{ unit_id: 59, name: "Лучевая диагностика", group_id: 2, name_kk: "Сәулелік диагностика бөлімшесі", document_genitive_kk: "Сәулелік диагностика бөлімшесінің" }]);
  await waitFor(() => expect(field).toHaveValue("Сәулелік диагностика бөлімшесінің"));
  fireEvent.change(field, { target: { value: "Ручная форма" } });
  fireEvent.change(screen.getByLabelText("Язык"), { target: { value: "ru" } });
  expect(field).toHaveValue("Ручная форма");
});

it("keeps a manual department-text edit when the dialog is closed and reopened", async () => {
  vi.mocked(getPersonnelOrderPublishedTemplateTitle).mockResolvedValue(unpaidTitles);
  vi.mocked(getEmployees).mockResolvedValue({ items: [employee], total: 1 });
  vi.mocked(getEmployee).mockResolvedValue(employeeDetail);
  vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue([{ unit_id: 59, name: "Лучевая диагностика", group_id: 2, document_genitive_kk: "Сәулелік диагностика бөлімшесінің" }]);
  const view = render(<PersonnelOrderCreateDialog open onClose={vi.fn()} onCreated={vi.fn()} />);
  await selectUnpaid();
  await selectEmployee();
  const field = screen.getByLabelText("Подразделение в тексте приказа (KK)");
  fireEvent.change(field, { target: { value: "Ручная форма" } });
  view.rerender(<PersonnelOrderCreateDialog open={false} onClose={vi.fn()} onCreated={vi.fn()} />);
  view.rerender(<PersonnelOrderCreateDialog open onClose={vi.fn()} onCreated={vi.fn()} />);
  expect(screen.getByLabelText("Подразделение в тексте приказа (KK)")).toHaveValue("Ручная форма");
});

it("identifies a missing Kazakh directory name next to the editable field", async () => {
  setup();
  vi.mocked(getEmployee).mockResolvedValueOnce({ ...employeeDetail, org_unit: { ...employee.org_unit, unit_id: 999 } });
  await selectUnpaid();
  await selectEmployee();
  expect(screen.getByText("В справочнике отсутствует казахское название выбранного подразделения.")).toBeInTheDocument();
  expect(screen.getByLabelText("Подразделение в тексте приказа (KK)")).toBeEnabled();
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
