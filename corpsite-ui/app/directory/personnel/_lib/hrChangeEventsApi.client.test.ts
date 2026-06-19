import { describe, expect, it } from "vitest";

import {
  buildHrChangeEventsExportUrl,
  buildHrChangeEventsHref,
  buildHrChangeEventsQueryParams,
  filterHrChangeEventsBySearch,
  parseHrChangeEventsFilters,
  type HrChangeEventRow,
} from "./hrChangeEventsApi.client";

describe("hrChangeEventsApi.client", () => {
  it("builds query params for API filters", () => {
    const qs = buildHrChangeEventsQueryParams(
      {
        employee_id: 42,
        department: "Терапия",
        event_type: "POSITION_CHANGED",
        date_from: "2026-01-01",
        date_to: "2026-06-30",
        source_batch_id: 7,
      },
      { includeClientSearch: false },
    );

    expect(qs.get("employee_id")).toBe("42");
    expect(qs.get("department")).toBe("Терапия");
    expect(qs.get("event_type")).toBe("POSITION_CHANGED");
    expect(qs.get("date_from")).toBe("2026-01-01");
    expect(qs.get("date_to")).toBe("2026-06-30");
    expect(qs.get("source_batch_id")).toBe("7");
    expect(qs.get("q")).toBeNull();
  });

  it("updates query params when filters change", () => {
    const initial = buildHrChangeEventsQueryParams({ event_type: "NEW" });
    expect(initial.get("event_type")).toBe("NEW");

    const next = buildHrChangeEventsQueryParams({
      event_type: "REMOVED",
      department: "Хирургия",
      q: "Иванов",
    });
    expect(next.get("event_type")).toBe("REMOVED");
    expect(next.get("department")).toBe("Хирургия");
    expect(next.get("q")).toBe("Иванов");
    expect(next.get("event_type")).not.toBe(initial.get("event_type"));
  });

  it("parses search params back into filters", () => {
    const params = new URLSearchParams(
      "employee_id=5&event_type=NEW&date_from=2026-06-01&source_batch_id=12&q=Петров",
    );
    expect(parseHrChangeEventsFilters(params)).toEqual({
      employee_id: 5,
      department: undefined,
      org_unit_id: undefined,
      event_type: "NEW",
      date_from: "2026-06-01",
      date_to: undefined,
      prior_snapshot_id: undefined,
      new_snapshot_id: undefined,
      source_batch_id: 12,
      q: "Петров",
    });
  });

  it("builds employee and batch deep links", () => {
    expect(buildHrChangeEventsHref({ employee_id: 9 })).toBe(
      "/directory/personnel/hr-change-events?employee_id=9",
    );
    expect(buildHrChangeEventsHref({ source_batch_id: 3 })).toBe(
      "/directory/personnel/hr-change-events?source_batch_id=3",
    );
  });

  it("builds export url with active filters", () => {
    const url = buildHrChangeEventsExportUrl({
      event_type: "NEW",
      department: "Терапия",
      q: "Иванов",
      source_batch_id: 4,
    });
    expect(url).toContain("/directory/personnel/hr-change-events/export.xlsx");
    expect(url).toContain("event_type=NEW");
    expect(url).toContain("department=");
    expect(url).toContain("q=");
    expect(decodeURIComponent(url)).toContain("q=Иванов");
    expect(url).toContain("source_batch_id=4");
  });

  it("filters items by employee search client-side", () => {
    const items: HrChangeEventRow[] = [
      {
        change_event_id: 1,
        prior_snapshot_id: 1,
        new_snapshot_id: 2,
        event_type: "NEW",
        event_at: "2026-06-01T10:00:00Z",
        employee_id: 10,
        match_key: "iin:123",
        record_kind: "roster",
        prior_entry_id: null,
        new_entry_id: 1,
        field_name: null,
        old_value: null,
        new_value: null,
        department: "A",
        org_unit_id: 1,
        full_name: "Иванов Иван",
        iin: "123",
        details: null,
      },
    ];
    expect(filterHrChangeEventsBySearch(items, "иван")).toHaveLength(1);
    expect(filterHrChangeEventsBySearch(items, "сидор")).toHaveLength(0);
  });
});
