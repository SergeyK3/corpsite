import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EmployeePersonnelHistorySection from "./EmployeePersonnelHistorySection";
import type { EmployeeEventDTO } from "../../employees/_lib/types";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("../../employees/_lib/api.client", () => ({
  listEmployeeEvents: vi.fn(async () => ({
    total: 1,
    items: [
      {
        event_id: 10,
        event_type: "CORRECTION",
        effective_date: "2026-07-01",
        from_org_unit_id: 10,
        to_org_unit_id: 20,
        from_position_id: 501,
        to_position_id: 502,
        from_rate: 1,
        to_rate: 0.5,
        order_ref: null,
        comment: "Сверка с приказом",
        created_by: 1,
        created_at: "2026-07-01T10:00:00.000Z",
        metadata: {
          domain: "assignment",
          reason: "Ошибка импорта",
          changes: {
            org_unit_id: { from: 10, to: 20 },
            full_name: { from: "Иванов И.", to: "Иванов Иван" },
          },
        },
      } satisfies EmployeeEventDTO,
    ],
  })),
  getPositions: vi.fn(async () => ({
    items: [
      { position_id: 501, name: "Врач" },
      { position_id: 502, name: "Медсестра" },
    ],
  })),
  mapApiErrorToMessage: (e: unknown, fallback = "Ошибка") =>
    e instanceof Error ? e.message : fallback,
}));

vi.mock("../../org-units/_lib/api.client", () => ({
  getOrgUnitsTree: vi.fn(async () => ({
    items: [
      { unit_id: 10, name: "Стационар", children: [] },
      { unit_id: 20, name: "Амбулатория", children: [] },
    ],
  })),
}));

afterEach(() => {
  cleanup();
});

describe("EmployeePersonnelHistorySection", () => {
  it("renders informative CORRECTION event details", async () => {
    render(<EmployeePersonnelHistorySection employeeId="1" />);

    expect(await screen.findByTestId("employee-personnel-history")).toBeInTheDocument();
    expect(screen.getByText("Исправление назначения")).toBeInTheDocument();
    expect(screen.getByText(/Подразделение:/)).toBeInTheDocument();
    expect(screen.getByText(/ФИО:/)).toBeInTheDocument();
    expect(screen.getByText(/Причина: Ошибка импорта/)).toBeInTheDocument();
    expect(screen.getByText(/Комментарий: Сверка с приказом/)).toBeInTheDocument();
  });
});
