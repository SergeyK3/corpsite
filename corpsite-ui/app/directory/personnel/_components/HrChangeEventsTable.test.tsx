import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HrChangeEventsTable } from "./HrChangeEventsTable";
import type { HrChangeEventRow } from "../_lib/hrChangeEventsApi.client";

const sampleRow: HrChangeEventRow = {
  change_event_id: 101,
  prior_snapshot_id: 1,
  new_snapshot_id: 2,
  event_type: "POSITION_CHANGED",
  event_at: "2026-06-15T12:00:00.000Z",
  employee_id: 55,
  match_key: "iin:770101234567",
  record_kind: "roster",
  prior_entry_id: 10,
  new_entry_id: 11,
  field_name: "position_raw",
  old_value: "Медсестра",
  new_value: "Старшая медсестра",
  department: "Терапия",
  org_unit_id: 3,
  full_name: "Петрова Анна",
  iin: "770101234567",
  details: null,
};

describe("HrChangeEventsTable", () => {
  it("renders empty state", () => {
    render(<HrChangeEventsTable items={[]} loading={false} emptyMessage="Нет данных" />);
    expect(screen.getByTestId("hr-change-events-empty")).toHaveTextContent("Нет данных");
  });

  it("renders loading state", () => {
    render(<HrChangeEventsTable items={[]} loading emptyMessage="Нет данных" />);
    expect(screen.getByTestId("hr-change-events-loading")).toBeInTheDocument();
  });

  it("renders table rows with event values", () => {
    const onRowClick = vi.fn();
    render(<HrChangeEventsTable items={[sampleRow]} onRowClick={onRowClick} />);

    expect(screen.getByTestId("hr-change-events-table")).toBeInTheDocument();
    expect(screen.getByText("Петрова Анна")).toBeInTheDocument();
    expect(screen.getByText("Терапия")).toBeInTheDocument();
    expect(screen.getByText("Медсестра")).toBeInTheDocument();
    expect(screen.getByText("Старшая медсестра")).toBeInTheDocument();

    screen.getByTestId("hr-change-event-row-101").click();
    expect(onRowClick).toHaveBeenCalledWith(sampleRow);
  });
});
