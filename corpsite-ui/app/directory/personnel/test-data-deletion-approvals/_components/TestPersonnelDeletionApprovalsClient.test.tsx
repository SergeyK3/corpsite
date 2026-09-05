import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TestPersonnelDeletionApprovalsClient from "./TestPersonnelDeletionApprovalsClient";
import type { MeInfo } from "@/lib/types";
import type { TestPersonnelRequest, TestPersonnelTarget } from "@/lib/testPersonnelDeletion";

let currentUser: MeInfo | null = null;

vi.mock("@/lib/currentUser", () => ({ useCurrentUser: () => currentUser }));
vi.mock("@/lib/testPersonnelDeletion", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/testPersonnelDeletion")>();
  return {
    ...actual,
    listTestPersonnelDeletionApprovals: vi.fn(),
    getTestPersonnelDeletionApproval: vi.fn(),
    approveTestPersonnelDeletionRequest: vi.fn(),
    rejectTestPersonnelDeletionRequest: vi.fn(),
  };
});

import {
  approveTestPersonnelDeletionRequest,
  getTestPersonnelDeletionApproval,
  listTestPersonnelDeletionApprovals,
  rejectTestPersonnelDeletionRequest,
} from "@/lib/testPersonnelDeletion";

const target: TestPersonnelTarget = {
  target_type: "APPLICANT", person_id: 10, application_id: 20,
  subject: "Синтетический кандидат", masked_iin: "********1234",
  eligibility_status: "HR_ATTESTATION_REQUIRED",
  blocking_codes: [], tombstone_required_codes: ["PPR_EVENT_TOMBSTONE_REQUIRED"],
  hr_attestation_codes: ["SUBMITTED_SYNTHETIC_CONFIRMATION_REQUIRED"], informational_codes: [],
  requires_hr_synthetic_confirmation: true,
};

function pending(): TestPersonnelRequest {
  return {
    request_id: "request-2", request_number: "TD-0002", status: "PENDING_HR_APPROVAL", version: 2,
    reason_code: "LEGACY_SYNTHETIC_TEST_DATA", basis: "LEGACY_MANIFEST",
    initiated_by_user_id: 1, initiated_by_display_name: "Системный администратор",
    target_set_hash: "1234567890abcdef", relationship_fingerprint: "a".repeat(64),
    created_at: "2026-09-04T10:00:00Z", expires_at: "2026-09-05T10:00:00Z",
    targets: [target], decisions: [],
  };
}

beforeEach(() => {
  currentUser = { user_id: 2, can_approve_test_personnel_deletion: true };
  vi.mocked(listTestPersonnelDeletionApprovals).mockReset().mockResolvedValue([pending()]);
  vi.mocked(getTestPersonnelDeletionApproval).mockReset().mockResolvedValue(pending());
  vi.mocked(approveTestPersonnelDeletionRequest).mockReset().mockResolvedValue({ ...pending(), status: "APPROVED", version: 3 });
  vi.mocked(rejectTestPersonnelDeletionRequest).mockReset().mockResolvedValue({ ...pending(), status: "REJECTED", version: 3 });
});

afterEach(cleanup);

describe("TestPersonnelDeletionApprovalsClient", () => {
  it("is capability-gated and does not admit ADMIN request-only capability", () => {
    currentUser = { user_id: 1, can_request_test_personnel_deletion: true };
    render(<TestPersonnelDeletionApprovalsClient />);
    expect(screen.queryByTestId("test-personnel-approvals-panel")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Недостаточно прав");
  });

  it("shows queue, exact manifest, masked identity, initiator and no execution action", async () => {
    render(<TestPersonnelDeletionApprovalsClient />);
    const row = await screen.findByRole("button", { name: /TD-0002/ });
    expect(row).toHaveTextContent("Системный администратор");
    fireEvent.click(row);
    expect(await screen.findByText("Синтетический кандидат")).toBeInTheDocument();
    expect(screen.getByText("********1234")).toBeInTheDocument();
    expect(screen.queryByText(/990101123456/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Выполнить удаление/ })).not.toBeInTheDocument();
  });

  it("requires attestation for approval and sends current version, comment and idempotency", async () => {
    vi.mocked(getTestPersonnelDeletionApproval)
      .mockResolvedValueOnce(pending())
      .mockResolvedValueOnce({ ...pending(), status: "APPROVED", version: 3 });
    render(<TestPersonnelDeletionApprovalsClient />);
    fireEvent.click(await screen.findByRole("button", { name: /TD-0002/ }));
    const approve = await screen.findByRole("button", { name: "Одобрить удаление" });
    expect(approve).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/Подтверждаю, что записи/));
    fireEvent.change(screen.getByLabelText(/Безопасный комментарий/), { target: { value: "Синтетический набор подтверждён" } });
    fireEvent.click(approve);
    await waitFor(() => expect(approveTestPersonnelDeletionRequest).toHaveBeenCalledWith("request-2", {
      version: 2, idempotencyKey: expect.stringMatching(/^wp-td-003-approve-/), comment: "Синтетический набор подтверждён",
      submittedSyntheticConfirmed: true,
    }));
  });

  it("rejects without attestation", async () => {
    vi.mocked(getTestPersonnelDeletionApproval)
      .mockResolvedValueOnce(pending())
      .mockResolvedValueOnce({ ...pending(), status: "REJECTED", version: 3 });
    render(<TestPersonnelDeletionApprovalsClient />);
    fireEvent.click(await screen.findByRole("button", { name: /TD-0002/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Отклонить" }));
    await waitFor(() => expect(rejectTestPersonnelDeletionRequest).toHaveBeenCalledWith("request-2", {
      version: 2, idempotencyKey: expect.stringMatching(/^wp-td-003-reject-/), comment: "", submittedSyntheticConfirmed: false,
    }));
  });

  it("suppresses duplicate approval while request is pending", async () => {
    let resolveApproval!: (value: TestPersonnelRequest) => void;
    vi.mocked(approveTestPersonnelDeletionRequest).mockReturnValue(new Promise((resolve) => { resolveApproval = resolve; }));
    render(<TestPersonnelDeletionApprovalsClient />);
    fireEvent.click(await screen.findByRole("button", { name: /TD-0002/ }));
    fireEvent.click(await screen.findByLabelText(/Подтверждаю, что записи/));
    const approve = screen.getByRole("button", { name: "Одобрить удаление" });
    fireEvent.click(approve);
    fireEvent.click(approve);
    expect(approveTestPersonnelDeletionRequest).toHaveBeenCalledTimes(1);
    resolveApproval({ ...pending(), status: "APPROVED", version: 3 });
    await waitFor(() => expect(getTestPersonnelDeletionApproval).toHaveBeenCalledTimes(2));
  });

  it("reuses the approval idempotency key after a transport failure", async () => {
    vi.mocked(approveTestPersonnelDeletionRequest)
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce({ ...pending(), status: "APPROVED", version: 3 });
    render(<TestPersonnelDeletionApprovalsClient />);
    fireEvent.click(await screen.findByRole("button", { name: /TD-0002/ }));
    fireEvent.click(await screen.findByLabelText(/Подтверждаю, что записи/));
    fireEvent.click(screen.getByRole("button", { name: "Одобрить удаление" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Не удалось связаться с сервером");
    fireEvent.click(screen.getByRole("button", { name: "Одобрить удаление" }));
    await waitFor(() => expect(approveTestPersonnelDeletionRequest).toHaveBeenCalledTimes(2));
    const firstKey = vi.mocked(approveTestPersonnelDeletionRequest).mock.calls[0][1].idempotencyKey;
    const retryKey = vi.mocked(approveTestPersonnelDeletionRequest).mock.calls[1][1].idempotencyKey;
    expect(retryKey).toBe(firstKey);
  });

  it("prevents switching requests while a detail response is pending", async () => {
    const second = { ...pending(), request_id: "request-3", request_number: "TD-0003" };
    vi.mocked(listTestPersonnelDeletionApprovals).mockResolvedValue([pending(), second]);
    let resolveDetail!: (value: TestPersonnelRequest) => void;
    vi.mocked(getTestPersonnelDeletionApproval).mockReturnValue(new Promise((resolve) => { resolveDetail = resolve; }));
    render(<TestPersonnelDeletionApprovalsClient />);
    const firstButton = await screen.findByRole("button", { name: /TD-0002/ });
    const secondButton = screen.getByRole("button", { name: /TD-0003/ });
    fireEvent.click(firstButton);
    expect(secondButton).toBeDisabled();
    fireEvent.click(secondButton);
    expect(getTestPersonnelDeletionApproval).toHaveBeenCalledTimes(1);
    resolveDetail(pending());
    expect(await screen.findByText("Синтетический кандидат")).toBeInTheDocument();
  });

  it("refreshes detail after a 409 transition to expired", async () => {
    vi.mocked(getTestPersonnelDeletionApproval)
      .mockResolvedValueOnce(pending())
      .mockResolvedValueOnce({ ...pending(), status: "EXPIRED", version: 3 });
    vi.mocked(approveTestPersonnelDeletionRequest).mockRejectedValue(
      Object.assign(new Error("conflict"), { status: 409 }),
    );
    render(<TestPersonnelDeletionApprovalsClient />);
    fireEvent.click(await screen.findByRole("button", { name: /TD-0002/ }));
    fireEvent.click(await screen.findByLabelText(/Подтверждаю, что записи/));
    fireEvent.click(screen.getByRole("button", { name: "Одобрить удаление" }));
    expect(await screen.findByText(/Срок согласования истёк/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Одобрить удаление" })).not.toBeInTheDocument();
  });
});
