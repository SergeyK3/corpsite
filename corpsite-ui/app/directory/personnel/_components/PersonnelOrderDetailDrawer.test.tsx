import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    generatePersonnelOrderEditorial: vi.fn(async () => ({
      order_id: 42,
      order_status: "DRAFT",
      editable: true,
      order_blocks: [],
      items: [],
    })),
  };
});

import { getPersonnelOrder, getPersonnelOrderEditorial } from "../_lib/personnelOrdersApi.client";

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
