import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelOrderDetailDrawer from "./PersonnelOrderDetailDrawer";
import type { PersonnelOrderDetailResponse } from "../_lib/personnelOrdersApi.client";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/directory/personnel/orders",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/components/OrgScopeFilter", () => ({
  default: () => <div data-testid="mock-org-scope-filter" />,
}));

vi.mock("@/app/directory/employees/_lib/api.client", () => ({
  getEmployees: vi.fn(async () => ({ items: [] })),
}));

vi.mock("@/lib/taskOrgFilters", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/taskOrgFilters")>();
  return {
    ...actual,
    loadScopedPositionOptions: vi.fn(async () => []),
  };
});

vi.mock("../_lib/personnelOrdersApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelOrdersApi.client")>(
    "../_lib/personnelOrdersApi.client",
  );
  return {
    ...actual,
    getPersonnelOrder: vi.fn(),
    getPersonnelOrderEditorial: vi.fn(async () => ({
      order_id: 42,
      order_status: "DRAFT",
      editable: true,
      order_blocks: [],
      items: [],
    })),
    getPersonnelOrderDocumentReview: vi.fn(async () => ({
      state: "NEEDS_REVIEW", document_revision: 1, blockers: [], warnings: [], allowed_actions: ["confirm"],
    })),
    confirmPersonnelOrderDocumentReview: vi.fn(async () => ({
      state: "CONFIRMED", document_revision: 2, blockers: [], warnings: [], allowed_actions: ["reopen"],
    })),
    reopenPersonnelOrderDocumentReview: vi.fn(async () => ({
      state: "NEEDS_REVIEW", document_revision: 3, blockers: [], warnings: [], allowed_actions: ["confirm"],
    })),
    previewPersonnelOrderHeaderDuplicate: vi.fn(async () => ({ blocking: false, warnings: [], candidates: [] })),
    patchPersonnelOrderDocumentHeader: vi.fn(async () => ({ no_op: false, resulting_document_revision: 2 })),
    listPersonnelOrderDocumentItems: vi.fn(async () => ({ document_revision: 1, items: [{ item_id: 9, item_number: 1, item_type_code: "HIRE", employee_id: 7, employee_name: "Test employee", effective_date: "2026-09-02" }] })),
    patchPersonnelOrderDocumentItem: vi.fn(async () => ({ no_op: false, resulting_document_revision: 2, header_type_code: "TRANSFER" })),
    generatePersonnelOrderEditorial: vi.fn(async () => ({
      order_id: 42,
      order_status: "DRAFT",
      editable: true,
      order_blocks: [],
      items: [],
    })),
  };
});

import { getPersonnelOrder, getPersonnelOrderEditorial, getPersonnelOrderDocumentReview, confirmPersonnelOrderDocumentReview, reopenPersonnelOrderDocumentReview, patchPersonnelOrderDocumentHeader, listPersonnelOrderDocumentItems, patchPersonnelOrderDocumentItem } from "../_lib/personnelOrdersApi.client";

const detail: PersonnelOrderDetailResponse = {
  order: {
    order_id: 42,
    order_number: "12-К",
    order_date: "2026-07-10",
    order_type_code: "HIRE",
    order_class: "SIMPLE",
    status: "DRAFT",
    source_mode: "PAPER",
    created_by: 1,
  },
  items: [],
  localized_texts: [],
  attachments: [],
  prints: [],
  events: [],
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelOrderDetailDrawer document tab", () => {
  it("opens typed document items without exposing payload and saves only allowed fields", async () => {
    vi.mocked(getPersonnelOrder).mockResolvedValue({ ...detail, order: { ...detail.order, document_revision: 3 } });
    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Пункты" }));
    expect(await screen.findByTestId("personnel-order-document-items")).toBeInTheDocument();
    expect(listPersonnelOrderDocumentItems).toHaveBeenCalledWith(42);
    expect(screen.queryByText(/payload/i)).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Тип пункта 9"), { target: { value: "TRANSFER" } });
    fireEvent.change(screen.getByLabelText("Сотрудник 9"), { target: { value: "8" } });
    fireEvent.change(screen.getByLabelText("Дата действия 9"), { target: { value: "2026-09-03" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить пункт" }));
    await waitFor(() => expect(patchPersonnelOrderDocumentItem).toHaveBeenCalledWith(42, 9, expect.objectContaining({ expected_document_revision: 3, item_type_code: "TRANSFER", employee_id: 8, effective_date: "2026-09-03" })));
  });

  it("opens requisites with current values and sends typed header patch", async () => {
    vi.mocked(getPersonnelOrder).mockResolvedValue({ ...detail, order: { ...detail.order, source_title: "Исходный текст", source_title_locale: "kk", document_revision: 3 } });
    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Реквизиты" }));
    expect(await screen.findByTestId("personnel-order-requisites")).toHaveTextContent("Ревизия документа: 3");
    expect(screen.getByLabelText("Номер приказа")).toHaveValue("12-К");
    fireEvent.change(screen.getByLabelText("Номер приказа"), { target: { value: "13-К" } });
    fireEvent.change(screen.getByLabelText("Исходное название"), { target: { value: "Новое название" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить реквизиты" }));
    await waitFor(() => expect(patchPersonnelOrderDocumentHeader).toHaveBeenCalledWith(42, expect.objectContaining({ expected_document_revision: 3, order_number: "13-К", source_title: "Новое название" })));
  });
  it("keeps document blockers in data and uses revision for confirm", async () => {
    vi.mocked(getPersonnelOrder).mockResolvedValue(detail);
    vi.mocked(getPersonnelOrderDocumentReview).mockResolvedValue({ state: "NEEDS_REVIEW", document_revision: 7, blockers: [{ code: "MISSING_ORDER_NUMBER" }], warnings: [], allowed_actions: ["confirm"] });
    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);
    expect(await screen.findByTestId("personnel-order-document-review-status")).toHaveTextContent("ревизия 7");
    expect(screen.queryByText("MISSING_ORDER_NUMBER")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Данные" }));
    expect(await screen.findByTestId("personnel-order-document-review")).toHaveTextContent("MISSING_ORDER_NUMBER");
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить кадровой службой" }));
    await waitFor(() => expect(confirmPersonnelOrderDocumentReview).toHaveBeenCalledWith(42, { expected_document_revision: 7, reason_code: "HR_DOCUMENT_REVIEW" }));
  });

  it("requires a reopen explanation and sends it with the revision", async () => {
    vi.mocked(getPersonnelOrder).mockResolvedValue(detail);
    vi.mocked(getPersonnelOrderDocumentReview).mockResolvedValue({ state: "CONFIRMED", document_revision: 4, blockers: [], warnings: [], allowed_actions: ["reopen"] });
    const prompt = vi.spyOn(window, "prompt").mockReturnValueOnce("").mockReturnValueOnce("Needs source review");
    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Данные" }));
    fireEvent.click(await screen.findByRole("button", { name: "Вернуть на проверку" }));
    expect(reopenPersonnelOrderDocumentReview).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Вернуть на проверку" }));
    await waitFor(() => expect(reopenPersonnelOrderDocumentReview).toHaveBeenCalledWith(42, { expected_document_revision: 4, reason_code: "HR_DOCUMENT_REOPEN", note: "Needs source review" }));
    prompt.mockRestore();
  });
  it("uses one drawer language switch before actions and keeps it across document, data, and print", async () => {
    vi.mocked(getPersonnelOrder).mockResolvedValue({
      ...detail,
      order: { ...detail.order, order_type_code: "TRANSFER" },
      items: [{
        item_id: 1, order_id: 42, item_number: 1, item_type_code: "TRANSFER", item_status: "ACTIVE", employee_id: 1,
        employee_name: "Иванов Иван", effective_date: "2026-02-01",
        payload: { to_assignment: { unit: { ru: "Отдел", kk: "Бөлім" }, position: { ru: "Медсестра", kk: "мейіргер" }, rate: "1" } },
      }],
    });
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);

    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);

    const switcher = await screen.findByTestId("personnel-order-language-switcher");
    expect(screen.getAllByTestId("personnel-order-language-switcher")).toHaveLength(1);
    expect(screen.queryByTestId("personnel-order-editorial-locale-tabs")).not.toBeInTheDocument();

    fireEvent.click(within(switcher).getByRole("button", { name: "Русский" }));
    expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("ПРИКАЗЫВАЮ:");

    fireEvent.click(screen.getByRole("tab", { name: "Данные" }));
    const editor = await screen.findByTestId("personnel-order-editorial-editor");
    expect(editor).toHaveAttribute("data-active-locale", "ru");
    expect(editor).toHaveTextContent("Редактирование русской версии приказа");
    expect(screen.queryByTestId("personnel-order-editorial-locale-tabs")).not.toBeInTheDocument();
    const actions = screen.getByText("Действия");
    expect(switcher.compareDocumentPosition(actions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    fireEvent.click(screen.getByRole("tab", { name: "Документ" }));
    expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("ПРИКАЗЫВАЮ:");
    fireEvent.click(screen.getByTestId("personnel-order-drawer-print"));
    await waitFor(() => expect(print).toHaveBeenCalled());
    expect(screen.getByTestId("personnel-order-active-print-root")).toHaveTextContent("ПРИКАЗЫВАЮ:");
    fireEvent(window, new Event("afterprint"));

    fireEvent.click(within(switcher).getByRole("button", { name: "Қазақша" }));
    expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("БҰЙЫРАМЫН:");
    fireEvent.click(screen.getByRole("tab", { name: "Данные" }));
    expect(await screen.findByTestId("personnel-order-editorial-editor")).toHaveAttribute("data-active-locale", "kk");
    expect(screen.getByTestId("personnel-order-editorial-editor")).toHaveTextContent("Редактирование казахской версии приказа");
  });

  it("opens the standardized document by default, switches language, and prints it directly", async () => {
    vi.mocked(getPersonnelOrder).mockResolvedValue({
      ...detail,
      order: {
        ...detail.order,
        order_type_code: "COMPOSITE",
        storage_json: { basis_documents: [{ basis_id: "application", document_type: "EMPLOYEE_APPLICATION" }] },
      },
      items: [
        {
          item_id: 1, order_id: 42, item_number: 1, item_type_code: "TRANSFER", item_status: "ACTIVE", employee_id: null, employee_name: null, effective_date: "2026-02-01",
          payload: { employee: { name: { canonical: "Ару Мұратқызы Амантай" } }, to_assignment: { unit: { kk: "қабылдау бөлімшесі" }, position: { kk: "күндізгі мейіргері" }, rate: "1" }, legal_basis: "38", basis_ids: ["application"] },
        },
        {
          item_id: 2, order_id: 42, item_number: 2, item_type_code: "CONCURRENT_DUTY_START", item_status: "ACTIVE", employee_id: null, employee_name: null, effective_date: "2026-02-01",
          payload: { assignment: { unit: { kk: "қабылдау бөлімшесі" }, position: { kk: "күндізгі мейіргері" }, rate: "0.5" }, basis_ids: ["application"] },
        },
      ],
    });
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);

    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("БҰЙЫРАМЫН:");
    });

    expect(screen.getByRole("tab", { name: "Документ" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("button", { name: "Русский" }));
    expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("ПРИКАЗЫВАЮ:");
    fireEvent.click(screen.getByTestId("personnel-order-drawer-print"));
    await waitFor(() => expect(print).toHaveBeenCalled());
    await waitFor(() => {
      expect(document.querySelectorAll("[data-personnel-order-active-print-root]")).toHaveLength(1);
    });
    const printRoot = screen.getByTestId("personnel-order-active-print-root");
    expect(printRoot).toHaveTextContent("ПРИКАЗЫВАЮ:");
    expect(printRoot).not.toHaveTextContent("БҰЙЫРАМЫН:");
    fireEvent.click(screen.getByTestId("personnel-order-drawer-print"));
    expect(document.querySelectorAll("[data-personnel-order-active-print-root]")).toHaveLength(1);
    fireEvent(window, new Event("afterprint"));
    await waitFor(() => {
      expect(screen.queryByTestId("personnel-order-active-print-root")).not.toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: "Қазақша" }));
    fireEvent.click(screen.getByTestId("personnel-order-drawer-print"));
    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-active-print-root")).toHaveTextContent("БҰЙЫРАМЫН:");
    });
  });

  it("rehydrates the production-shaped top-level position override into Russian document and print", async () => {
    const productionDetail: PersonnelOrderDetailResponse = {
      ...detail,
      order: {
        ...detail.order,
        order_id: 405,
        order_number: "1336-ж",
        order_type_code: "TRANSFER",
      },
      items: [{
        item_id: 399,
        order_id: 405,
        item_number: 1,
        item_type_code: "TRANSFER",
        item_status: "ACTIVE",
        employee_id: 77,
        employee_name: "Иванов Иван",
        effective_date: "2026-02-01",
        payload: {
          to_assignment: {
            unit: { ru: "Приемное отделение", kk: "Қабылдау бөлімшесі" },
            position: { ru: "Медсестра", kk: "мейіргер" },
            rate: "1.0",
          },
          position_text_override: { kk: "", ru: "медбрат" },
        },
      }],
    };
    vi.mocked(getPersonnelOrder).mockResolvedValue(productionDetail);
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue({
      order_id: 405,
      order_status: "DRAFT",
      editable: true,
      order_blocks: [],
      items: [{
        order_item_id: 399,
        item_number: 1,
        item_type_code: "TRANSFER",
        basis_required: true,
        blocks: [
          { block_id: 1, scope: "item", order_item_id: 399, locale: "ru", block_type: "body", generated_text: "Перевести Иванова на должность медсестра.", override_text: null, effective_text: "Перевести Иванова на должность медсестра.", review_status: "CURRENT", editable: true, revision: 1 },
          { block_id: 2, scope: "item", order_item_id: 399, locale: "kk", block_type: "body", generated_text: "Автоматты мәтін", override_text: "мейіргер", effective_text: "мейіргер", review_status: "CURRENT", editable: true, revision: 1 },
        ],
      }],
    });
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);

    const { rerender } = render(<PersonnelOrderDetailDrawer orderId={405} open onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Русский" }));
    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("медбрат");
    });
    fireEvent.click(screen.getByTestId("personnel-order-drawer-print"));
    await waitFor(() => expect(print).toHaveBeenCalled());
    expect(screen.getByTestId("personnel-order-active-print-root")).toHaveTextContent("медбрат");
    fireEvent(window, new Event("afterprint"));

    rerender(<PersonnelOrderDetailDrawer orderId={405} open={false} onClose={vi.fn()} />);
    rerender(<PersonnelOrderDetailDrawer orderId={405} open onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Русский" }));
    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("медбрат");
    });
  });

  it("shows archive block for archived orders", async () => {
    vi.mocked(getPersonnelOrder).mockResolvedValue({
      ...detail,
      order: {
        ...detail.order,
        status: "REGISTERED",
        is_archived: true,
        archive_summary_at: "2026-07-12T10:00:00",
        archive_summary_by_name: "Иванова",
        archive_summary_reason: "Перенесён в архив",
      },
    });

    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);

    fireEvent.click(await screen.findByRole("tab", { name: "Данные" }));

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-archive-block")).toBeInTheDocument();
    });
    expect(screen.getByText("Иванова")).toBeInTheDocument();
    expect(screen.getByText("Перенесён в архив")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-archived-badge")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Аннулировать" })).not.toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-drawer-print")).toBeInTheDocument();
  });

  it("shows read-only requisites from saved order header", async () => {
    vi.mocked(getPersonnelOrder).mockResolvedValue({
      ...detail,
      order: {
        ...detail.order,
        status: "REGISTERED",
        order_date: "2026-07-18",
        signed_by_position: "Директор",
        signed_by_name: "М. Тулеутаев",
      },
    });

    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);

    fireEvent.click(await screen.findByRole("tab", { name: "Данные" }));

    await waitFor(() => {
      expect(screen.getByText("Должность подписанта")).toBeInTheDocument();
    });

    expect(screen.getAllByText("М. Тулеутаев").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Директор").length).toBeGreaterThan(0);
    expect(screen.getByText("Дата приказа")).toBeInTheDocument();
    expect(screen.queryByTestId("personnel-order-header-editor")).not.toBeInTheDocument();
  });

  it("shows manual signatory override in read-only header view", async () => {
    vi.mocked(getPersonnelOrder).mockResolvedValue({
      ...detail,
      order: {
        ...detail.order,
        status: "REGISTERED",
        order_date: "2026-07-18",
        signed_by_position: "И. о. директора",
        signed_by_name: "К. Замещающий",
      },
    });

    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);

    fireEvent.click(await screen.findByRole("tab", { name: "Данные" }));

    await waitFor(() => {
      expect(screen.getByText("И. о. директора")).toBeInTheDocument();
    });
    expect(screen.getAllByText("К. Замещающий").length).toBeGreaterThan(0);
    expect(screen.queryByText("М. Тулеутаев")).not.toBeInTheDocument();
  });
});
