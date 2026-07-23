import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PersonnelApplicationsTable } from "./PersonnelApplicationsTable";
import type { PersonnelApplicationListItem } from "../_lib/personnelApplicationsApi.client";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const baseItem: PersonnelApplicationListItem = {
  application_id: 10,
  person_id: 5,
  full_name: "Петров Пётр Петрович",
  iin: "900101300123",
  status: "registered",
  application_received_at: "2026-07-01",
  intended_org_group_id: 1,
  intended_org_unit_id: 2,
  intended_position_id: 3,
  intended_org_group_name: "Группа",
  intended_org_unit_name: "Терапия",
  intended_position_name: "Медсестра",
  registered_at: "2026-07-02T10:00:00Z",
  registered_by_user_id: 7,
  registered_by_name: "HR User",
  director_resolution_status: null,
  personnel_order_id: null,
  is_active: true,
  intake_link_status: null,
  intake_draft_status: null,
  intake_link_display_state: "not_issued",
  intake_url_path: null,
  intake_opened_at: null,
  intake_submitted_at: null,
  employee_id: null,
  employee_full_name: null,
  completed_at: null,
  closed_at: null,
  is_read_only: false,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelApplicationsTable", () => {
  it("renders sticky actions column with Open button for every active row", () => {
    const onOpen = vi.fn();
    render(
      <PersonnelApplicationsTable
        items={[
          baseItem,
          {
            ...baseItem,
            application_id: 11,
            full_name: "Иванов Иван",
            intake_draft_status: "submitted",
            intake_link_display_state: "submitted",
          },
        ]}
        onOpen={onOpen}
      />,
    );

    expect(screen.getByRole("columnheader", { name: "Действия" })).toHaveClass("sticky");
    expect(screen.getByTestId("personnel-application-open-10")).toHaveTextContent("Открыть");
    expect(screen.getByTestId("personnel-application-open-11")).toHaveTextContent("Открыть");
  });

  it("opens the selected application when Open is clicked", () => {
    const onOpen = vi.fn();
    render(<PersonnelApplicationsTable items={[baseItem]} onOpen={onOpen} />);

    fireEvent.click(screen.getByTestId("personnel-application-open-10"));

    expect(onOpen).toHaveBeenCalledTimes(1);
    expect(onOpen).toHaveBeenCalledWith(10);
  });

  it("does not trigger row click when Open button is used", () => {
    const onOpen = vi.fn();
    render(<PersonnelApplicationsTable items={[baseItem]} onOpen={onOpen} />);

    fireEvent.click(screen.getByTestId("personnel-application-open-10"));

    expect(onOpen).toHaveBeenCalledWith(10);
  });

  it("renders Open button in archive mode", () => {
    const onOpen = vi.fn();
    render(
      <PersonnelApplicationsTable
        items={[{ ...baseItem, closed_at: "2026-08-01T12:00:00Z", is_active: false }]}
        archiveMode
        onOpen={onOpen}
      />,
    );

    fireEvent.click(screen.getByTestId("personnel-application-open-10"));
    expect(onOpen).toHaveBeenCalledWith(10);
  });

  it("keeps actions column visible in horizontally scrollable container", () => {
    render(
      <div style={{ width: "320px" }}>
        <PersonnelApplicationsTable items={[baseItem]} onOpen={vi.fn()} />
      </div>,
    );

    const tableWrapper = screen.getByTestId("personnel-applications-table");
    expect(tableWrapper).toHaveClass("overflow-x-auto");
    expect(screen.getByTestId("personnel-application-open-10")).toBeVisible();
  });
});
