import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PprPersonalCardPageClient from "./PprPersonalCardPageClient";
import {
  PPR_HR_RELATIONSHIP_CANDIDATE,
  PPR_SECTION_CODE_EDUCATION,
  PPR_SECTION_CODE_EMPLOYMENT_BIOGRAPHY,
  PPR_SECTION_CODE_FAMILY,
  PPR_SECTION_CODE_MILITARY,
  PPR_SECTION_CODE_TRAINING,
  PPR_MILITARY_RECORD_KIND_REGISTRATION,
  type PprCompositeReadResponse,
} from "../_lib/pprQueryTypes";
import { PERSONAL_CARD_TITLE } from "@/lib/personnelCardTerminology";
import { toApiError } from "@/lib/api";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const pushMock = vi.fn();
let currentCardSearchParams = new URLSearchParams("");
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn() }),
  usePathname: () => "/directory/personnel/employees/42/card",
  useSearchParams: () => currentCardSearchParams,
}));

const getPprByEmployeeIdMock = vi.fn();
const getPprByPersonIdMock = vi.fn();
vi.mock("../_lib/pprQueryApi.client", () => ({
  getPprByEmployeeId: (...args: unknown[]) => getPprByEmployeeIdMock(...args),
  getPprByPersonId: (...args: unknown[]) => getPprByPersonIdMock(...args),
}));

const getEmployeeImportCard2OptionalMock = vi.fn();
vi.mock("../_lib/importApi.client", () => ({
  getEmployeeImportCard2Optional: (...args: unknown[]) => getEmployeeImportCard2OptionalMock(...args),
  getEmployeeImportCard2: vi.fn(),
}));

vi.mock("./EmployeeOperationalAssignmentSection", () => ({
  default: () => <div data-testid="assignment-section">Трудовая деятельность</div>,
}));

vi.mock("./EmployeeCardOrdersSection", () => ({
  default: () => <div data-testid="orders-section">Кадровые приказы</div>,
}));

vi.mock("./PprCardApplicationsSection", () => ({
  default: ({ personId }: { personId: number }) => (
    <div data-testid="applications-section">Кадровые обращения #{personId}</div>
  ),
}));

function buildMaterializedPpr(overrides?: Partial<PprCompositeReadResponse>): PprCompositeReadResponse {
  return {
    identity: {
      requested_person_id: null,
      requested_employee_id: 42,
      resolved_person_id: 100,
      merge_redirected: false,
      merge_chain: [100],
      employee_context_id: 42,
      person_status: "active",
      match_key: "iin:123",
      iin: "123456789012",
    },
    materialization: {
      materialized: true,
      lifecycle_state: "ACTIVE",
      hr_relationship_context: "EMPLOYED",
      envelope_version: 1,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-02-01T00:00:00Z",
    },
    general: {
      full_name: "Иванов Иван Иванович",
      last_name: "Иванов",
      first_name: "Иван",
      middle_name: "Иванович",
      birth_date: "1990-05-15",
      iin: "123456789012",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-02-01T00:00:00Z",
    },
    sections: {
      [PPR_SECTION_CODE_EDUCATION]: {
        section_code: PPR_SECTION_CODE_EDUCATION,
        active: [
          {
            record_id: 1,
            education_kind: "Высшее",
            institution_type: null,
            institution_name: "КазНМУ",
            specialty: "Медицина",
            qualification: "Врач",
            started_at: "2008-09-01",
            completed_at: "2014-06-30",
            diploma_number: null,
            document_date: null,
            verification_status: "verified",
            lifecycle_status: "active",
          },
        ],
        superseded: [
          {
            record_id: 2,
            education_kind: "Среднее",
            institution_type: null,
            institution_name: "Школа №1",
            specialty: null,
            qualification: null,
            started_at: "1996-09-01",
            completed_at: "2007-05-25",
            diploma_number: null,
            document_date: null,
            verification_status: "verified",
            lifecycle_status: "superseded",
          },
        ],
        voided: [
          {
            record_id: 3,
            education_kind: "Курсы",
            institution_type: null,
            institution_name: "Аннулированный колледж",
            specialty: null,
            qualification: null,
            started_at: "2010-01-01",
            completed_at: "2010-06-01",
            diploma_number: null,
            document_date: null,
            verification_status: "verified",
            lifecycle_status: "voided",
          },
        ],
      },
      [PPR_SECTION_CODE_TRAINING]: {
        section_code: PPR_SECTION_CODE_TRAINING,
        active: [
          {
            record_id: 10,
            training_kind: "Курс",
            title: "Первая помощь",
            organization_name: "Учебный центр",
            hours: 40,
            started_at: "2023-01-01",
            completed_at: "2023-01-15",
            certificate_number: null,
            document_date: null,
            verification_status: "verified",
            lifecycle_status: "active",
          },
        ],
        superseded: [],
        voided: [],
      },
      [PPR_SECTION_CODE_FAMILY]: {
        section_code: PPR_SECTION_CODE_FAMILY,
        active: [
          {
            record_id: 20,
            relationship_type: "spouse",
            relationship_label: "Супруг(а)",
            full_name: "Иванова Мария Петровна",
            birth_date: "1988-04-12",
            birth_place: "г. Алматы",
            organization_name: "ТОО «Пример»",
            residence_address: null,
            notes: null,
            verification_status: "verified",
            lifecycle_status: "active",
          },
        ],
        superseded: [
          {
            record_id: 21,
            relationship_type: "mother",
            relationship_label: "Мать",
            full_name: "Иванова Анна Семёновна (устар.)",
            birth_date: "1960-01-01",
            birth_place: null,
            organization_name: null,
            residence_address: null,
            notes: null,
            verification_status: "verified",
            lifecycle_status: "superseded",
          },
        ],
        voided: [
          {
            record_id: 22,
            relationship_type: "son",
            relationship_label: "Сын",
            full_name: "Иванов Пётр Иванович",
            birth_date: "2010-05-20",
            birth_place: null,
            organization_name: null,
            residence_address: null,
            notes: null,
            verification_status: "verified",
            lifecycle_status: "voided",
          },
        ],
      },
      [PPR_SECTION_CODE_MILITARY]: {
        section_code: PPR_SECTION_CODE_MILITARY,
        active: [
          {
            record_id: 301,
            record_kind: PPR_MILITARY_RECORD_KIND_REGISTRATION,
            obligation_status: "liable",
            registration_category: "II",
            military_rank: "рядовой",
            military_specialty_code: "123456",
            personnel_composition: "soldiers",
            fitness_category: "А",
            registration_status: "registered",
            commissariat_name: "Алмалинский РВК",
            registered_at: "2015-05-01",
            deregistered_at: null,
            notes: null,
            source_type: "entered",
            provenance: null,
            metadata: null,
            employee_context_id: null,
            verification_status: "verified",
            lifecycle_status: "active",
            created_at: "2024-01-01T00:00:00Z",
            updated_at: "2024-03-01T00:00:00Z",
          },
        ],
        superseded: [],
        voided: [],
      },
      [PPR_SECTION_CODE_EMPLOYMENT_BIOGRAPHY]: {
        section_code: PPR_SECTION_CODE_EMPLOYMENT_BIOGRAPHY,
        active: [
          {
            record_id: 101,
            record_kind: "episode",
            employer_name: "ТОО Альфа",
            department_name: "Производство",
            position_title: "Инженер",
            employment_type: null,
            started_at: "2020-01-01",
            ended_at: "2022-12-31",
            termination_reason: null,
            document_reference: null,
            source_system: "manual",
            source_id: null,
            provenance: null,
            notes: null,
            employee_context_id: null,
            verification_status: "verified",
            lifecycle_status: "active",
            created_at: "2024-01-01T00:00:00Z",
            updated_at: "2024-03-01T00:00:00Z",
          },
          {
            record_id: 100,
            record_kind: "narrative_summary",
            employer_name: null,
            department_name: null,
            position_title: null,
            employment_type: null,
            started_at: null,
            ended_at: null,
            termination_reason: null,
            document_reference: null,
            source_system: "manual",
            source_id: null,
            provenance: null,
            notes: "Сводный стаж до поступления",
            employee_context_id: null,
            verification_status: "verified",
            lifecycle_status: "active",
            created_at: "2024-01-01T00:00:00Z",
            updated_at: "2024-02-01T00:00:00Z",
          },
        ],
        superseded: [
          {
            record_id: 99,
            record_kind: "episode",
            employer_name: "ТОО Бета (устар.)",
            department_name: null,
            position_title: "Стажёр",
            employment_type: null,
            started_at: "2015-01-01",
            ended_at: "2017-12-31",
            termination_reason: null,
            document_reference: null,
            source_system: "manual",
            source_id: null,
            provenance: null,
            notes: null,
            employee_context_id: null,
            verification_status: "verified",
            lifecycle_status: "superseded",
            created_at: "2024-01-01T00:00:00Z",
            updated_at: "2024-01-15T00:00:00Z",
          },
        ],
        voided: [],
      },
    },
    events: {
      recent: [
        {
          event_id: 1,
          event_type: "PPR_CREATED",
          category: "lifecycle",
          record_table_name: "ppr_envelope",
          record_id: 1,
          occurred_at: "2024-01-01T12:00:00Z",
          section_code: null,
          domain_code: "PPR",
        },
      ],
      returned_count: 1,
      limit: 20,
    },
    intended_employment: null,
    metadata: {
      read_mode: "composite",
      source: "ppr",
      generated_at: "2024-03-01T00:00:00Z",
      warnings: [],
      transitional: false,
      merge_redirected: false,
      source_person_id: 100,
      requested_input_kind: "employee",
      requested_input_id: 42,
    },
    ...overrides,
  };
}

beforeEach(() => {
  getPprByEmployeeIdMock.mockReset();
  getPprByPersonIdMock.mockReset();
  getEmployeeImportCard2OptionalMock.mockReset();
  pushMock.mockReset();
  currentCardSearchParams = new URLSearchParams("");
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PprPersonalCardPageClient", () => {
  it("loads card with a single PPR API request", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: PERSONAL_CARD_TITLE })).toBeInTheDocument();
    });

    expect(getPprByEmployeeIdMock).toHaveBeenCalledTimes(1);
    expect(getPprByEmployeeIdMock).toHaveBeenCalledWith("42", expect.objectContaining({ signal: expect.any(AbortSignal) }));
    expect(getEmployeeImportCard2OptionalMock).not.toHaveBeenCalled();
  });

  it("renders materialized card with general, education, training and event history", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getAllByText("Иванов Иван Иванович").length).toBeGreaterThan(0);
    });

    expect(screen.getByText(/только для просмотра/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /редактир/i })).not.toBeInTheDocument();
    expect(screen.getByText("КазНМУ")).toBeInTheDocument();
    expect(screen.getByText("Первая помощь")).toBeInTheDocument();
    expect(screen.getByText("Иванова Мария Петровна")).toBeInTheDocument();
    expect(screen.getByText("Личная карточка сформирована")).toBeInTheDocument();
    expect(screen.getByTestId("assignment-section")).toBeInTheDocument();
    expect(screen.getByTestId("orders-section")).toBeInTheDocument();
    expect(screen.queryByText("NOT_MATERIALIZED")).not.toBeInTheDocument();
    expect(screen.queryByText("Кадровая карточка-досье")).not.toBeInTheDocument();
    expect(screen.queryByText("Текущее назначение")).not.toBeInTheDocument();
    expect(screen.queryByText("Доступ")).not.toBeInTheDocument();
    expect(screen.queryByText("История кадровых событий")).not.toBeInTheDocument();
  });

  it("uses PPR tab navigation labels", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByRole("navigation", { name: /Разделы Личная карточка/ })).toBeInTheDocument();
    });

    const nav = screen.getByRole("navigation", { name: /Разделы Личная карточка/ });
    expect(within(nav).getByRole("link", { name: "Образование" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Обучение и повышение квалификации" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Родственники" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Воинский учёт" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Трудовая биография" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Трудовая деятельность" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "История изменений" })).toBeInTheDocument();
  });

  it("shows back navigation to personnel list", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Назад к персоналу" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Назад к персоналу" }));
    expect(pushMock).toHaveBeenCalledWith("/directory/staff");
  });

  it("returns to applicants journal when return_to is present", async () => {
    currentCardSearchParams = new URLSearchParams(
      "return_to=%2Fdirectory%2Fpersonnel%2Fapplicants%3Fq%3Dpetrov%26application_id%3D10",
    );
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Назад к претендентам" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Назад к претендентам" }));
    expect(pushMock).toHaveBeenCalledWith("/directory/personnel/applicants?q=petrov&application_id=10");
  });

  it("shows NOT_MATERIALIZED as informational banner", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(
      buildMaterializedPpr({
        materialization: {
          materialized: false,
          lifecycle_state: "NOT_MATERIALIZED",
          hr_relationship_context: "EMPLOYED",
          envelope_version: null,
          created_at: null,
          updated_at: null,
        },
        sections: {
          [PPR_SECTION_CODE_EMPLOYMENT_BIOGRAPHY]: {
            section_code: PPR_SECTION_CODE_EMPLOYMENT_BIOGRAPHY,
            active: [],
            superseded: [],
            voided: [],
          },
        },
        events: null,
      }),
    );

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(
        screen.getByText(/Формирование служебной части личной карточки ещё не завершено/),
      ).toBeInTheDocument();
      expect(screen.getByTestId("emp-bio-empty")).toBeInTheDocument();
    });
    expect(screen.getByText("Не сформирована полностью")).toBeInTheDocument();
    expect(screen.queryByText(/ошибк/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId("emp-bio-create-btn")).not.toBeInTheDocument();
  });

  it("hides employment biography mutations for read-only card access", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" canEditPprSections={false} />);

    await waitFor(() => {
      expect(screen.getByTestId("emp-bio-record-101")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("emp-bio-create-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("emp-bio-supersede-btn-101")).not.toBeInTheDocument();
    expect(screen.queryByTestId("emp-bio-void-btn-101")).not.toBeInTheDocument();
  });

  it("shows employment biography mutations for materialized editable card", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" canEditPprSections />);

    await waitFor(() => {
      expect(screen.getByTestId("emp-bio-create-btn")).toBeInTheDocument();
      expect(screen.getByTestId("emp-bio-supersede-btn-101")).toBeInTheDocument();
      expect(screen.getByTestId("emp-bio-void-btn-101")).toBeInTheDocument();
    });
  });

  it("renders employment biography records in backend order", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByTestId("emp-bio-record-101")).toBeInTheDocument();
    });

    const cards = screen.getAllByTestId(/emp-bio-record-/);
    expect(cards[0]).toHaveTextContent("ТОО Альфа");
    expect(cards[1]).toHaveTextContent("Сводная запись о стаже");
    expect(screen.queryByText("ТОО Бета (устар.)")).not.toBeInTheDocument();
  });

  it("shows employment biography empty state", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(
      buildMaterializedPpr({
        sections: {
          [PPR_SECTION_CODE_EDUCATION]: {
            section_code: PPR_SECTION_CODE_EDUCATION,
            active: [],
            superseded: [],
            voided: [],
          },
          [PPR_SECTION_CODE_TRAINING]: {
            section_code: PPR_SECTION_CODE_TRAINING,
            active: [],
            superseded: [],
            voided: [],
          },
          [PPR_SECTION_CODE_FAMILY]: {
            section_code: PPR_SECTION_CODE_FAMILY,
            active: [],
            superseded: [],
            voided: [],
          },
          [PPR_SECTION_CODE_EMPLOYMENT_BIOGRAPHY]: {
            section_code: PPR_SECTION_CODE_EMPLOYMENT_BIOGRAPHY,
            active: [],
            superseded: [],
            voided: [],
          },
        },
      }),
    );

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByTestId("emp-bio-empty")).toBeInTheDocument();
      expect(screen.getByText("Записи трудовой биографии отсутствуют.")).toBeInTheDocument();
    });
  });

  it("shows employment biography on person card with editable actions", async () => {
    getPprByPersonIdMock.mockResolvedValue(
      buildMaterializedPpr({
        identity: {
          requested_person_id: 501,
          requested_employee_id: null,
          resolved_person_id: 501,
          merge_redirected: false,
          merge_chain: [501],
          employee_context_id: null,
          person_status: "active",
          match_key: "iin:seed",
          iin: "900101350123",
        },
        materialization: {
          materialized: true,
          lifecycle_state: "CREATED",
          hr_relationship_context: PPR_HR_RELATIONSHIP_CANDIDATE,
          envelope_version: 1,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-02-01T00:00:00Z",
        },
        sections: {
          [PPR_SECTION_CODE_EMPLOYMENT_BIOGRAPHY]: {
            section_code: PPR_SECTION_CODE_EMPLOYMENT_BIOGRAPHY,
            active: [],
            superseded: [],
            voided: [],
          },
        },
      }),
    );

    render(<PprPersonalCardPageClient personId="501" />);

    await waitFor(() => {
      expect(screen.getByTestId("emp-bio-empty")).toBeInTheDocument();
      expect(screen.getByTestId("emp-bio-create-btn")).toBeInTheDocument();
    });
  });

  it("collapses superseded and voided education groups by default", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByText("КазНМУ")).toBeInTheDocument();
    });

    const educationSection = document.getElementById("education");
    expect(educationSection).not.toBeNull();
    expect(
      within(educationSection as HTMLElement).getByRole("button", { name: /Заменённые записи \(1\)/ }),
    ).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Школа №1")).not.toBeInTheDocument();
    expect(screen.queryByText("Аннулированный колледж")).not.toBeInTheDocument();
  });

  it("expands superseded education records on click", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByText("КазНМУ")).toBeInTheDocument();
    });

    const educationSection = document.getElementById("education");
    fireEvent.click(
      within(educationSection as HTMLElement).getByRole("button", { name: /Заменённые записи \(1\)/ }),
    );
    expect(screen.getByText("Школа №1")).toBeInTheDocument();
  });

  it("shows merge redirect banner for survivor record", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(
      buildMaterializedPpr({
        identity: {
          requested_person_id: null,
          requested_employee_id: 42,
          resolved_person_id: 200,
          merge_redirected: true,
          merge_chain: [100, 200],
          employee_context_id: 42,
          person_status: "active",
          match_key: "iin:123",
          iin: "123456789012",
        },
        metadata: {
          read_mode: "composite",
          source: "ppr",
          generated_at: "2024-03-01T00:00:00Z",
          warnings: [],
          transitional: false,
          merge_redirected: true,
          source_person_id: 200,
          requested_input_kind: "employee",
          requested_input_id: 42,
        },
      }),
    );

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(
        screen.getByText(/Отображаются сведения канонической записи после объединения/),
      ).toBeInTheDocument();
    });
  });

  it("shows 403 access denied message", async () => {
    getPprByEmployeeIdMock.mockRejectedValue(toApiError(403, { message: "Forbidden" }));

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(
        screen.getByText("У вас нет доступа к личной карточке этого сотрудника."),
      ).toBeInTheDocument();
    });
  });

  it("shows 404 not found message", async () => {
    getPprByEmployeeIdMock.mockRejectedValue(toApiError(404, { message: "Not found" }));

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByText("Сотрудник или личная карточка не найдены.")).toBeInTheDocument();
    });
  });

  it("shows 409 identity conflict message", async () => {
    getPprByEmployeeIdMock.mockRejectedValue(toApiError(409, { message: "Conflict" }));

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(
        screen.getByText(/Не удалось определить кадровую запись сотрудника/),
      ).toBeInTheDocument();
    });
  });

  it("offers network retry and reloads on click", async () => {
    getPprByEmployeeIdMock
      .mockRejectedValueOnce(new TypeError("fetch failed"))
      .mockResolvedValueOnce(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Повторить" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));

    await waitFor(() => {
      expect(getPprByEmployeeIdMock).toHaveBeenCalledTimes(2);
      expect(screen.getByText("КазНМУ")).toBeInTheDocument();
    });
  });

  it("exposes accessible section navigation labels", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByRole("navigation", { name: /Разделы Личная карточка/ })).toBeInTheDocument();
    });

    const nav = screen.getByRole("navigation", { name: /Разделы Личная карточка/ });
    expect(within(nav).getByRole("link", { name: "Общие сведения" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Образование" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "История изменений" })).toBeInTheDocument();
  });

  it("collapses superseded and voided family groups by default", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByText("Иванова Мария Петровна")).toBeInTheDocument();
    });

    const familySection = document.getElementById("family");
    expect(familySection).not.toBeNull();
    expect(
      within(familySection as HTMLElement).getByRole("button", { name: /Заменённые записи \(1\)/ }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Иванова Анна Семёновна (устар.)")).not.toBeInTheDocument();
    expect(screen.queryByText("Иванов Пётр Иванович")).not.toBeInTheDocument();
  });

  it("shows family empty state when section has no records", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(
      buildMaterializedPpr({
        sections: {
          [PPR_SECTION_CODE_EDUCATION]: {
            section_code: PPR_SECTION_CODE_EDUCATION,
            active: [],
            superseded: [],
            voided: [],
          },
          [PPR_SECTION_CODE_TRAINING]: {
            section_code: PPR_SECTION_CODE_TRAINING,
            active: [],
            superseded: [],
            voided: [],
          },
          [PPR_SECTION_CODE_FAMILY]: {
            section_code: PPR_SECTION_CODE_FAMILY,
            active: [],
            superseded: [],
        voided: [],
      },
      [PPR_SECTION_CODE_EMPLOYMENT_BIOGRAPHY]: {
        section_code: PPR_SECTION_CODE_EMPLOYMENT_BIOGRAPHY,
        active: [
          {
            record_id: 101,
            record_kind: "episode",
            employer_name: "ТОО Альфа",
            department_name: "Производство",
            position_title: "Инженер",
            employment_type: null,
            started_at: "2020-01-01",
            ended_at: "2022-12-31",
            termination_reason: null,
            document_reference: null,
            source_system: "manual",
            source_id: null,
            provenance: null,
            notes: null,
            employee_context_id: null,
            verification_status: "verified",
            lifecycle_status: "active",
            created_at: "2024-01-01T00:00:00Z",
            updated_at: "2024-03-01T00:00:00Z",
          },
          {
            record_id: 100,
            record_kind: "narrative_summary",
            employer_name: null,
            department_name: null,
            position_title: null,
            employment_type: null,
            started_at: null,
            ended_at: null,
            termination_reason: null,
            document_reference: null,
            source_system: "manual",
            source_id: null,
            provenance: null,
            notes: "Сводный стаж до поступления",
            employee_context_id: null,
            verification_status: "verified",
            lifecycle_status: "active",
            created_at: "2024-01-01T00:00:00Z",
            updated_at: "2024-02-01T00:00:00Z",
          },
        ],
        superseded: [
          {
            record_id: 99,
            record_kind: "episode",
            employer_name: "ТОО Бета (устар.)",
            department_name: null,
            position_title: "Стажёр",
            employment_type: null,
            started_at: "2015-01-01",
            ended_at: "2017-12-31",
            termination_reason: null,
            document_reference: null,
            source_system: "manual",
            source_id: null,
            provenance: null,
            notes: null,
            employee_context_id: null,
            verification_status: "verified",
            lifecycle_status: "superseded",
            created_at: "2024-01-01T00:00:00Z",
            updated_at: "2024-01-15T00:00:00Z",
          },
        ],
        voided: [],
      },
    },
      }),
    );

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByText("Сведения о родственниках отсутствуют.")).toBeInTheDocument();
    });
  });

  it("renders family section for applicant card", async () => {
    getPprByPersonIdMock.mockResolvedValue(
      buildMaterializedPpr({
        identity: {
          requested_person_id: 501,
          requested_employee_id: null,
          resolved_person_id: 501,
          merge_redirected: false,
          merge_chain: [501],
          employee_context_id: null,
          person_status: "active",
          match_key: "iin:seed",
          iin: "900101350123",
        },
        materialization: {
          materialized: true,
          lifecycle_state: "CREATED",
          hr_relationship_context: PPR_HR_RELATIONSHIP_CANDIDATE,
          envelope_version: 1,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-02-01T00:00:00Z",
        },
      }),
    );

    render(<PprPersonalCardPageClient personId="501" />);

    await waitFor(() => {
      expect(screen.getByTestId("ppr-applicant-status-banner")).toBeInTheDocument();
      expect(screen.getByText("Иванова Мария Петровна")).toBeInTheDocument();
    });
    expect(getPprByPersonIdMock).toHaveBeenCalledTimes(1);
  });

  it("renders military section with active record", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByTestId("military-record-301")).toBeInTheDocument();
      expect(screen.getByText("Алмалинский РВК")).toBeInTheDocument();
    });
  });

  it("shows military empty state", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(
      buildMaterializedPpr({
        sections: {
          [PPR_SECTION_CODE_MILITARY]: {
            section_code: PPR_SECTION_CODE_MILITARY,
            active: [],
            superseded: [],
            voided: [],
          },
        },
      }),
    );

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByTestId("military-empty")).toBeInTheDocument();
      expect(screen.getByText("Сведения о воинском учёте отсутствуют.")).toBeInTheDocument();
    });
  });

  it("shows military mutations for materialized editable card", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" canEditPprSections />);

    await waitFor(() => {
      expect(screen.getByTestId("military-create-btn")).toBeInTheDocument();
      expect(screen.getByTestId("military-supersede-btn-301")).toBeInTheDocument();
      expect(screen.getByTestId("military-void-btn-301")).toBeInTheDocument();
    });
  });

  it("hides military mutations for read-only card access", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" canEditPprSections={false} />);

    await waitFor(() => {
      expect(screen.getByTestId("military-record-301")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("military-create-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("military-supersede-btn-301")).not.toBeInTheDocument();
    expect(screen.queryByTestId("military-void-btn-301")).not.toBeInTheDocument();
  });

  it("shows military on person card with editable actions", async () => {
    getPprByPersonIdMock.mockResolvedValue(
      buildMaterializedPpr({
        identity: {
          requested_person_id: 501,
          requested_employee_id: null,
          resolved_person_id: 501,
          merge_redirected: false,
          merge_chain: [501],
          employee_context_id: null,
          person_status: "active",
          match_key: "iin:seed",
          iin: "900101350123",
        },
        materialization: {
          materialized: true,
          lifecycle_state: "CREATED",
          hr_relationship_context: PPR_HR_RELATIONSHIP_CANDIDATE,
          envelope_version: 1,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-02-01T00:00:00Z",
        },
        sections: {
          [PPR_SECTION_CODE_MILITARY]: {
            section_code: PPR_SECTION_CODE_MILITARY,
            active: [],
            superseded: [],
            voided: [],
          },
        },
      }),
    );

    render(<PprPersonalCardPageClient personId="501" />);

    await waitFor(() => {
      expect(screen.getByTestId("military-empty")).toBeInTheDocument();
      expect(screen.getByTestId("military-create-btn")).toBeInTheDocument();
    });
    expect(getPprByPersonIdMock).toHaveBeenCalledTimes(1);
  });

  it("shows applications history section on personal card", async () => {
    getPprByPersonIdMock.mockResolvedValue(
      buildMaterializedPpr({
        identity: {
          requested_person_id: 501,
          requested_employee_id: null,
          resolved_person_id: 501,
          merge_redirected: false,
          merge_chain: [501],
          employee_context_id: null,
          person_status: "active",
          match_key: "iin:seed",
          iin: "900101350123",
        },
        materialization: {
          materialized: true,
          lifecycle_state: "CREATED",
          hr_relationship_context: PPR_HR_RELATIONSHIP_CANDIDATE,
          envelope_version: 1,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-02-01T00:00:00Z",
        },
      }),
    );

    render(<PprPersonalCardPageClient personId="501" />);

    await waitFor(() => {
      expect(screen.getByTestId("applications-section")).toHaveTextContent("Кадровые обращения #501");
    });
    expect(screen.getByRole("link", { name: "Кадровые обращения" })).toBeInTheDocument();
  });

  it("does not expose legacy import-card dual-fetch", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByText("КазНМУ")).toBeInTheDocument();
    });

    expect(getEmployeeImportCard2OptionalMock).not.toHaveBeenCalled();
    expect(getPprByEmployeeIdMock).toHaveBeenCalledTimes(1);
  });
});
