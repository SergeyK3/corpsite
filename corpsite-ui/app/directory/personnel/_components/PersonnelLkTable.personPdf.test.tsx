import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelLkTable from "./PersonnelLkTable";

const personPdf = vi.fn().mockResolvedValue({ ok: true });
const applicantPdf = vi.fn().mockResolvedValue({ ok: true });
vi.mock("../_lib/personCardPdfOpen.client", () => ({ downloadPersonCardPdf: (...args: unknown[]) => personPdf(...args) }));
vi.mock("@/app/intake/_lib/intakePdfOpen.client", () => ({ downloadIntakePdfByApplicationId: (...args: unknown[]) => applicantPdf(...args) }));

afterEach(cleanup);

describe("PersonnelLkTable person PDF", () => {
  it("uses person_id for an employee and preserves applicant application PDF", async () => {
    const onOpenApplicant = vi.fn();
    render(<PersonnelLkTable loading={false} registryReturnHref="/directory/personnel/lk" onOpenApplicant={onOpenApplicant} items={[
      { record_kind: "employee", person_id: 7, employee_id: 3, id: 3, active_application_id: null, fio: "Сотрудник", iin: null, rate: null, status: "active", application_status: null },
      { record_kind: "applicant", person_id: 8, employee_id: null, id: null, active_application_id: 11, fio: "Претендент", iin: null, rate: null, status: "active", application_status: "pending" },
    ]} />);
    fireEvent.click(screen.getByTestId("personnel-lk-pdf-person-7"));
    expect(personPdf).toHaveBeenCalledWith(7);
    fireEvent.click(screen.getByTestId("personnel-lk-pdf-application-11"));
    expect(applicantPdf).toHaveBeenCalledWith(11);
    fireEvent.click(screen.getByTestId("personnel-lk-open-application-11"));
    expect(onOpenApplicant).toHaveBeenCalledWith(11);
  });

  it("prevents duplicate applicant PDF generation while the first request is pending", async () => {
    applicantPdf.mockReset();
    let finish: ((result: { ok: true }) => void) | undefined;
    applicantPdf.mockImplementationOnce(
      () => new Promise<{ ok: true }>((resolve) => { finish = resolve; }),
    );
    render(<PersonnelLkTable loading={false} registryReturnHref="/directory/personnel/lk" onOpenApplicant={vi.fn()} items={[
      { record_kind: "applicant", person_id: 8, employee_id: null, id: null, active_application_id: 11, fio: "Претендент", iin: null, rate: null, status: "active", application_status: "pending" },
    ]} />);

    const pdf = screen.getByTestId("personnel-lk-pdf-application-11");
    fireEvent.click(pdf);
    fireEvent.click(pdf);
    expect(applicantPdf).toHaveBeenCalledTimes(1);
    expect(pdf).toBeDisabled();
    expect(pdf).toHaveTextContent("Формирование…");

    finish?.({ ok: true });
    await waitFor(() => expect(pdf).not.toBeDisabled());
  });
});
