import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { listIncomingDocumentsMock, pushMock, replaceMock } = vi.hoisted(() => ({
  listIncomingDocumentsMock: vi.fn(),
  pushMock: vi.fn(),
  replaceMock: vi.fn(),
}));

let currentSearchParams = new URLSearchParams();
const routerMock = { push: pushMock, replace: replaceMock };

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  useSearchParams: () => currentSearchParams,
}));

vi.mock("../_lib/api.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/api.client")>("../_lib/api.client");
  return { ...actual, listIncomingDocuments: listIncomingDocumentsMock };
});

import IncomingInformationPageClient from "./IncomingInformationPageClient";

const item = {
  incoming_document_id: 42,
  registration_number: "ВХ-2026-0042",
  registered_at: "2026-08-05T10:00:00Z",
  document_type_label: "Письмо",
  summary: "Краткое содержание документа",
  sender_display: "ТОО Отправитель",
  addressee_display: "Подразделение",
  primary_executor_display: "Иванов И.И.",
  due_date: "2026-08-01",
  status_code: "IN_PROGRESS",
  status_label: "В работе",
  access_level: "NORMAL",
  responsible_org_unit_id: 7,
  is_overdue: true,
};

function response(items = [item], total = items.length, offset = 0) {
  return { items, total, limit: 25, offset };
}

describe("IncomingInformationPageClient", () => {
  beforeEach(() => {
    currentSearchParams = new URLSearchParams();
    pushMock.mockReset();
    replaceMock.mockReset();
    listIncomingDocumentsMock.mockReset();
    listIncomingDocumentsMock.mockResolvedValue(response([], 0));
  });

  afterEach(() => cleanup());

  it("shows loading while the request is pending", () => {
    listIncomingDocumentsMock.mockReturnValue(new Promise(() => undefined));
    render(<IncomingInformationPageClient />);
    expect(screen.getByTestId("incoming-information-loading")).toBeInTheDocument();
  });

  it("renders populated rows, backend overdue flag and detail link", async () => {
    listIncomingDocumentsMock.mockResolvedValue(response([item], 1));
    render(<IncomingInformationPageClient />);

    expect(await screen.findByTestId("incoming-information-table")).toBeInTheDocument();
    expect(screen.getByText("Краткое содержание документа")).toBeInTheDocument();
    expect(screen.getByTestId("incoming-information-overdue-42")).toHaveTextContent("Просрочено");
    expect(screen.getByRole("link", { name: "ВХ-2026-0042" })).toHaveAttribute(
      "href",
      "/directory/incoming-information/documents/42",
    );
  });

  it("renders an explicit empty state", async () => {
    render(<IncomingInformationPageClient />);
    expect(await screen.findByTestId("incoming-information-empty")).toHaveTextContent(
      "Доступных входящих документов нет",
    );
  });

  it("redirects to login on 401", async () => {
    listIncomingDocumentsMock.mockRejectedValue({ status: 401 });
    render(<IncomingInformationPageClient />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });

  it("renders a separate forbidden state on 403", async () => {
    listIncomingDocumentsMock.mockRejectedValue({ status: 403 });
    render(<IncomingInformationPageClient />);
    expect(await screen.findByTestId("incoming-information-forbidden")).toHaveTextContent(
      "Нет доступа к реестру",
    );
  });

  it("renders network error and retries", async () => {
    listIncomingDocumentsMock
      .mockRejectedValueOnce(new Error("Сеть недоступна"))
      .mockResolvedValueOnce(response([item], 1));
    render(<IncomingInformationPageClient />);

    expect(await screen.findByTestId("incoming-information-error")).toHaveTextContent("Сеть недоступна");
    fireEvent.click(screen.getByRole("button", { name: "Повторить" }));
    expect(await screen.findByTestId("incoming-information-table")).toBeInTheDocument();
    expect(listIncomingDocumentsMock).toHaveBeenCalledTimes(2);
  });

  it("uses offset from URL and pushes pagination history entries", async () => {
    currentSearchParams = new URLSearchParams("offset=25");
    listIncomingDocumentsMock.mockResolvedValue(response([item], 60, 25));
    render(<IncomingInformationPageClient />);

    await screen.findByTestId("incoming-information-table");
    expect(listIncomingDocumentsMock).toHaveBeenCalledWith({ limit: 25, offset: 25 });
    fireEvent.click(screen.getByTestId("incoming-information-page-prev"));
    fireEvent.click(screen.getByTestId("incoming-information-page-next"));
    expect(pushMock).toHaveBeenNthCalledWith(1, "/directory/incoming-information");
    expect(pushMock).toHaveBeenNthCalledWith(2, "/directory/incoming-information?offset=50");
  });

  it("normalizes an invalid or negative URL offset without sending it to backend", async () => {
    currentSearchParams = new URLSearchParams("offset=-25");
    render(<IncomingInformationPageClient />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/directory/incoming-information");
      expect(listIncomingDocumentsMock).toHaveBeenCalledWith({ limit: 25, offset: 0 });
    });
  });
});
