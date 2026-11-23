import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ControlListEntryDialog from "./ControlListEntryDialog";
import { getEmployees } from "../_lib/api.client";
import { getEducationProfileDetail, getNormalizedRecord, listEducationProfiles, listNormalizedRecords } from "../../personnel/_lib/importApi.client";

vi.mock("../_lib/api.client", () => ({ getEmployees: vi.fn(), mapApiErrorToMessage: (error: unknown) => String(error) }));
vi.mock("../../personnel/_lib/importApi.client", () => ({
  listNormalizedRecords: vi.fn(), getNormalizedRecord: vi.fn(), listEducationProfiles: vi.fn(), getEducationProfileDetail: vi.fn(), mapImportApiError: (error: unknown) => String(error),
}));
vi.mock("./ControlListProfilePreviewDialog", () => ({ default: ({ detail, open }: { detail: { full_name: string } | null; open: boolean }) => open && detail ? <div data-testid="profile-preview">{detail.full_name}</div> : null }));
vi.mock("../../personnel/_components/ImportEnrollEmployeeWizard", () => ({ default: ({ record, onReviewed }: { record: { normalized_record_id: number }; onReviewed: (record: unknown) => void }) => <div data-testid="enroll-only-wizard" data-record-id={record.normalized_record_id}><button type="button" onClick={() => undefined}>dry run</button><button type="button" onClick={() => undefined}>cancel</button><button type="button" onClick={() => undefined}>error</button><button type="button" onClick={() => onReviewed(record)}>enrollment success</button></div> }));

const record = (id: number, batchId: number, rowId: number, iin = "750812450121", fullName = "Умерзакова Махаббат") =>
  ({ normalized_record_id: id, record_id: id, batch_id: batchId, row_id: rowId, iin, full_name: fullName }) as never;

function startEmptyOperationalSearch() {
  vi.mocked(getEmployees).mockResolvedValue({ items: [], total: 0 });
  render(<ControlListEntryDialog open onClose={vi.fn()} />);
  fireEvent.change(screen.getByPlaceholderText("Фамилия"), { target: { value: "Умерзакова" } });
  fireEvent.click(screen.getByRole("button", { name: "Найти" }));
}

async function openControlListSearch() {
  await screen.findByText("Сотрудник в оперативном контуре не найден");
  fireEvent.click(screen.getByRole("button", { name: "Найти в контрольном списке" }));
}

beforeEach(() => vi.clearAllMocks());
afterEach(cleanup);

describe("ControlListEntryDialog grouped control-list flow", () => {
  it("keeps operational result separate and does not query normalized records", async () => {
    vi.mocked(getEmployees).mockResolvedValue({ items: [{ id: "42", fio: "Иванова Анна", department: null, org_unit: null, position: null }], total: 1 } as never);
    render(<ControlListEntryDialog open onClose={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText("Фамилия"), { target: { value: "Иванова" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    expect(await screen.findByText("Сотрудник уже существует в оперативном контуре")).toBeInTheDocument();
    expect(listNormalizedRecords).not.toHaveBeenCalled();
  });

  it("groups four records with one IIN into one person and lists unique imports", async () => {
    vi.mocked(listNormalizedRecords).mockResolvedValue({ total: 4, limit: 50, offset: 0, items: [record(1, 809, 11), record(2, 809, 12), record(3, 613, 21), record(4, 613, 22)] } as never);
    startEmptyOperationalSearch();
    await openControlListSearch();
    expect(await screen.findByText("ИИН: 750812450121")).toBeInTheDocument();
    expect(screen.getByText("Импорты: 809, 613")).toBeInTheDocument();
    expect(screen.getByText("Исходных записей: 4")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Выбрать" })).toHaveLength(1);
  });

  it("does not group same-name records without an IIN", async () => {
    vi.mocked(listNormalizedRecords).mockResolvedValue({ total: 2, limit: 50, offset: 0, items: [record(1, 809, 11, ""), record(2, 613, 21, "")] } as never);
    startEmptyOperationalSearch();
    await openControlListSearch();
    expect(await screen.findAllByRole("button", { name: "Выбрать" })).toHaveLength(2);
  });

  it("deduplicates profiles within an import and keeps profiles from different imports selectable", async () => {
    const records = [record(1, 809, 11), record(2, 809, 12), record(3, 613, 21), record(4, 613, 22)];
    vi.mocked(listNormalizedRecords).mockResolvedValue({ total: 4, limit: 50, offset: 0, items: records } as never);
    vi.mocked(getNormalizedRecord).mockImplementation(async (id) => records.find((item) => item.normalized_record_id === id) as never);
    vi.mocked(listEducationProfiles).mockImplementation(async (batchId) => batchId === 809
      ? ({ batch_id: 809, total: 1, limit: 100, offset: 0, items: [{ profile_id: 91, source_row_ids: [11, 12], org_unit_name: "HR", position_raw: "Manager" }] } as never)
      : ({ batch_id: 613, total: 1, limit: 100, offset: 0, items: [{ profile_id: 92, source_row_ids: [21, 22], org_unit_name: "HR", position_raw: "Manager" }] } as never));

    startEmptyOperationalSearch();
    await openControlListSearch();
    fireEvent.click(await screen.findByRole("button", { name: "Выбрать" }));
    expect(await screen.findByText("2. Импортная карточка с расширенными сведениями")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByRole("radio")).toHaveLength(2));
    expect(screen.getByText("Импорт: 809")).toBeInTheDocument();
    expect(screen.getByText("Импорт: 613")).toBeInTheDocument();
    expect(screen.getAllByText("Связанных исходных записей: 2")).toHaveLength(2);
  });

  it("opens the selected read-only import card", async () => {
    const selected = record(1, 809, 11);
    vi.mocked(listNormalizedRecords).mockResolvedValue({ total: 1, limit: 50, offset: 0, items: [selected] } as never);
    vi.mocked(getNormalizedRecord).mockResolvedValue(selected as never);
    vi.mocked(listEducationProfiles).mockResolvedValue({ batch_id: 809, total: 1, limit: 100, offset: 0, items: [{ profile_id: 91, source_row_ids: [11], org_unit_name: "HR", position_raw: "Manager" }] } as never);
    vi.mocked(getEducationProfileDetail).mockResolvedValue({ full_name: "Умерзакова Махаббат" } as never);

    startEmptyOperationalSearch();
    await openControlListSearch();
    fireEvent.click(await screen.findByRole("button", { name: "Выбрать" }));
    const openButton = await screen.findByRole("button", { name: "Открыть импортную карточку" });
    fireEvent.click(openButton);
    await waitFor(() => expect(getEducationProfileDetail).toHaveBeenCalledWith(809, 91));
    expect(await screen.findByTestId("profile-preview")).toHaveTextContent("Умерзакова Махаббат");
  });

  it("does not open preview when delayed profile detail resolves after profile selection changes", async () => {
    const records = [record(1, 809, 11), record(3, 613, 21)];
    let resolvePreview: ((value: { full_name: string }) => void) | undefined;
    const previewPromise = new Promise<{ full_name: string }>((resolve) => {
      resolvePreview = resolve;
    });

    vi.mocked(listNormalizedRecords).mockResolvedValue({ total: 2, limit: 50, offset: 0, items: records } as never);
    vi.mocked(getNormalizedRecord).mockImplementation(async (id) => records.find((item) => item.normalized_record_id === id) as never);
    vi.mocked(listEducationProfiles).mockImplementation(async (batchId) =>
      batchId === 809
        ? ({ batch_id: 809, total: 1, limit: 100, offset: 0, items: [{ profile_id: 91, source_row_ids: [11], org_unit_name: "HR", position_raw: "Manager" }] } as never)
        : ({ batch_id: 613, total: 1, limit: 100, offset: 0, items: [{ profile_id: 92, source_row_ids: [21], org_unit_name: "HR", position_raw: "Manager" }] } as never),
    );
    vi.mocked(getEducationProfileDetail).mockReturnValue(previewPromise as never);

    startEmptyOperationalSearch();
    await openControlListSearch();
    fireEvent.click(await screen.findByRole("button", { name: "Выбрать" }));
    await waitFor(() => expect(screen.getAllByRole("radio")).toHaveLength(2));

    fireEvent.click(screen.getAllByRole("radio")[0]!);
    fireEvent.click(screen.getByRole("button", { name: "Открыть импортную карточку" }));
    await waitFor(() => expect(getEducationProfileDetail).toHaveBeenCalledWith(809, 91));

    fireEvent.click(screen.getAllByRole("radio")[1]!);
    expect(await screen.findByTestId("enroll-only-wizard")).toBeInTheDocument();
    expect(screen.queryByTestId("profile-preview")).not.toBeInTheDocument();

    resolvePreview?.({ full_name: "Умерзакова Махаббат" });
    await waitFor(() => expect(getEducationProfileDetail).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId("profile-preview")).not.toBeInTheDocument();
    expect(screen.getByTestId("enroll-only-wizard")).toBeInTheDocument();
  });

  it("refreshes the list callback only after the wizard reports successful enrollment", async () => {
    const selected = record(1, 809, 11);
    const onEnrolled = vi.fn();
    vi.mocked(listNormalizedRecords).mockResolvedValue({ total: 1, limit: 50, offset: 0, items: [selected] } as never);
    vi.mocked(getNormalizedRecord).mockResolvedValue(selected as never);
    vi.mocked(listEducationProfiles).mockResolvedValue({ batch_id: 809, total: 1, limit: 100, offset: 0, items: [{ profile_id: 91, source_row_ids: [11] }] } as never);
    vi.mocked(getEmployees).mockResolvedValue({ items: [], total: 0 });
    render(<ControlListEntryDialog open onClose={vi.fn()} onEnrolled={onEnrolled} />);
    fireEvent.change(screen.getByPlaceholderText("Фамилия"), { target: { value: "Умерзакова" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    await openControlListSearch();
    fireEvent.click(await screen.findByRole("button", { name: "Выбрать" }));
    await screen.findByTestId("enroll-only-wizard");
    fireEvent.click(screen.getByRole("button", { name: "dry run" }));
    fireEvent.click(screen.getByRole("button", { name: "cancel" }));
    fireEvent.click(screen.getByRole("button", { name: "error" }));
    expect(onEnrolled).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "enrollment success" }));
    expect(onEnrolled).toHaveBeenCalledTimes(1);
  });
});

