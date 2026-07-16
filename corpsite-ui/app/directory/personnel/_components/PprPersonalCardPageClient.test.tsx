import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PprPersonalCardPageClient from "./PprPersonalCardPageClient";
import {
  PPR_SECTION_CODE_EDUCATION,
  PPR_SECTION_CODE_TRAINING,
  type PprCompositeReadResponse,
} from "../_lib/pprQueryTypes";
import { PERSONAL_CARD_TITLE } from "@/lib/personnelCardTerminology";
import { PPR_CARD_RETURN_HREF } from "@/lib/pprCardFeature";
import { toApiError } from "@/lib/api";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn() }),
  usePathname: () => "/directory/personnel/employees/42/card",
  useSearchParams: () => new URLSearchParams(""),
}));

const getPprByEmployeeIdMock = vi.fn();
vi.mock("../_lib/pprQueryApi.client", () => ({
  getPprByEmployeeId: (...args: unknown[]) => getPprByEmployeeIdMock(...args),
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
  getEmployeeImportCard2OptionalMock.mockReset();
  pushMock.mockReset();
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
    expect(pushMock).toHaveBeenCalledWith(PPR_CARD_RETURN_HREF);
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
        sections: {},
        events: null,
      }),
    );

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(
        screen.getByText(/Формирование служебной части личной карточки ещё не завершено/),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Не сформирована полностью")).toBeInTheDocument();
    expect(screen.queryByText(/ошибк/i)).not.toBeInTheDocument();
  });

  it("collapses superseded and voided education groups by default", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByText("КазНМУ")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /Заменённые записи \(1\)/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(screen.queryByText("Школа №1")).not.toBeInTheDocument();
    expect(screen.queryByText("Аннулированный колледж")).not.toBeInTheDocument();
  });

  it("expands superseded education records on click", async () => {
    getPprByEmployeeIdMock.mockResolvedValue(buildMaterializedPpr());

    render(<PprPersonalCardPageClient employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByText("КазНМУ")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Заменённые записи \(1\)/ }));
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
