import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { IncomingDocumentDetail } from "../_lib/types";

const { getIncomingDocumentMock, replaceMock } = vi.hoisted(() => ({
  getIncomingDocumentMock: vi.fn(),
  replaceMock: vi.fn(),
}));

const routerMock = { replace: replaceMock };

vi.mock("next/navigation", () => ({ useRouter: () => routerMock }));

vi.mock("../_lib/api.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/api.client")>("../_lib/api.client");
  return { ...actual, getIncomingDocument: getIncomingDocumentMock };
});

import IncomingDocumentDetailPageClient from "./IncomingDocumentDetailPageClient";

const detail: IncomingDocumentDetail = {
  incoming_document_id: 42,
  registration_number: "ВХ-2026-0042",
  registration_year: 2026,
  registration_seq: 42,
  received_at: "2026-08-04",
  registered_at: "2026-08-05T10:00:00Z",
  document_type_id: 1,
  document_type_code: "LETTER",
  document_type_label: "Письмо",
  receipt_channel_id: 1,
  receipt_channel_code: "EMAIL",
  receipt_channel_label: "Электронная почта",
  status_id: 1,
  status_code: "REGISTERED",
  status_label: "Зарегистрировано",
  status_is_terminal: false,
  planned_result_id: null,
  planned_result_code: null,
  planned_result_label: null,
  summary: "Краткое содержание документа",
  access_level: "NORMAL",
  sender_kind: "EXTERNAL_TEXT",
  sender_person_id: null,
  sender_employee_id: null,
  sender_org_unit_id: null,
  sender_text: "ТОО Отправитель",
  addressee_kind: "ORG_UNIT",
  addressee_user_id: null,
  addressee_employee_id: null,
  addressee_org_unit_id: 7,
  addressee_position_id: null,
  addressee_text: null,
  registration_org_unit_id: 2,
  responsible_org_unit_id: 7,
  resolution_text: null,
  due_date: null,
  planned_result_note: null,
  executed_at: null,
  execution_result: null,
  closed_at: null,
  note: null,
  priority_level: null,
  is_control_document: false,
  received_after_registration_exception: false,
  exception_comment: null,
  transfer_comment: null,
  cancellation_reason: null,
  control_decision: null,
  control_comment: null,
  controller_user_id: null,
  row_version: 1,
  closed_by_user_id: null,
  cancelled_at: null,
  cancelled_by_user_id: null,
  transferred_at: null,
  transferred_by_user_id: null,
  resolve_recorded_at: null,
  reopened_at: null,
  reopen_reason: null,
  reopen_count: 0,
  external_recipient_kind: null,
  external_recipient_user_id: null,
  external_recipient_org_unit_id: null,
  external_recipient_text: null,
  created_by_user_id: 1,
  updated_by_user_id: null,
  created_at: "2026-08-05T10:00:00Z",
  updated_at: "2026-08-05T10:00:00Z",
  is_overdue: false,
};

describe("IncomingDocumentDetailPageClient", () => {
  beforeEach(() => {
    replaceMock.mockReset();
    getIncomingDocumentMock.mockReset();
    getIncomingDocumentMock.mockResolvedValue(detail);
  });

  afterEach(() => cleanup());

  it("shows loading while detail request is pending", () => {
    getIncomingDocumentMock.mockReturnValue(new Promise(() => undefined));
    render(<IncomingDocumentDetailPageClient documentId="42" />);
    expect(screen.getByTestId("incoming-document-loading")).toBeInTheDocument();
  });

  it("renders factual read-only detail fields", async () => {
    render(<IncomingDocumentDetailPageClient documentId="42" />);
    expect(await screen.findByTestId("incoming-document-detail")).toBeInTheDocument();
    expect(screen.getAllByText("ВХ-2026-0042").length).toBeGreaterThan(0);
    expect(screen.getByText("Краткое содержание документа")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /назначить|закрыть|изменить/i })).not.toBeInTheDocument();
  });

  it("redirects to login on 401", async () => {
    getIncomingDocumentMock.mockRejectedValue({ status: 401 });
    render(<IncomingDocumentDetailPageClient documentId="42" />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });

  it("renders separate 403 and 404 states", async () => {
    getIncomingDocumentMock.mockRejectedValueOnce({ status: 403 });
    const first = render(<IncomingDocumentDetailPageClient documentId="42" />);
    expect(await screen.findByTestId("incoming-document-forbidden")).toBeInTheDocument();
    first.unmount();

    getIncomingDocumentMock.mockRejectedValueOnce({ status: 404 });
    render(<IncomingDocumentDetailPageClient documentId="43" />);
    expect(await screen.findByTestId("incoming-document-not-found")).toHaveTextContent("не найден");
  });

  it("rejects invalid document ID without an API request", async () => {
    render(<IncomingDocumentDetailPageClient documentId="not-a-number" />);
    expect(await screen.findByTestId("incoming-document-not-found")).toHaveTextContent(
      "Некорректный идентификатор",
    );
    expect(getIncomingDocumentMock).not.toHaveBeenCalled();
  });

  it("renders generic error and retries", async () => {
    getIncomingDocumentMock
      .mockRejectedValueOnce(new Error("Сеть недоступна"))
      .mockResolvedValueOnce(detail);
    render(<IncomingDocumentDetailPageClient documentId="42" />);
    expect(await screen.findByTestId("incoming-document-error")).toHaveTextContent("Сеть недоступна");
    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));
    expect(await screen.findByTestId("incoming-document-detail")).toBeInTheDocument();
    expect(getIncomingDocumentMock).toHaveBeenCalledTimes(2);
  });
});
