import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import PersonLinkDialog from "./PersonLinkDialog";
import { applyPersonLink, runPersonLinkPreflight } from "../_lib/personnelMigrationApi.client";

const routerReplace = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: routerReplace }) }));
vi.mock("../_lib/personnelMigrationApi.client", () => ({
  applyPersonLink: vi.fn(), runPersonLinkPreflight: vi.fn(),
}));

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const record = { normalized_record_id: 1, employee_id: 44, iin: "123456789012", review_status: "approved", record_kind: "education", source_field: "sheet" } as any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const preflight = { classification: "P0_CREATE", blockers: [], expected_precondition: "x", control_list_full_name: "Нурбеков Багдат Байтлевич", employee_full_name: "Нурбеков Бахдат Байтлевич" } as any;

describe("PersonLinkDialog", () => {
  beforeEach(() => {
    vi.mocked(applyPersonLink).mockReset();
    vi.mocked(runPersonLinkPreflight).mockReset();
    routerReplace.mockReset();
  });

  it("shows records, requires name confirmation and applies once", async () => {
    vi.mocked(runPersonLinkPreflight).mockResolvedValue(preflight);
    vi.mocked(applyPersonLink).mockResolvedValue({ person_id: 9 } as never);
    render(<PersonLinkDialog employeeId={44} employeeName="Нурбеков Бахдат Байтлевич" iin={record.iin} records={[record]} preflight={preflight} onClose={vi.fn()} />);
    expect(screen.getByText(/#1 · education · approved/)).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: "Подтвердить" });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Подтверждаю исправление ФИО"));
    fireEvent.click(submit);
    await waitFor(() => expect(applyPersonLink).toHaveBeenCalledTimes(1));
    expect(routerReplace).toHaveBeenCalledWith("/directory/personnel/persons/9/card");
  });

  it("shows the approval blocker and never applies it", () => {
    const blocked = {
      ...preflight,
      blockers: [{ code: "IMPORT_RECORD_NOT_APPROVED", detail: "Approval is required." }],
    };
    render(<PersonLinkDialog employeeId={44} employeeName="Нурбеков Бахдат Байтлевич" iin={record.iin} records={[record]} preflight={blocked} onClose={vi.fn()} />);
    expect(screen.getByText(/IMPORT_RECORD_NOT_APPROVED/)).toBeInTheDocument();
    const submit = screen.getAllByRole("button").find(button => button.hasAttribute("disabled"));
    expect(submit).toBeDefined();
    fireEvent.click(submit!);
    expect(applyPersonLink).not.toHaveBeenCalled();
  });
});
