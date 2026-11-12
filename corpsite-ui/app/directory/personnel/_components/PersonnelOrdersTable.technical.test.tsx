import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PersonnelOrderListItem } from "../_lib/personnelOrdersApi.client";
import { PersonnelOrdersTable } from "./PersonnelOrdersTable";

const legacy: PersonnelOrderListItem = { order_id: 1, order_number: "PERSONNEL-IMPORT-2026-273", order_date: "2026-01-01", order_type_code: "HIRE", order_class: "PERSONNEL", status: "SIGNED", source_mode: "DIGITAL", storage_json: {}, employee_names: [], employee_ids: [], item_count: 0, created_by: 1 };
const confirmed: PersonnelOrderListItem = { ...legacy, order_id: 2, order_number: "PERSONNEL-IMPORT-2026-274", storage_json: { technical_record: true, record_quality: "TECHNICAL_RECORD" } };
const corrected: PersonnelOrderListItem = { ...legacy, order_id: 3, order_number: "DEMO-47", storage_json: { technical_record: true, record_quality: "TECHNICAL_RECORD", import_source_order_number: "CSV-PILOT-47" } };

describe("technical personnel-order labels", () => {
  it("shows a neutral import label before and after the official number is entered", () => {
    render(<PersonnelOrdersTable items={[legacy, confirmed, corrected]} />);
    expect(screen.getAllByText("Импортирован")).toHaveLength(3);
    expect(screen.getByText("DEMO-47")).toBeInTheDocument();
    expect(screen.queryByText("Техническая запись прежнего формата")).not.toBeInTheDocument();
  });
});
