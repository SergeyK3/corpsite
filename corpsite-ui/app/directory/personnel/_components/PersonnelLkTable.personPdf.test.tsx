import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PersonnelLkTable from "./PersonnelLkTable";

const personPdf = vi.fn().mockResolvedValue({ ok: true });
const applicantPdf = vi.fn().mockResolvedValue({ ok: true });
vi.mock("../_lib/personCardPdfOpen.client", () => ({ downloadPersonCardPdf: (...args: unknown[]) => personPdf(...args) }));
vi.mock("@/app/intake/_lib/intakePdfOpen.client", () => ({ downloadIntakePdfByApplicationId: (...args: unknown[]) => applicantPdf(...args) }));

describe("PersonnelLkTable person PDF", () => {
  it("uses person_id for an employee and preserves applicant application PDF", async () => {
    render(<PersonnelLkTable loading={false} registryReturnHref="/directory/personnel/lk" onOpenApplicant={vi.fn()} items={[
      { record_kind: "employee", person_id: 7, employee_id: 3, id: 3, active_application_id: null, fio: "Сотрудник", iin: null, rate: null, status: "active", application_status: null },
      { record_kind: "applicant", person_id: 8, employee_id: null, id: null, active_application_id: 11, fio: "Претендент", iin: null, rate: null, status: "active", application_status: "pending" },
    ]} />);
    fireEvent.click(screen.getByTestId("personnel-lk-pdf-person-7"));
    expect(personPdf).toHaveBeenCalledWith(7);
    fireEvent.click(screen.getByTestId("personnel-lk-pdf-application-11"));
    expect(applicantPdf).toHaveBeenCalledWith(11);
  });
});
