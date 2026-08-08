import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CurrentUserProvider } from "@/lib/currentUser";
import type { EmployeeDetails } from "../../employees/_lib/types";
import PprPersonalCardPageClient from "./PprPersonalCardPageClient";

const getPprByPersonId = vi.fn();
const getEmployee = vi.fn();
const getEmployees = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("../_lib/pprQueryApi.client", () => ({
  getPprByPersonId: (...args: unknown[]) => getPprByPersonId(...args),
  getPprByEmployeeId: vi.fn(),
}));

vi.mock("../_lib/personnelApplicationsApi.client", () => ({
  getPersonApplicationsHistory: vi.fn(async () => ({ items: [] })),
}));

vi.mock("../../employees/_lib/api.client", () => ({
  getEmployee: (...args: unknown[]) => getEmployee(...args),
  getEmployees: (...args: unknown[]) => getEmployees(...args),
  getPositions: vi.fn(async () => ({ items: [{ id: 29, name: "Менеджер" }] })),
  correctEmployee: vi.fn(),
  mapApiErrorToMessage: (error: unknown) => (error instanceof Error ? error.message : "Ошибка"),
}));

vi.mock("../../org-units/_lib/api.client", () => ({
  getOrgUnitsTree: vi.fn(async () => ({
    items: [{ unit_id: 73, name: "Отдел кадров", group_id: 1, children: [] }],
  })),
}));

vi.mock("@/lib/orgScope", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/orgScope")>();
  return {
    ...actual,
    fetchDepartmentGroups: vi.fn(async () => [{ group_id: 1, group_name: "Администрация" }]),
  };
});

vi.mock("../_lib/importApi.client", () => ({
  getNormalizedRecord: vi.fn(),
  listNormalizedRecords: vi.fn(async () => ({ items: [] })),
  mapImportApiError: (_error: unknown, fallback: string) => fallback,
}));

vi.mock("./EmployeeAssignmentCorrectionDrawer", () => ({ default: () => null }));
vi.mock("./ImportNormalizedRecordDrawer", () => ({ default: () => null }));
vi.mock("./EmployeeCardOrdersSection", () => ({ default: () => null }));
vi.mock("./EmployeeOnboardingSection", () => ({ default: () => null }));
vi.mock("./PprCardGeneralSection", () => ({ default: () => null }));
vi.mock("./PprCardEducationSection", () => ({ default: () => null }));
vi.mock("./PprCardTrainingSection", () => ({ default: () => null }));
vi.mock("./PprCardFamilySection", () => ({ default: () => null }));
vi.mock("./PprCardMilitarySection", () => ({ default: () => null }));
vi.mock("./PprCardEmploymentBiographySection", () => ({ default: () => null }));
vi.mock("./PprCardAdditionalSection", () => ({ default: () => null }));
vi.mock("./PprCardEventHistorySection", () => ({ default: () => null }));
vi.mock("./PprCardIntendedEmploymentSection", () => ({ default: () => null }));
vi.mock("./PprCardApplicationsSection", () => ({ default: () => null }));

const employee: EmployeeDetails = {
  id: "16",
  person_id: 105,
  active_assignment_id: 107,
  fio: "Өсерова Айсара Асанқызы",
  department: { id: 73, name: "Отдел кадров" },
  position: { id: 86, name: "Руководитель отдела кадров" },
  org_unit: {
    unit_id: 73,
    name: "Отдел кадров",
    code: "HR",
    parent_unit_id: null,
    is_active: true,
  },
  rate: 1,
  status: "active",
  date_from: "2025-01-01",
  date_to: null,
};

function personCardResponse() {
  return {
    identity: {
      requested_person_id: 105,
      requested_employee_id: null,
      resolved_person_id: 105,
      merge_redirected: false,
      merge_chain: [105],
      employee_context_id: null,
      person_status: "active",
      match_key: "person:105",
      iin: null,
    },
    materialization: {
      materialized: true,
      lifecycle_state: "ACTIVE",
      hr_relationship_context: "EMPLOYED",
      envelope_version: 1,
      created_at: null,
      updated_at: null,
    },
    general: {
      full_name: "Өсерова Айсара Асанқызы",
      last_name: "Өсерова",
      first_name: "Айсара",
      middle_name: "Асанқызы",
      birth_date: null,
      iin: null,
      created_at: "",
      updated_at: "",
    },
    sections: {},
    events: null,
    intended_employment: null,
    additional: {
      foreign_languages: [],
      foreign_languages_none: true,
      awards: [],
      awards_none: true,
      academic_degrees: [],
      academic_degrees_none: true,
      academic_titles: [],
      academic_titles_none: true,
    },
    metadata: {
      read_mode: "composite",
      source: "ppr",
      generated_at: "",
      warnings: [],
      transitional: false,
      merge_redirected: false,
      source_person_id: 105,
      requested_input_kind: "person",
      requested_input_id: 105,
    },
  };
}

describe("person-card current assignment integration", () => {
  beforeEach(() => {
    getPprByPersonId.mockResolvedValue(personCardResponse());
    getEmployees.mockResolvedValue({ items: [employee], total: 1 });
    getEmployee.mockResolvedValue(employee);
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders current assignment and its action on person 105 for the exact capability", async () => {
    render(
      <CurrentUserProvider value={{ user_id: 8, has_hr_enrollment_manager: true }}>
        <PprPersonalCardPageClient personId="105" />
      </CurrentUserProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Текущее назначение" })).toBeInTheDocument();
    await waitFor(() => expect(getEmployee).toHaveBeenCalledWith("16"));
    expect(getEmployees).toHaveBeenCalledWith(
      expect.objectContaining({ status: "all", q: "Өсерова Айсара Асанқызы" }),
    );
    expect(screen.getByText("Отдел кадров")).toBeInTheDocument();
    expect(screen.getByText("Руководитель отдела кадров")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Изменить назначение" })).toBeInTheDocument();
    expect(getPprByPersonId).toHaveBeenCalledWith(
      "105",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("keeps the action hidden on the same person route without the capability", async () => {
    render(
      <CurrentUserProvider value={{ user_id: 34, has_hr_enrollment_manager: false }}>
        <PprPersonalCardPageClient personId="105" />
      </CurrentUserProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Текущее назначение" })).toBeInTheDocument();
    await waitFor(() => expect(getEmployee).toHaveBeenCalledWith("16"));
    expect(screen.queryByRole("button", { name: "Изменить назначение" })).not.toBeInTheDocument();
  });
});
