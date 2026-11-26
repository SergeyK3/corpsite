import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import ElectronicHireApplicationDrawer from "./ElectronicHireApplicationDrawer";
import * as workflow from "../_lib/personnelApplicantWorkflow";

const listApplications = vi.fn();
const getElectronicHire = vi.fn();
const printElectronicHire = vi.fn();
const getElectronicHireOrderPreview = vi.fn();
const getElectronicHireOrderReadiness = vi.fn();
const getHireUnitApprovalMode = vi.fn();
const searchFormerCandidates = vi.fn();
const getPositionReview = vi.fn();
const getPersonnelApplication = vi.fn();
const getActiveIntakeLink = vi.fn();
const reissueIntakeLink = vi.fn();

vi.mock("@/lib/useOrgUnitScopeOptions", () => ({
  useOrgUnitScopeOptions: () => ({
    options: [{ unit_id: 1, group_id: 1, name: "Тестовое отделение" }],
    catalogOptions: [{ unit_id: 1, group_id: 1, name: "Тестовое отделение" }],
    loading: false,
    error: null,
  }),
}));
vi.mock("@/lib/usePersonnelOrderPositionOptions", () => ({
  usePersonnelOrderPositionOptions: () => ({ scopedOptions: [{ id: 1, label: "Тестовая должность" }], loading: false, error: null }),
}));
vi.mock("@/components/OrgScopeFilter", () => ({ default: () => <div /> }));
vi.mock("../_lib/electronicHireApi.client", () => ({
  listElectronicHireApplications: (...args: unknown[]) => listApplications(...args),
  getElectronicHire: (...args: unknown[]) => getElectronicHire(...args),
  printElectronicHire: (...args: unknown[]) => printElectronicHire(...args),
  getElectronicHireOrderPreview: (...args: unknown[]) => getElectronicHireOrderPreview(...args),
  getElectronicHireOrderReadiness: (...args: unknown[]) => getElectronicHireOrderReadiness(...args),
  getHireUnitApprovalMode: (...args: unknown[]) => getHireUnitApprovalMode(...args),
  searchFormerCandidates: (...args: unknown[]) => searchFormerCandidates(...args),
  getPositionReview: (...args: unknown[]) => getPositionReview(...args),
}));
vi.mock("../_lib/personnelApplicationsApi.client", () => ({
  getPersonnelApplication: (...args: unknown[]) => getPersonnelApplication(...args),
  getActiveIntakeLink: (...args: unknown[]) => getActiveIntakeLink(...args),
  reissueIntakeLink: (...args: unknown[]) => reissueIntakeLink(...args),
}));
vi.mock("./PersonnelApplicationIntakeOnBehalfDrawer", () => ({ default: () => null }));
vi.mock("./PersonnelApplicationIntakeReviewDrawer", () => ({
  default: ({ open, applicationId }: { open: boolean; applicationId: number | null }) =>
    open ? <div data-testid="opened-intake-review">Проверка анкеты #{applicationId}</div> : null,
}));

beforeEach(() => {
  process.env.NEXT_PUBLIC_PERSONNEL_INTAKE_PUBLIC_BASE_URL = "https://test.mmc.004.kz";
  listApplications.mockResolvedValue({ items: [{ application_id: 77, full_name: "Тестовый кандидат", status: "intake_pending" }] });
  getElectronicHire.mockResolvedValue({
    person_id: 900, iin: "900101000000", full_name: "Тестовый кандидат",
    application_received_at: "2026-11-24", planned_start_date: "2026-12-01",
    intended_org_unit_id: 1, intended_position_id: 1, intended_employment_rate: 1,
    position_resolution: "catalog", notification: null,
  });
  printElectronicHire.mockResolvedValue({ ru: "Заявление", kk: "Өтініш" });
  getElectronicHireOrderReadiness.mockResolvedValue({ application_id: 77, ready: false,
    identity_confirmed: false, intake_transferred: false, missing_card_fields: [],
    missing_steps: ["Проверьте анкету и подтвердите личность по документу."] });
  getHireUnitApprovalMode.mockResolvedValue({approval_mode: "paper"});
  getElectronicHireOrderPreview.mockResolvedValue({ application_id: 77, saved: false, template_version_id: 1,
    ru: {title: "О приёме", preamble: "", body: "Тестовый кандидат · должность · 1,0", basis: ""},
    kk: {title: "Жұмысқа қабылдау", preamble: "", body: "Тестовый кандидат · қызмет · 1,0", basis: ""} });
  searchFormerCandidates.mockResolvedValue({items: []});
  getPositionReview.mockResolvedValue({ request: null });
  getActiveIntakeLink.mockResolvedValue({ display_state: "active", intake_url_path: "/intake/test-token" });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.clearAllMocks();
  delete process.env.NEXT_PUBLIC_PERSONNEL_INTAKE_PUBLIC_BASE_URL;
});

it("copies an existing link twice, then opens the existing review after submission", async () => {
  let submitted = false;
  getPersonnelApplication.mockImplementation(async () => ({
    application_id: 77, person_id: 900,
    status: submitted ? "intake_submitted" : "intake_pending",
    intake_draft_status: submitted ? "submitted" : "editable",
    intake_link_status: submitted ? "submitted" : "issued",
    intake_submitted_at: submitted ? "2026-11-24T12:30:00Z" : null,
  }));
  const copy = vi.spyOn(workflow, "copyTextToClipboard").mockResolvedValue(true);

  render(<ElectronicHireApplicationDrawer open onClose={vi.fn()} />);
  fireEvent.click(await screen.findByRole("button", { name: /^№77 ·/ }));
  expect(await screen.findByTestId("electronic-hire-preliminary-name")).toHaveTextContent("Ранее сохранённое ФИО: Тестовый кандидат");
  expect(screen.getByRole("button", {name: "Сформировать черновик приказа"})).toBeDisabled();
  fireEvent.click(screen.getByRole("button", {name: "Предпросмотр приказа"}));
  expect(await screen.findByTestId("electronic-hire-order-preview")).toHaveTextContent("Тестовый кандидат · должность · 1,0");
  expect(getElectronicHireOrderPreview).toHaveBeenCalledWith(77);
  const copyButton = await screen.findByRole("button", { name: "Скопировать ссылку кандидата" });
  await waitFor(() => expect(copyButton).toBeEnabled());
  fireEvent.click(copyButton);
  fireEvent.click(copyButton);
  await waitFor(() => expect(copy).toHaveBeenCalledTimes(2));
  expect(copy).toHaveBeenNthCalledWith(1, "https://test.mmc.004.kz/intake/test-token");
  expect(copy).toHaveBeenNthCalledWith(2, "https://test.mmc.004.kz/intake/test-token");
  expect(reissueIntakeLink).not.toHaveBeenCalled();

  submitted = true;
  fireEvent.click(screen.getByRole("button", { name: "Обновить статус анкеты" }));
  expect(await screen.findByRole("button", { name: "Проверить анкету" })).toBeInTheDocument();
  expect(screen.getByTestId("electronic-hire-intake-status")).toHaveTextContent("Дата отправки:");
  fireEvent.click(screen.getByRole("button", { name: "Проверить анкету" }));
  expect(screen.getByTestId("opened-intake-review")).toHaveTextContent("#77");
  expect(getPersonnelApplication).toHaveBeenCalledWith(77);
});

it("prefills structured former names without splitting a compound surname", async () => {
  searchFormerCandidates.mockResolvedValue({items: [{
    person_id: 91, full_name: "Тестовая Қара Тегі Әлия", iin: "920203123456",
    last_name: "Тестовая Қара Тегі", first_name: "Әлия", middle_name: null,
  }]});
  render(<ElectronicHireApplicationDrawer open onClose={vi.fn()} />);
  fireEvent.change(screen.getByPlaceholderText("ФИО или ИИН"), {target: {value: "Тестовая"}});
  fireEvent.click(await screen.findByRole("button", {name: /Тестовая Қара Тегі Әлия/}));
  expect(screen.getByLabelText("Фамилия")).toHaveValue("Тестовая Қара Тегі");
  expect(screen.getByLabelText("Имя")).toHaveValue("Әлия");
  expect(screen.getByLabelText("Отчество (если есть)")).toHaveValue("");
});

it("shows a legacy former name intact and leaves all three fields for manual entry", async () => {
  searchFormerCandidates.mockResolvedValue({items: [{
    person_id: 92, full_name: "Тестовая Старая ФИО", iin: "920203123457",
    last_name: null, first_name: null, middle_name: null,
  }]});
  render(<ElectronicHireApplicationDrawer open onClose={vi.fn()} />);
  fireEvent.change(screen.getByPlaceholderText("ФИО или ИИН"), {target: {value: "Тестовая"}});
  fireEvent.click(await screen.findByRole("button", {name: /Тестовая Старая ФИО/}));
  expect(screen.getByText(/ФИО в прежней карточке: Тестовая Старая ФИО/)).toBeInTheDocument();
  expect(screen.getByLabelText("Фамилия")).toHaveValue("");
  expect(screen.getByLabelText("Имя")).toHaveValue("");
  expect(screen.getByLabelText("Отчество (если есть)")).toHaveValue("");
});
