import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PersonnelOrderListItem } from "../_lib/personnelOrdersApi.client";
import { PersonnelOrdersTable } from "./PersonnelOrdersTable";

const legacy: PersonnelOrderListItem = { order_id: 1, order_number: "PERSONNEL-IMPORT-2026-273", order_date: "2026-01-01", order_type_code: "HIRE", order_class: "PERSONNEL", status: "SIGNED", source_mode: "DIGITAL", storage_json: {}, employee_names: [], employee_ids: [], item_count: 0, created_by: 1 };
const confirmed: PersonnelOrderListItem = { ...legacy, order_id: 2, order_number: "PERSONNEL-IMPORT-2026-274", storage_json: { technical_record: true, record_quality: "TECHNICAL_RECORD" } };

describe("technical personnel-order labels", () => {
  it("keeps the legacy import label distinct from confirmed technical provenance", () => {
    render(<PersonnelOrdersTable items={[legacy, confirmed]} />);
    expect(screen.getByText("Техническая запись прежнего формата")).toBeInTheDocument();
    expect(screen.getByText("Техническая запись")).toBeInTheDocument();
  });
});
