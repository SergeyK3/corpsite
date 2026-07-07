import { describe, expect, it } from "vitest";

import {
  buildPersonnelOrdersHref,
  buildPersonnelOrdersQueryParams,
  filterPersonnelOrdersBySearch,
  parsePersonnelOrdersFilters,
  type PersonnelOrderListItem,
} from "./personnelOrdersApi.client";

describe("personnelOrdersApi.client", () => {
  it("builds query params for API filters", () => {
    const qs = buildPersonnelOrdersQueryParams(
      {
        status: "REGISTERED",
        order_type_code: "HIRE",
        date_from: "2026-01-01",
        date_to: "2026-06-30",
        employee_id: 42,
        org_unit_id: 7,
      },
      { includeClientSearch: false },
    );

    expect(qs.get("status")).toBe("REGISTERED");
    expect(qs.get("order_type_code")).toBe("HIRE");
    expect(qs.get("date_from")).toBe("2026-01-01");
    expect(qs.get("date_to")).toBe("2026-06-30");
    expect(qs.get("employee_id")).toBe("42");
    expect(qs.get("org_unit_id")).toBe("7");
    expect(qs.get("q")).toBeNull();
  });

  it("parses search params back into filters", () => {
    const params = new URLSearchParams(
      "status=SIGNED&order_type_code=TRANSFER&date_from=2026-06-01&employee_id=5&org_unit_id=3&q=WPPO",
    );
    expect(parsePersonnelOrdersFilters(params)).toEqual({
      status: "SIGNED",
      order_type_code: "TRANSFER",
      date_from: "2026-06-01",
      date_to: undefined,
      employee_id: 5,
      org_unit_id: 3,
      q: "WPPO",
    });
  });

  it("builds deep links", () => {
    expect(buildPersonnelOrdersHref({ employee_id: 9 })).toBe(
      "/directory/personnel/orders?employee_id=9",
    );
    expect(buildPersonnelOrdersHref({ status: "VOIDED" })).toBe(
      "/directory/personnel/orders?status=VOIDED",
    );
  });

  it("filters items by order number and employee names client-side", () => {
    const items: PersonnelOrderListItem[] = [
      {
        order_id: 1,
        order_number: "WPPO-001",
        order_date: "2026-07-07",
        order_type_code: "HIRE",
        order_class: "PERSONNEL",
        status: "REGISTERED",
        source_mode: "PAPER",
        created_by: 1,
        item_count: 1,
        employee_ids: [10],
        employee_names: ["Иванов Иван"],
      },
    ];
    expect(filterPersonnelOrdersBySearch(items, "wppo")).toHaveLength(1);
    expect(filterPersonnelOrdersBySearch(items, "иван")).toHaveLength(1);
    expect(filterPersonnelOrdersBySearch(items, "сидор")).toHaveLength(0);
  });
});
