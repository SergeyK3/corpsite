import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { listHREventRegistryMock, listPersonnelEventsMock } = vi.hoisted(() => ({
  listHREventRegistryMock: vi.fn(),
  listPersonnelEventsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/components/TaskOrgFiltersBar", () => ({ default: () => null }));
vi.mock("@/lib/taskOrgFilters", () => ({
  readTaskOrgFiltersFromSearchParams: () => ({}),
}));
vi.mock("../_lib/personnelJournalApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelJournalApi.client")>("../_lib/personnelJournalApi.client");
  return {
    ...actual,
    listHREventRegistry: listHREventRegistryMock,
    listPersonnelEvents: listPersonnelEventsMock,
  };
});

import PersonnelJournalPageClient from "./PersonnelJournalPageClient";

afterEach(() => cleanup());

describe("PersonnelJournalPageClient annual leave", () => {
  it("renders leave period and context without false personnel transitions", async () => {
    listHREventRegistryMock.mockResolvedValue({ version: "1.1", items: [] });
    listPersonnelEventsMock.mockResolvedValue({
      total: 1,
      items: [{
        event_id: 1551,
        employee_id: 17,
        employee_name: "A. Employee",
        event_type: "ANNUAL_LEAVE",
        event_label: "Annual leave",
        effective_date: "2026-03-26",
        metadata: { leave_start: "2026-03-26", leave_end: "2026-04-03", leave_days: 9 },
        from_org_unit_id: 75,
        from_org_unit_name: "Accounting",
        to_org_unit_id: 75,
        to_org_unit_name: "Accounting",
        from_position_id: 8,
        from_position_name: "Chief accountant",
        to_position_id: 8,
        to_position_name: "Chief accountant",
        from_rate: 1,
        to_rate: 1,
        order_ref: "№79-д от 2026-03-04",
        comment: null,
      }],
    });

    render(<PersonnelJournalPageClient />);

    expect(await screen.findByText("Период отпуска: 26.03.2026 – 03.04.2026")).toBeInTheDocument();
    expect(screen.getByText("Календарных дней: 9")).toBeInTheDocument();
    expect(screen.getByText("Подразделение: Accounting")).toBeInTheDocument();
    expect(screen.getByText("Должность: Chief accountant")).toBeInTheDocument();
    expect(screen.getByText("Ставка: 1")).toBeInTheDocument();
    expect(screen.getByText("№79-д от 04.03.2026")).toBeInTheDocument();
    expect(screen.queryByText("Accounting → Accounting")).not.toBeInTheDocument();
    expect(screen.queryByText("Chief accountant → Chief accountant")).not.toBeInTheDocument();
    expect(screen.queryByText("1 → 1")).not.toBeInTheDocument();
  });

  it("keeps transfer transitions and omits empty annual-leave context lines", async () => {
    listHREventRegistryMock.mockResolvedValue({ version: "1.1", items: [] });
    listPersonnelEventsMock.mockResolvedValue({
      total: 2,
      items: [
        {
          event_id: 1, employee_id: 1, employee_name: "Transfer employee", event_type: "TRANSFER", effective_date: "2026-03-01",
          from_org_unit_id: 1, from_org_unit_name: "Old unit", to_org_unit_id: 2, to_org_unit_name: "New unit",
          from_position_id: 1, from_position_name: "Old position", to_position_id: 2, to_position_name: "New position",
          from_rate: 0.5, to_rate: 1, order_ref: null, comment: null,
        },
        {
          event_id: 2, employee_id: 2, employee_name: "Leave employee", event_type: "ANNUAL_LEAVE", effective_date: "2026-03-02",
          metadata: {}, from_org_unit_id: null, from_org_unit_name: null, to_org_unit_id: null, to_org_unit_name: null,
          from_position_id: null, from_position_name: null, to_position_id: null, to_position_name: null,
          from_rate: null, to_rate: null, order_ref: null, comment: null,
        },
      ],
    });

    render(<PersonnelJournalPageClient />);

    expect(await screen.findByText("Отделение: Old unit → New unit")).toBeInTheDocument();
    expect(screen.getByText("Должность: Old position → New position")).toBeInTheDocument();
    expect(screen.getByText("Ставка: 0.5 → 1")).toBeInTheDocument();
    expect(screen.queryByText("Подразделение: —")).not.toBeInTheDocument();
    expect(screen.queryByText("Должность: —")).not.toBeInTheDocument();
    expect(screen.queryByText("Ставка: —")).not.toBeInTheDocument();
  });
});
