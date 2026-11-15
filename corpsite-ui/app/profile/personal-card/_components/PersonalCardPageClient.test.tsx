import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonalCardPageClient from "./PersonalCardPageClient";

const cardSearchParams = new URLSearchParams();
const cardRouter = { push: vi.fn(), replace: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => cardRouter,
  useSearchParams: () => cardSearchParams,
}));
vi.mock("@/app/directory/personnel/_components/PprPersonPhoto", () => ({
  default: ({ fullName }: { fullName: string }) => <div data-testid="ppr-person-photo" aria-label={`Фото сотрудника ${fullName}`} />,
}));

const getMyPersonalCard = vi.fn();
const getMyOperationalAssignment = vi.fn();
const getMyContacts = vi.fn();

vi.mock("../_lib/selfPersonalCardApi.client", () => ({
  getMyPersonalCard: (...args: unknown[]) => getMyPersonalCard(...args),
  getMyOperationalAssignment: (...args: unknown[]) => getMyOperationalAssignment(...args),
  getMyContacts: (...args: unknown[]) => getMyContacts(...args),
}));
vi.mock("../_lib/selfPersonCardPdfOpen.client", () => ({
  downloadMyPersonalCardPdf: vi.fn(),
}));

afterEach(() => {
  cleanup();
  getMyPersonalCard.mockReset();
  getMyOperationalAssignment.mockReset();
  getMyContacts.mockReset();
});

const card = {
  materialization: { materialized: true, lifecycle_state: "READY", hr_relationship_context: "EMPLOYEE", envelope_version: 1, created_at: null, updated_at: null },
  general: { full_name: "Масимов Акрамжан Бакримжанович", last_name: "Масимов", first_name: "Акрамжан", middle_name: "Бакримжанович", birth_date: null, iin: null, created_at: "2026-01-01", updated_at: "2026-01-01" },
  sections: {
    "PPR-EDUCATION": { section_code: "PPR-EDUCATION", active: [{ record_id: 7, education_kind: "higher", institution_type: "university", institution_name: "КазНУ", specialty: "Медицина", qualification: "Врач", started_at: "2000-09-01", completed_at: "2006-06-01", diploma_number: "123", document_date: "2006-06-01", verification_status: "confirmed", lifecycle_status: "active" }], superseded: [], voided: [] },
    "PPR-TRAINING": { section_code: "PPR-TRAINING", active: [], superseded: [], voided: [] },
    "PPR-FAMILY": { section_code: "PPR-FAMILY", active: [], superseded: [], voided: [] },
    "PPR-EMPLOYMENT-BIOGRAPHY": { section_code: "PPR-EMPLOYMENT-BIOGRAPHY", active: [], superseded: [], voided: [] },
  },
  additional: { foreign_languages: [{ language: "Английский", proficiency: "C1" }], foreign_languages_none: false, awards: [{ name: "Грамота", issued_by: "Организация", awarded_at: "2024-01-01", document_number: "1" }], awards_none: false, academic_degrees: [], academic_degrees_none: true, academic_titles: [], academic_titles_none: true, qualification_categories: [], status_facts: [] },
};

function ready(assignedRate: number | null = null) {
  getMyPersonalCard.mockResolvedValue({ status: "READY", card });
  getMyOperationalAssignment.mockResolvedValue({ status: "READY", operational_assignment: {
    department_group_name: null,
    org_unit_name: "ОВЭиПД",
    position_name: "Руководитель",
    operational_status: "active",
    employment_rate: assignedRate,
    iin: null,
  } });
  getMyContacts.mockResolvedValue({ canonical: { mobile_phone: "+77001234567", email: null, registration_address: null, residence_address: null }, fallback: null });
}

describe("PersonalCardPageClient", () => {
  it("uses only ID-free self endpoints and shows saved PPR sections in read-only mode", async () => {
    ready();
    render(<PersonalCardPageClient />);

    const view = await screen.findByTestId("self-personal-card-ready");
    expect(getMyPersonalCard).toHaveBeenCalledWith({ signal: expect.any(AbortSignal) });
    expect(getMyOperationalAssignment).toHaveBeenCalledWith({ signal: expect.any(AbortSignal) });
    expect(getMyContacts).toHaveBeenCalledWith({ signal: expect.any(AbortSignal) });
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByTestId("ppr-person-photo")).toHaveAttribute("aria-label", `Фото сотрудника ${card.general.full_name}`);
    expect(screen.queryByTestId("ppr-card-back-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("ppr-card-edit-mode-button")).not.toBeInTheDocument();
    expect(within(view).getAllByText(card.general.full_name).length).toBeGreaterThan(0);
    expect(within(view).getByText("КазНУ")).toBeInTheDocument();
    expect(within(view).getByText("Медицина")).toBeInTheDocument();
    expect(within(view).getByText("Грамота")).toBeInTheDocument();
    expect(within(view).getByText("+77001234567")).toBeInTheDocument();
    expect(within(view).getByTestId("ppr-additional-languages-table")).toBeInTheDocument();
    expect(within(view).getByTestId("self-operational-assignment")).toHaveTextContent("ОВЭиПД");
    expect(within(view).queryByRole("button", { name: /редактировать|добавить|удалить/i })).not.toBeInTheDocument();
    expect(within(view).queryByText(/Кадровая связь|Кадровые приказы|Доступ/)).not.toBeInTheDocument();
  });

  it("keeps a genuinely absent employment rate empty", async () => {
    ready(null);
    render(<PersonalCardPageClient />);
    const assignment = within(await screen.findByTestId("self-operational-assignment"));
    expect(assignment.getByText("Ставка").parentElement).toHaveTextContent("—");
    expect(assignment.getByText("Ставка").parentElement).not.toHaveTextContent("1.00");
  });

  it("reports a contact load failure without treating it as empty data", async () => {
    ready();
    getMyContacts.mockRejectedValue(new Error("network"));
    render(<PersonalCardPageClient />);
    const view = await screen.findByTestId("self-personal-card-ready");
    expect(within(view).getByRole("alert")).toHaveTextContent("Контактные сведения не удалось загрузить");
    expect(within(view).queryByTestId("self-contacts")).not.toBeInTheDocument();
    expect(within(view).getAllByText(card.general.full_name).length).toBeGreaterThan(0);
  });

  it("explains a missing Person link without showing card actions", async () => {
    getMyPersonalCard.mockResolvedValue({ status: "PERSON_NOT_LINKED", card: null });
    render(<PersonalCardPageClient />);
    expect(await screen.findByTestId("self-personal-card-person-not-linked")).toHaveTextContent("Обратитесь в отдел кадров");
    expect(getMyOperationalAssignment).not.toHaveBeenCalled();
    expect(screen.queryByTestId("self-personal-card-download-pdf")).not.toBeInTheDocument();
  });
});
