import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import HrChangeEventDrawer from "./HrChangeEventDrawer";
import type { HrChangeEventRow } from "../_lib/hrChangeEventsApi.client";

const fullIin = "770101234567";

const sampleEvent: HrChangeEventRow = {
  change_event_id: 101,
  prior_snapshot_id: 1,
  new_snapshot_id: 2,
  event_type: "POSITION_CHANGED",
  event_at: "2026-06-15T12:00:00.000Z",
  employee_id: 55,
  match_key: `iin:${fullIin}`,
  record_kind: "roster",
  prior_entry_id: 10,
  new_entry_id: 11,
  field_name: "position_raw",
  old_value: "Медсестра",
  new_value: "Старшая медсестра",
  department: "Терапия",
  org_unit_id: 3,
  full_name: "Петрова Анна",
  iin: fullIin,
  details: null,
};

describe("HrChangeEventDrawer", () => {
  it("renders full IIN without masking", () => {
    render(<HrChangeEventDrawer event={sampleEvent} open onClose={vi.fn()} />);

    expect(screen.getByText(fullIin)).toBeInTheDocument();
    expect(screen.queryByText(/7701\*+/)).not.toBeInTheDocument();
  });
});
