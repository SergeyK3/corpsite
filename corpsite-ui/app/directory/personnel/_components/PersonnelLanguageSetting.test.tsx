import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { apiFetchJson } from "@/lib/api";
import { PersonnelSectionLanguageProvider, localizedPersonnelTitle } from "../_lib/personnelSectionLanguage";
import { personnelOrderTypeLabel } from "../_lib/personnelOrderLabels";
import PersonnelLanguageSetting from "./PersonnelLanguageSetting";
import PersonnelOrderTypeBadge from "./PersonnelOrderTypeBadge";
import PersonnelOrderCreateDialog from "./PersonnelOrderCreateDialog";
import { PersonnelOrdersTable } from "./PersonnelOrdersTable";
import type { PersonnelOrderListItem } from "../_lib/personnelOrdersApi.client";
import { loadOrgUnitSelectOptions } from "@/lib/orgUnitsSelect";

let pathname = "/directory/personnel/orders";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
vi.mock("@/lib/api", async () => ({ ...(await vi.importActual<object>("@/lib/api")), apiFetchJson: vi.fn() }));
vi.mock("../_lib/personnelOrdersApi.client", async () => ({ ...(await vi.importActual<object>("../_lib/personnelOrdersApi.client")), getPersonnelOrderPublishedVariants: vi.fn().mockResolvedValue({ items: [] }) }));
vi.mock("@/lib/orgUnitsSelect", () => ({ loadOrgUnitSelectOptions: vi.fn() }));
beforeEach(() => {
  pathname = "/directory/personnel/orders";
  vi.mocked(apiFetchJson).mockReset().mockResolvedValue({ language: "kk", can_edit: true });
  vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue([]);
});
afterEach(cleanup);
const view = () => render(<PersonnelSectionLanguageProvider><PersonnelLanguageSetting /><PersonnelOrderTypeBadge typeCode="HIRE" /></PersonnelSectionLanguageProvider>);

it("loads shared language, saves to API and updates display", async () => {
  view();
  const select = await screen.findByLabelText("Кадр бөлімінің тілі");
  await waitFor(() => expect(select).toBeEnabled());
  expect(screen.getByText("Жұмысқа қабылдау туралы")).toBeInTheDocument();
  vi.mocked(apiFetchJson).mockResolvedValueOnce({ language: "ru", can_edit: true });
  fireEvent.change(select, { target: { value: "ru" } });
  await waitFor(() => expect(screen.getByLabelText("Язык кадрового раздела")).toHaveValue("ru"));
  expect(apiFetchJson).toHaveBeenLastCalledWith("/personnel/settings", { method: "PUT", body: { language: "ru" } });
  expect(screen.getByText("О приёме на работу")).toBeInTheDocument();
});

it("reads again on another page opening and makes the setting read-only for other roles", async () => {
  vi.mocked(apiFetchJson).mockResolvedValue({ language: "ru", can_edit: false });
  const result = view();
  await waitFor(() => expect(screen.getByLabelText("Язык кадрового раздела")).toHaveValue("ru"));
  expect(screen.getByLabelText("Язык кадрового раздела")).toBeDisabled();
  vi.mocked(apiFetchJson).mockResolvedValueOnce({ language: "kk", can_edit: false });
  pathname = "/directory/personnel/journal";
  result.rerender(<PersonnelSectionLanguageProvider><PersonnelLanguageSetting /></PersonnelSectionLanguageProvider>);
  await waitFor(() => expect(screen.getByLabelText("Кадр бөлімінің тілі")).toHaveValue("kk"));
  expect(apiFetchJson).toHaveBeenCalledTimes(2);
});

it("does not change document language when shared language changes", async () => {
  render(<PersonnelSectionLanguageProvider><PersonnelLanguageSetting /><PersonnelOrderCreateDialog open onClose={() => {}} onCreated={() => {}} /></PersonnelSectionLanguageProvider>);
  const select = screen.getByLabelText("Кадр бөлімінің тілі");
  await waitFor(() => expect(select).toBeEnabled());
  fireEvent.change(screen.getByLabelText("Язык"), { target: { value: "ru" } });
  vi.mocked(apiFetchJson).mockResolvedValueOnce({ language: "ru", can_edit: true });
  fireEvent.change(select, { target: { value: "ru" } });
  await waitFor(() => expect(screen.getByLabelText("Язык кадрового раздела")).toHaveValue("ru"));
  expect(screen.getByLabelText("Язык")).toHaveValue("ru");
  vi.mocked(apiFetchJson).mockResolvedValueOnce({ language: "kk", can_edit: true });
  fireEvent.change(screen.getByLabelText("Язык кадрового раздела"), { target: { value: "kk" } });
  await waitFor(() => expect(screen.getByLabelText("Кадр бөлімінің тілі")).toHaveValue("kk"));
  expect(screen.getByLabelText("Язык")).toHaveValue("ru");
  await waitFor(() => expect(screen.getByRole("button", { name: "Тип кадрового приказа" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Тип кадрового приказа" }));
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "Жұмысқа қабылдау" } });
  expect(screen.getByRole("menuitem", { name: "Жұмысқа қабылдау туралы" })).toBeInTheDocument();
});

it("uses existing approved names and falls back to the available translation", () => {
  expect(personnelOrderTypeLabel("LEAVE.CHILDCARE.GRANT", "ru")).toBe("О неоплачиваемом отпуске по уходу за ребенком");
  expect(personnelOrderTypeLabel("RETURN_FROM_CHILDCARE_LEAVE", "kk")).toBe("Бала күтіміне байланысты демалыстан жұмысқа шығу туралы");
  expect(localizedPersonnelTitle({ title_ru: "Только RU", title_kk: " " }, "kk")).toBe("Только RU");
  expect(localizedPersonnelTitle({ title_kk: "Тек KK" }, "ru")).toBe("Тек KK");
});

it("keeps the archive source title verbatim while changing the type label", async () => {
  const row = { order_id: 1, order_type_code: "HIRE", source_title: "Архив: исходное название", employee_ids: [], employee_names: [] } as unknown as PersonnelOrderListItem;
  const original = JSON.stringify(row);
  render(<PersonnelSectionLanguageProvider><PersonnelLanguageSetting /><PersonnelOrdersTable items={[row]} /></PersonnelSectionLanguageProvider>);
  const select = screen.getByLabelText("Кадр бөлімінің тілі");
  await waitFor(() => expect(select).toBeEnabled());
  expect(screen.getByText("Архив: исходное название")).toBeInTheDocument();
  vi.mocked(apiFetchJson).mockResolvedValueOnce({ language: "ru", can_edit: true });
  fireEvent.change(select, { target: { value: "ru" } });
  await screen.findByText("О приёме на работу");
  expect(screen.getByText("Архив: исходное название")).toBeInTheDocument();
  expect(JSON.stringify(row)).toBe(original);
});

it("retains the saved language if saving fails", async () => {
  view();
  const select = screen.getByLabelText("Кадр бөлімінің тілі");
  await waitFor(() => expect(select).toBeEnabled());
  vi.mocked(apiFetchJson).mockRejectedValueOnce(new Error("failed"));
  fireEvent.change(select, { target: { value: "ru" } });
  await screen.findByRole("alert");
  expect(select).toHaveValue("kk");
  expect(screen.getByText("Жұмысқа қабылдау туралы")).toBeInTheDocument();
});

it("explains missing setup and reloads permissions after retry without bypassing disabled", async () => {
  vi.mocked(apiFetchJson).mockRejectedValueOnce({ details: { detail: { code: "PERSONNEL_SETTINGS_SCHEMA_REQUIRED" } } });
  view();
  await screen.findByRole("alert");
  expect(screen.getByRole("alert")).toHaveTextContent("Әкімшіге хабарласыңыз");
  expect(screen.getByLabelText("Кадр бөлімінің тілі")).toBeDisabled();
  vi.mocked(apiFetchJson).mockResolvedValueOnce({ language: "kk", can_edit: true });
  fireEvent.click(screen.getByRole("button", { name: "Қайталау" }));
  await waitFor(() => expect(screen.getByLabelText("Кадр бөлімінің тілі")).toBeEnabled());
  expect(apiFetchJson).toHaveBeenCalledTimes(2);
});
