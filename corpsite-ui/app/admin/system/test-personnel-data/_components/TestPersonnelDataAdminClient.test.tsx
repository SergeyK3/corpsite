import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TestPersonnelDataAdminClient from "./TestPersonnelDataAdminClient";
import type { MeInfo } from "@/lib/types";
import type { TestPersonnelRequest, TestPersonnelTarget } from "@/lib/testPersonnelDeletion";

let currentUser: MeInfo | null = null;

vi.mock("@/lib/currentUser", () => ({ useCurrentUser: () => currentUser }));
vi.mock("@/lib/testPersonnelDeletion", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/testPersonnelDeletion")>();
  return {
    ...actual,
    previewTestPersonnel: vi.fn(),
    createTestPersonnelDeletionRequest: vi.fn(),
    listTestPersonnelDeletionRequests: vi.fn(),
    getTestPersonnelDeletionRequest: vi.fn(),
    submitTestPersonnelDeletionRequest: vi.fn(),
    cancelTestPersonnelDeletionRequest: vi.fn(),
  };
});

import {
  cancelTestPersonnelDeletionRequest,
  createTestPersonnelDeletionRequest,
  getTestPersonnelDeletionRequest,
  listTestPersonnelDeletionRequests,
  previewTestPersonnel,
  submitTestPersonnelDeletionRequest,
} from "@/lib/testPersonnelDeletion";

const allowedTarget: TestPersonnelTarget = {
  target_type: "APPLICANT", person_id: 10, application_id: 20,
  subject: "Тестовый Пользователь", masked_iin: "********1234",
  eligibility_status: "TOMBSTONE_REQUIRED",
  stage_admissibility: { create: true, submit: true, approve: true, future_execution: false },
  blocking_codes: [], tombstone_required_codes: ["PPR_EVENT_TOMBSTONE_REQUIRED"],
  hr_attestation_codes: [], informational_codes: [],
};

const blockedTarget: TestPersonnelTarget = {
  ...allowedTarget, person_id: 11, application_id: 21, subject: "Заблокированная запись",
  eligibility_status: "BLOCKED", blocking_codes: ["LEGACY_PERSONNEL_PRESENT"],
  tombstone_required_codes: [], stage_admissibility: { create: false, submit: false, approve: false, future_execution: false },
};

function request(status = "DRAFT", version = 1): TestPersonnelRequest {
  return {
    request_id: "request-1", request_number: "TD-0001", status, version,
    reason_code: "LEGACY_SYNTHETIC_TEST_DATA", basis: "LEGACY_MANIFEST",
    initiated_by_user_id: 1, initiated_by_display_name: "Администратор",
    target_set_hash: "abcdef1234567890", relationship_fingerprint: "f".repeat(64),
    created_at: "2026-09-04T10:00:00Z", expires_at: "2026-09-05T10:00:00Z",
    targets: [allowedTarget], decisions: [],
  };
}

beforeEach(() => {
  currentUser = { user_id: 1, can_request_test_personnel_deletion: true };
  vi.mocked(listTestPersonnelDeletionRequests).mockReset().mockResolvedValue([]);
  vi.mocked(previewTestPersonnel).mockReset();
  vi.mocked(createTestPersonnelDeletionRequest).mockReset();
  vi.mocked(getTestPersonnelDeletionRequest).mockReset();
  vi.mocked(submitTestPersonnelDeletionRequest).mockReset();
  vi.mocked(cancelTestPersonnelDeletionRequest).mockReset();
});

afterEach(cleanup);

describe("TestPersonnelDataAdminClient", () => {
  it("is capability-gated and does not admit HR_HEAD approval-only capability", () => {
    currentUser = { user_id: 2, can_approve_test_personnel_deletion: true };
    render(<TestPersonnelDataAdminClient />);
    expect(screen.queryByTestId("test-personnel-admin-panel")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Недостаточно прав");
  });

  it("previews masked identity, permits manual selection, and disables BLOCK", async () => {
    vi.mocked(previewTestPersonnel).mockResolvedValue({ items: [allowedTarget, blockedTarget], count: 2 });
    render(<TestPersonnelDataAdminClient />);
    fireEvent.change(screen.getByLabelText("Маска отображаемого имени"), { target: { value: "Тестовый*" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    expect(await screen.findAllByText("********1234")).toHaveLength(2);
    expect(screen.getByText("BLOCK — выбор запрещён")).toBeInTheDocument();
    expect(screen.getByLabelText("Выбрать Заблокированная запись")).toBeDisabled();
    expect(screen.queryByText(/990101123456/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Выбрать Тестовый Пользователь"));
    expect(screen.getByRole("button", { name: "Создать запрос на удаление" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /Выполнить удаление/ })).not.toBeInTheDocument();
  });

  it("creates an exact request and submits current version with idempotency", async () => {
    vi.mocked(previewTestPersonnel).mockResolvedValue({ items: [allowedTarget], count: 1 });
    vi.mocked(createTestPersonnelDeletionRequest).mockResolvedValue(request());
    vi.mocked(getTestPersonnelDeletionRequest)
      .mockResolvedValueOnce(request())
      .mockResolvedValueOnce(request("PENDING_HR_APPROVAL", 2));
    vi.mocked(submitTestPersonnelDeletionRequest).mockResolvedValue(request("PENDING_HR_APPROVAL", 2));
    render(<TestPersonnelDataAdminClient />);
    fireEvent.change(screen.getByLabelText("Маска отображаемого имени"), { target: { value: "Тестовый*" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    fireEvent.click(await screen.findByLabelText("Выбрать Тестовый Пользователь"));
    fireEvent.click(screen.getByRole("button", { name: "Создать запрос на удаление" }));
    await screen.findByText(/Точный manifest TD-0001/);
    expect(createTestPersonnelDeletionRequest).toHaveBeenCalledWith(expect.objectContaining({
      original_mask: "Тестовый*", targets: [{ person_id: 10, application_id: 20 }],
      idempotency_key: expect.stringMatching(/^wp-td-003-create-/),
    }));
    fireEvent.click(screen.getByRole("button", { name: "Отправить на согласование" }));
    await waitFor(() => expect(submitTestPersonnelDeletionRequest).toHaveBeenCalledWith(
      "request-1", 1, expect.stringMatching(/^wp-td-003-submit-/),
    ));
  });

  it("cancels with current version", async () => {
    vi.mocked(listTestPersonnelDeletionRequests).mockResolvedValue([request()]);
    vi.mocked(getTestPersonnelDeletionRequest)
      .mockResolvedValueOnce(request())
      .mockResolvedValueOnce(request("CANCELLED", 2));
    vi.mocked(cancelTestPersonnelDeletionRequest).mockResolvedValue(request("CANCELLED", 2));
    render(<TestPersonnelDataAdminClient />);
    fireEvent.click(await screen.findByRole("button", { name: /TD-0001/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Отменить запрос" }));
    await waitFor(() => expect(cancelTestPersonnelDeletionRequest).toHaveBeenCalledWith(
      "request-1", 1, expect.stringMatching(/^wp-td-003-cancel-/),
    ));
  });

  it("shows approval participant, comment, target count, hash and validity", async () => {
    const approved = {
      ...request("APPROVED", 3), approval_expires_at: "2026-09-06T10:00:00Z",
      decisions: [{
        decision_id: 7, decision: "APPROVE" as const, actor_user_id: 2,
        actor_display_name: "Руководитель кадров", comment: "Подтверждено",
        submitted_synthetic_confirmed: true, decided_at: "2026-09-04T11:00:00Z",
      }],
    };
    vi.mocked(listTestPersonnelDeletionRequests).mockResolvedValue([approved]);
    vi.mocked(getTestPersonnelDeletionRequest).mockResolvedValue(approved);
    render(<TestPersonnelDataAdminClient />);
    fireEvent.click(await screen.findByRole("button", { name: /TD-0001/ }));
    expect(await screen.findByText("Удаление одобрено руководителем отдела кадров")).toBeInTheDocument();
    expect(screen.getByText(/Руководитель кадров/)).toBeInTheDocument();
    expect(screen.getByText(/Подтверждено/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Выполнить удаление/ })).not.toBeInTheDocument();
  });

  it.each(["EXPIRED", "REAPPROVAL_REQUIRED"])("renders explicit %s state", async (status) => {
    vi.mocked(listTestPersonnelDeletionRequests).mockResolvedValue([request(status)]);
    vi.mocked(getTestPersonnelDeletionRequest).mockResolvedValue(request(status));
    render(<TestPersonnelDataAdminClient />);
    fireEvent.click(await screen.findByRole("button", { name: /TD-0001/ }));
    expect(await screen.findByText(
      status === "EXPIRED" ? /Срок согласования истёк/ : /Требуется повторное согласование/,
    )).toBeInTheDocument();
  });

  it("suppresses a duplicate create click while command is pending", async () => {
    vi.mocked(previewTestPersonnel).mockResolvedValue({ items: [allowedTarget], count: 1 });
    let resolveCreate!: (value: TestPersonnelRequest) => void;
    vi.mocked(createTestPersonnelDeletionRequest).mockReturnValue(new Promise((resolve) => { resolveCreate = resolve; }));
    vi.mocked(getTestPersonnelDeletionRequest).mockResolvedValue(request());
    render(<TestPersonnelDataAdminClient />);
    fireEvent.change(screen.getByLabelText("Маска отображаемого имени"), { target: { value: "Тестовый*" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    fireEvent.click(await screen.findByLabelText("Выбрать Тестовый Пользователь"));
    const create = screen.getByRole("button", { name: "Создать запрос на удаление" });
    fireEvent.click(create);
    fireEvent.click(create);
    expect(createTestPersonnelDeletionRequest).toHaveBeenCalledTimes(1);
    resolveCreate(request());
    await screen.findByText(/Точный manifest/);
  });

  it("reuses the create idempotency key after a transport failure", async () => {
    vi.mocked(previewTestPersonnel).mockResolvedValue({ items: [allowedTarget], count: 1 });
    vi.mocked(createTestPersonnelDeletionRequest)
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(request());
    vi.mocked(getTestPersonnelDeletionRequest).mockResolvedValue(request());
    render(<TestPersonnelDataAdminClient />);
    const maskInput = screen.getByLabelText("Маска отображаемого имени");
    fireEvent.change(maskInput, { target: { value: "Тестовый*" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    fireEvent.click(await screen.findByLabelText("Выбрать Тестовый Пользователь"));
    const create = screen.getByRole("button", { name: "Создать запрос на удаление" });
    fireEvent.click(create);
    expect(await screen.findByRole("alert")).toHaveTextContent("Не удалось связаться с сервером");
    fireEvent.click(screen.getByRole("button", { name: "Создать запрос на удаление" }));
    await screen.findByText(/Точный manifest/);
    const firstKey = vi.mocked(createTestPersonnelDeletionRequest).mock.calls[0][0].idempotency_key;
    const retryKey = vi.mocked(createTestPersonnelDeletionRequest).mock.calls[1][0].idempotency_key;
    expect(retryKey).toBe(firstKey);
  });

  it("invalidates old preview and selection when the mask changes", async () => {
    vi.mocked(previewTestPersonnel).mockResolvedValue({ items: [allowedTarget], count: 1 });
    render(<TestPersonnelDataAdminClient />);
    const maskInput = screen.getByLabelText("Маска отображаемого имени");
    fireEvent.change(maskInput, { target: { value: "Тестовый*" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    fireEvent.click(await screen.findByLabelText("Выбрать Тестовый Пользователь"));
    expect(screen.getByRole("button", { name: "Создать запрос на удаление" })).toBeEnabled();
    fireEvent.change(maskInput, { target: { value: "Другая*" } });
    expect(screen.queryByText("Тестовый Пользователь")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Создать запрос на удаление" })).toBeDisabled();
  });

  it("ignores an obsolete preview response", async () => {
    let resolveOld!: (value: { items: TestPersonnelTarget[]; count: number }) => void;
    let resolveNew!: (value: { items: TestPersonnelTarget[]; count: number }) => void;
    vi.mocked(previewTestPersonnel)
      .mockReturnValueOnce(new Promise((resolve) => { resolveOld = resolve; }))
      .mockReturnValueOnce(new Promise((resolve) => { resolveNew = resolve; }));
    render(<TestPersonnelDataAdminClient />);
    const maskInput = screen.getByLabelText("Маска отображаемого имени");
    fireEvent.change(maskInput, { target: { value: "Старая*" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    fireEvent.change(maskInput, { target: { value: "Новая*" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    const newTarget = { ...allowedTarget, person_id: 12, application_id: 22, subject: "Новая запись" };
    resolveNew({ items: [newTarget], count: 1 });
    expect(await screen.findByText("Новая запись")).toBeInTheDocument();
    resolveOld({ items: [allowedTarget], count: 1 });
    await waitFor(() => expect(screen.queryByText("Тестовый Пользователь")).not.toBeInTheDocument());
  });

  it("refreshes detail after a 409 transition to reapproval", async () => {
    vi.mocked(listTestPersonnelDeletionRequests).mockResolvedValue([request()]);
    vi.mocked(getTestPersonnelDeletionRequest)
      .mockResolvedValueOnce(request())
      .mockResolvedValueOnce(request("REAPPROVAL_REQUIRED", 2));
    vi.mocked(submitTestPersonnelDeletionRequest).mockRejectedValue(
      Object.assign(new Error("conflict"), { status: 409 }),
    );
    render(<TestPersonnelDataAdminClient />);
    fireEvent.click(await screen.findByRole("button", { name: /TD-0001/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Отправить на согласование" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Требуется повторное согласование");
    expect(screen.getByRole("alert")).toHaveTextContent("Данные запроса изменились");
  });

  it.each([
    [403, "Недостаточно прав"], [409, "Данные запроса изменились"],
    [410, "Операция отключена"], [422, "Проверьте заполнение"],
  ])("handles HTTP %s", async (status, message) => {
    vi.mocked(previewTestPersonnel).mockRejectedValue(Object.assign(new Error("api"), { status }));
    render(<TestPersonnelDataAdminClient />);
    fireEvent.change(screen.getByLabelText("Маска отображаемого имени"), { target: { value: "Тестовый*" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });
});
