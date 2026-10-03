import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelOrderDetailDrawer from "./PersonnelOrderDetailDrawer";
import type { PersonnelOrderDetailResponse } from "../_lib/personnelOrdersApi.client";

const currentUser = vi.hoisted(() => ({ value: null as { role_code?: string } | null }));
const hrHeadDelete = vi.hoisted(() => vi.fn());

vi.mock("@/lib/currentUser", () => ({ useCurrentUser: () => currentUser.value }));

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
    patchPersonnelOrderEditorialBlock: vi.fn(),
    listPersonnelOrderDocumentItems: vi.fn(async () => ({ document_revision: 1, items: [{ item_id: 9, item_number: 1, item_type_code: "HIRE", employee_id: 7, employee_name: "Test employee", position_name: null, org_unit_name: null, specialty: null, needs_employee_link: false, effective_date: "2026-09-02" }] })),
    patchPersonnelOrderDocumentItem: vi.fn(async () => ({ no_op: false, resulting_document_revision: 2, header_type_code: "TRANSFER" })),
    generatePersonnelOrderEditorial: vi.fn(async () => ({
      order_id: 42,
      order_status: "DRAFT",
      editable: true,
      order_blocks: [],
      items: [],
    })),
    previewPersonnelOrderTemplateApplication: vi.fn(async () => ({
      available: true,
      template: { template_version_id: 9, version_number: 2, item_type_code: "TERMINATION" },
      has_overrides: false,
      override_blocks: [],
      has_prior_application: false,
      last_application: null,
      current: {},
      proposed: {},
      order_revision: 1,
    })),
    applyPersonnelOrderTemplateApplication: vi.fn(),
    deletePersonnelOrderAsHrHead: hrHeadDelete,
  };
});

import { applyPersonnelOrderTemplateApplication, generatePersonnelOrderEditorial, getPersonnelOrder, getPersonnelOrderEditorial, getPersonnelOrderDocumentReview, confirmPersonnelOrderDocumentReview, reopenPersonnelOrderDocumentReview, patchPersonnelOrderDocumentHeader, patchPersonnelOrderEditorialBlock, listPersonnelOrderDocumentItems, patchPersonnelOrderDocumentItem, previewPersonnelOrderTemplateApplication, type PersonnelOrderEditorialState } from "../_lib/personnelOrdersApi.client";
import { getEmployees } from "@/app/directory/employees/_lib/api.client";

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

function templateApplicationPreview() {
  const current = Object.fromEntries(
    ["ru", "kk"].flatMap((locale) => ["title", "preamble", "body", "basis"].map((block) => [
      `${locale}:${block}`,
      { generated_text: `old ${locale} ${block}`, override_text: null, revision: 1 },
    ])),
  );
  const proposed = Object.fromEntries(
    ["ru", "kk"].flatMap((locale) => ["title", "preamble", "body", "basis"].map((block) => [
      block === "body" ? `body_template_${locale}` : `${block}_${locale}`,
      `new ${locale} ${block}`,
    ])),
  );
  return {
    available: true,
    template: { template_version_id: 9, version_number: 2, item_type_code: "TERMINATION" },
    has_overrides: false,
    override_blocks: [],
    has_prior_application: false,
    last_application: null,
    current,
    proposed,
    order_revision: 1,
  };
}

function templateEditorial(prefix: "old" | "new"): PersonnelOrderEditorialState {
  return {
    order_id: 42,
    order_status: "DRAFT",
    editable: true,
    order_blocks: ["ru", "kk"].flatMap((locale, index) => [
      { block_id: index * 2 + 1, scope: "order" as const, order_item_id: null, locale: locale as "ru" | "kk", block_type: "title" as const, generated_text: `${prefix} ${locale} title`, override_text: null, effective_text: `${prefix} ${locale} title`, review_status: "CURRENT" as const, editable: true, revision: 1 },
      { block_id: index * 2 + 2, scope: "order" as const, order_item_id: null, locale: locale as "ru" | "kk", block_type: "preamble" as const, generated_text: `${prefix} ${locale} preamble`, override_text: null, effective_text: `${prefix} ${locale} preamble`, review_status: "CURRENT" as const, editable: true, revision: 1 },
      { block_id: index * 2 + 5, scope: "order" as const, order_item_id: null, locale: locale as "ru" | "kk", block_type: "closing" as const, generated_text: `${prefix} ${locale} closing`, override_text: null, effective_text: `${prefix} ${locale} closing`, review_status: "CURRENT" as const, editable: true, revision: 1 },
    ]),
    items: [{
      order_item_id: 17,
      item_number: 1,
      item_type_code: "TERMINATION",
      basis_required: true,
      blocks: ["ru", "kk"].flatMap((locale, index) => [
        { block_id: 10 + index * 2, scope: "item" as const, order_item_id: 17, locale: locale as "ru" | "kk", block_type: "body" as const, generated_text: `${prefix} ${locale} body`, override_text: null, effective_text: `${prefix} ${locale} body`, review_status: "CURRENT" as const, editable: true, revision: 1 },
        { block_id: 11 + index * 2, scope: "item" as const, order_item_id: 17, locale: locale as "ru" | "kk", block_type: "basis" as const, generated_text: `${prefix} ${locale} basis`, override_text: null, effective_text: `${prefix} ${locale} basis`, review_status: "CURRENT" as const, editable: true, revision: 1 },
      ]),
    }],
  };
}

function withClosingSuppressed(editorial: PersonnelOrderEditorialState, suppressed: boolean): PersonnelOrderEditorialState {
  return {
    ...editorial,
    order_blocks: editorial.order_blocks.map((block) => block.block_type === "closing"
      ? { ...block, override_text: suppressed ? "" : null, effective_text: suppressed ? "" : block.generated_text, revision: block.revision + 1 }
      : block) as PersonnelOrderEditorialState["order_blocks"],
  };
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  currentUser.value = null;
});

describe("PersonnelOrderDetailDrawer document tab", () => {
  it("shows HR_HEAD all-status deletion in the card and calls the dedicated soft-delete API after one confirmation", async () => {
    currentUser.value = { role_code: "HR_HEAD" };
    vi.mocked(getPersonnelOrder).mockResolvedValue({ ...detail, order: { ...detail.order, status: "SIGNED" } });
    hrHeadDelete.mockResolvedValue({ status: "SOFT_DELETED", order_id: 42 });
    const onClose = vi.fn();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<PersonnelOrderDetailDrawer orderId={42} open initialTab="data" onClose={onClose} />);
    const button = await screen.findByRole("button", { name: "Удалить" });
    fireEvent.click(button);
    await waitFor(() => expect(hrHeadDelete).toHaveBeenCalledWith(42));
    expect(onClose).toHaveBeenCalled();
  });

  it.each(["ADMIN", "HR_HEAD"])("opens the DRAFT header editor for %s even when number and date are empty", async (roleCode) => {
    currentUser.value = { role_code: roleCode };
    vi.mocked(getPersonnelOrder).mockResolvedValue({
      ...detail,
      order: { ...detail.order, order_number: null, order_date: null, status: "DRAFT" },
    });

    render(<PersonnelOrderDetailDrawer orderId={42} open initialTab="data" onClose={vi.fn()} />);
    const editButton = await screen.findByTestId("personnel-order-open-header-editor");
    fireEvent.click(editButton);

    const editor = screen.getByTestId("personnel-order-header-editor-section");
    const orderNumber = within(editor).getByPlaceholderText("Заполнить перед регистрацией");
    const orderDate = within(editor).getByTestId("personnel-order-header-order-date");
    await waitFor(() => expect(orderNumber).toHaveFocus());
    expect(orderNumber).not.toBeDisabled();
    expect(orderDate).not.toBeDisabled();
  });

  it("shows the applied LEAVE.UNPAID.GRANT v2 editorial snapshot without consulting the legacy template whitelist", async () => {
    const leaveDetail: PersonnelOrderDetailResponse = {
      ...detail,
      order: { ...detail.order, order_type_code: "LEAVE.UNPAID.GRANT", document_revision: 2 },
      items: [{
        item_id: 91, order_id: 42, item_number: 1, item_type_code: "LEAVE.UNPAID.GRANT", item_status: "ACTIVE",
        employee_id: 7, employee_name: "Employee", effective_date: "2026-07-13", payload: {},
      }],
    };
    const applied: PersonnelOrderEditorialState = {
      order_id: 42, order_status: "DRAFT", editable: true,
      order_blocks: ["kk", "ru"].flatMap((locale, index) => [
        { block_id: index * 2 + 1, scope: "order" as const, order_item_id: null, locale: locale as "kk" | "ru", block_type: "title" as const, generated_text: `snapshot ${locale} title`, override_text: null, effective_text: `snapshot ${locale} title`, review_status: "CURRENT" as const, editable: true, revision: 2 },
        { block_id: index * 2 + 2, scope: "order" as const, order_item_id: null, locale: locale as "kk" | "ru", block_type: "preamble" as const, generated_text: `snapshot ${locale} preamble`, override_text: null, effective_text: `snapshot ${locale} preamble`, review_status: "CURRENT" as const, editable: true, revision: 2 },
      ]),
      items: [{
        order_item_id: 91, item_number: 1, item_type_code: "LEAVE.UNPAID.GRANT", basis_required: true,
        blocks: ["kk", "ru"].flatMap((locale, index) => [
          { block_id: 10 + index * 2, scope: "item" as const, order_item_id: 91, locale: locale as "kk" | "ru", block_type: "body" as const, generated_text: `snapshot ${locale} body`, override_text: null, effective_text: `snapshot ${locale} body`, review_status: "CURRENT" as const, editable: true, revision: 2 },
          { block_id: 11 + index * 2, scope: "item" as const, order_item_id: 91, locale: locale as "kk" | "ru", block_type: "basis" as const, generated_text: `snapshot ${locale} basis`, override_text: null, effective_text: `snapshot ${locale} basis`, review_status: "CURRENT" as const, editable: true, revision: 2 },
        ]),
      }],
    };
    vi.mocked(getPersonnelOrder).mockResolvedValueOnce(leaveDetail).mockResolvedValueOnce(leaveDetail);
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValueOnce({ ...applied, order_blocks: [], items: [] });
    vi.mocked(previewPersonnelOrderTemplateApplication).mockResolvedValueOnce({
      ...templateApplicationPreview(),
      template: { template_version_id: 11, version_number: 2, item_type_code: "LEAVE.UNPAID.GRANT" },
      items: [{ order_item_id: 91, item_number: 1, current: {}, proposed: { body_kk: "snapshot kk body", body_ru: "snapshot ru body", basis_kk: "snapshot kk basis", basis_ru: "snapshot ru basis" }, warnings: [], missing_data: [] }],
    });
    vi.mocked(applyPersonnelOrderTemplateApplication).mockResolvedValueOnce(applied);

    render(<PersonnelOrderDetailDrawer orderId={42} open initialTab="data" onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "\u041f\u0440\u0438\u043c\u0435\u043d\u0438\u0442\u044c \u0448\u0430\u0431\u043b\u043e\u043d" }));
    await waitFor(() => expect(applyPersonnelOrderTemplateApplication).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("tab", { name: "\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442" }));

    const document = await screen.findByTestId("personnel-order-document");
    expect(document).toHaveTextContent("snapshot kk title");
    expect(document).toHaveTextContent("snapshot kk preamble");
    expect(document).toHaveTextContent("snapshot kk body");
    expect(document).toHaveTextContent("snapshot kk basis");
    expect(screen.queryByTestId("personnel-order-document-missing-template")).not.toBeInTheDocument();
    expect(generatePersonnelOrderEditorial).not.toHaveBeenCalled();
  });

  it("synchronizes data and document tabs from one multi-item apply response", async () => {
    const oldEditorial = templateEditorial("old");
    const newEditorial: PersonnelOrderEditorialState = {
      ...templateEditorial("new"),
      items: [
        ...templateEditorial("new").items,
        {
          order_item_id: 18, item_number: 2, item_type_code: "TERMINATION", basis_required: true,
          blocks: [
            { block_id: 30, scope: "item", order_item_id: 18, locale: "ru", block_type: "body", generated_text: "new ru body item 2", override_text: null, effective_text: "new ru body item 2", review_status: "CURRENT", editable: true, revision: 1 },
            { block_id: 31, scope: "item", order_item_id: 18, locale: "kk", block_type: "body", generated_text: "new kk body item 2", override_text: null, effective_text: "new kk body item 2", review_status: "CURRENT", editable: true, revision: 1 },
            { block_id: 32, scope: "item", order_item_id: 18, locale: "ru", block_type: "basis", generated_text: "new ru basis item 2", override_text: null, effective_text: "new ru basis item 2", review_status: "CURRENT", editable: true, revision: 1 },
            { block_id: 33, scope: "item", order_item_id: 18, locale: "kk", block_type: "basis", generated_text: "new kk basis item 2", override_text: null, effective_text: "new kk basis item 2", review_status: "CURRENT", editable: true, revision: 1 },
          ],
        },
      ],
    };
    const multiDetail: PersonnelOrderDetailResponse = {
      ...detail,
      order: { ...detail.order, order_type_code: "TERMINATION", document_revision: 1 },
      items: [17, 18].map((item_id, index) => ({ item_id, order_id: 42, item_number: index + 1, item_type_code: "TERMINATION", item_status: "ACTIVE", employee_id: 7, employee_name: `Employee ${index + 1}`, effective_date: "2026-07-01", payload: { basis_ids: ["application"] } })),
    };
    vi.mocked(getPersonnelOrder).mockResolvedValueOnce(multiDetail).mockResolvedValueOnce(multiDetail);
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValueOnce(oldEditorial);
    vi.mocked(previewPersonnelOrderTemplateApplication).mockResolvedValueOnce(templateApplicationPreview());
    vi.mocked(applyPersonnelOrderTemplateApplication).mockResolvedValueOnce(newEditorial);
    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Данные" }));
    fireEvent.click(await screen.findByRole("button", { name: "Применить шаблон" }));
    await waitFor(() => expect(screen.getByTestId("personnel-order-editorial-editor")).toHaveTextContent("new kk body item 2"));
    fireEvent.click(screen.getByRole("tab", { name: "Документ" }));
    const document = await screen.findByTestId("personnel-order-document");
    expect(document).toHaveTextContent("new kk body item 2");
    expect(document).not.toHaveTextContent("old kk body");
  });

  it("uses the applied template response as the single editorial snapshot across data and document", async () => {
    const oldEditorial = templateEditorial("old");
    const newEditorial = templateEditorial("new");
    const terminationDetail: PersonnelOrderDetailResponse = {
      ...detail,
      order: { ...detail.order, order_type_code: "TERMINATION", document_revision: 1 },
      items: [{
        item_id: 17,
        order_id: 42,
        item_number: 1,
        item_type_code: "TERMINATION",
        item_status: "ACTIVE",
        employee_id: 7,
        employee_name: "Historical employee",
        effective_date: "2026-07-01",
        payload: { basis_ids: ["application"] },
      }],
    };
    vi.mocked(getPersonnelOrder).mockResolvedValueOnce(terminationDetail).mockResolvedValueOnce(terminationDetail);
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValueOnce(oldEditorial);
    vi.mocked(previewPersonnelOrderTemplateApplication).mockResolvedValueOnce(templateApplicationPreview());
    vi.mocked(applyPersonnelOrderTemplateApplication).mockResolvedValueOnce(newEditorial);

    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Данные" }));
    const editor = await screen.findByTestId("personnel-order-editorial-editor");
    expect(editor).toHaveTextContent("old kk title");
    expect(editor).toHaveTextContent("old kk preamble");
    expect(editor).toHaveTextContent("old kk body");
    expect(editor).toHaveTextContent("old kk basis");

    fireEvent.click(screen.getByRole("button", { name: "Применить шаблон" }));
    await waitFor(() => expect(applyPersonnelOrderTemplateApplication).toHaveBeenCalledTimes(1));
    expect(getPersonnelOrderEditorial).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-editorial-editor")).toHaveTextContent("new kk title");
    });
    expect(screen.getByTestId("personnel-order-editorial-editor")).toHaveTextContent("new kk preamble");
    expect(screen.getByTestId("personnel-order-editorial-editor")).toHaveTextContent("new kk body");
    expect(screen.getByTestId("personnel-order-editorial-editor")).toHaveTextContent("new kk basis");
    expect(screen.getByTestId("personnel-order-editorial-editor")).not.toHaveTextContent("old kk basis");
    expect(generatePersonnelOrderEditorial).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("tab", { name: "Документ" }));
    const document = await screen.findByTestId("personnel-order-document");
    expect(document).toHaveTextContent("new kk title");
    expect(document).toHaveTextContent("new kk preamble");
    expect(document).toHaveTextContent("new kk body");
    expect(document).toHaveTextContent("new kk basis");
    expect(document).not.toHaveTextContent("old kk basis");
  });

  it("opens typed corrections without exposing payload and saves only allowed fields", async () => {
    vi.mocked(getPersonnelOrder).mockResolvedValue({ ...detail, order: { ...detail.order, status: "REGISTERED", document_revision: 3 } });
    vi.mocked(getEmployees).mockResolvedValue({ items: [{ id: 8, fio: "Selected employee", position: { name: "Doctor" }, org_unit: { name: "Unit" } }] } as never);
    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Корректировки" }));
    expect(await screen.findByTestId("personnel-order-document-items")).toBeInTheDocument();
    expect(listPersonnelOrderDocumentItems).toHaveBeenCalledWith(42);
    expect(screen.queryByText(/payload/i)).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Тип пункта 9"), { target: { value: "TRANSFER" } });
    fireEvent.change(screen.getByLabelText("Сотрудник 9"), { target: { value: "Selected" } });
    await waitFor(() => expect(getEmployees).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /Selected employee/ }));
    fireEvent.change(screen.getByLabelText("Должность в приказе 9"), { target: { value: "Document doctor" } });
    fireEvent.change(screen.getByLabelText("Отделение в приказе 9"), { target: { value: "Document unit" } });
    fireEvent.change(screen.getByLabelText("Специальность 9"), { target: { value: "Neurology" } });
    fireEvent.change(screen.getByLabelText("Дата действия 9"), { target: { value: "2026-09-03" } });
    fireEvent.change(screen.getByLabelText("Ставка в приказе 9"), { target: { value: "0,25" } });
    fireEvent.change(screen.getByLabelText("Причина исправления пункта"), { target: { value: "DOCUMENT_CONTEXT_CORRECTION" } });
    fireEvent.change(screen.getByLabelText("Пояснение исправления пункта"), { target: { value: "Исправлен документный контекст" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить изменения" }));
    await waitFor(() => expect(patchPersonnelOrderDocumentItem).toHaveBeenCalledWith(42, 9, expect.objectContaining({ expected_document_revision: 1, item_type_code: "TRANSFER", employee_id: 8, effective_date: "2026-09-03", document_subject_context: { position_name: "Document doctor", org_unit_name: "Document unit", specialty: "Neurology", rate: "0,25" }, reason_code: "DOCUMENT_CONTEXT_CORRECTION", reason_text: "Исправлен документный контекст" })));
    await waitFor(() => expect(getPersonnelOrderEditorial).toHaveBeenCalledTimes(2));
  });

  it("shows only Document and Data tabs for a draft and resolves legacy items to Data", async () => {
    vi.mocked(getPersonnelOrder).mockResolvedValue({ ...detail, order: { ...detail.order, status: "DRAFT" } });
    render(<PersonnelOrderDetailDrawer orderId={42} open initialTab="items" onClose={vi.fn()} />);

    await screen.findByRole("tab", { name: "Данные" });
    expect(screen.getByRole("tab", { name: "Документ" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Корректировки" })).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("tab", { name: "Данные" })).toHaveAttribute("aria-selected", "true"));
    expect(screen.queryByTestId("personnel-order-document-items")).not.toBeInTheDocument();
  });

  it.each(["REGISTERED", "SIGNED"] as const)("keeps the typed correction flow available for %s legacy items links", async (status) => {
    vi.mocked(getPersonnelOrder).mockResolvedValue({ ...detail, order: { ...detail.order, status } });
    render(<PersonnelOrderDetailDrawer orderId={42} open initialTab="items" onClose={vi.fn()} />);

    const corrections = await screen.findByRole("tab", { name: "Корректировки" });
    expect(corrections).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByTestId("personnel-order-document-items")).toBeInTheDocument();
    expect(listPersonnelOrderDocumentItems).toHaveBeenCalledWith(42);
  });

  it("keeps Corrections usable after tab switching and reopening a multi-item order", async () => {
    const registeredMultiItemDetail: PersonnelOrderDetailResponse = {
      ...detail,
      order: { ...detail.order, status: "REGISTERED" },
      items: [
        { item_id: 1, order_id: 42, item_number: 1, item_type_code: "HIRE", item_status: "ACTIVE", employee_id: 11, employee_name: "First employee", effective_date: "2026-07-01", payload: {} },
        { item_id: 2, order_id: 42, item_number: 2, item_type_code: "TRANSFER", item_status: "ACTIVE", employee_id: 12, employee_name: "Second employee", effective_date: "2026-07-02", payload: {} },
      ],
    };
    vi.mocked(getPersonnelOrder).mockResolvedValue(registeredMultiItemDetail);
    const onClose = vi.fn();
    const { rerender } = render(<PersonnelOrderDetailDrawer orderId={42} open onClose={onClose} />);

    fireEvent.click(await screen.findByRole("tab", { name: "Корректировки" }));
    expect(await screen.findByTestId("personnel-order-document-items")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Данные" }));
    const itemEditor = await screen.findByTestId("personnel-order-item-editor");
    expect(itemEditor).toHaveTextContent("First employee");
    expect(itemEditor).toHaveTextContent("Second employee");

    rerender(<PersonnelOrderDetailDrawer orderId={42} open={false} onClose={onClose} />);
    rerender(<PersonnelOrderDetailDrawer orderId={42} open initialTab="items" onClose={onClose} />);
    expect(await screen.findByRole("tab", { name: "Корректировки" })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByTestId("personnel-order-document-items")).toBeInTheDocument();
  });

  it("does not render a separate requisites tab", async () => {
    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);
    await screen.findByTestId("personnel-order-detail-drawer");
    expect(screen.queryByRole("tab", { name: "Реквизиты" })).not.toBeInTheDocument();
  });

  it("keeps the current editorial title separate from absent journal/import provenance", async () => {
    const editorial = templateEditorial("new");
    editorial.order_blocks = editorial.order_blocks.map((block) => block.block_type === "title" && block.locale === "kk"
      ? { ...block, generated_text: "Еңбек шартын бұзу туралы", effective_text: "Еңбек шартын бұзу туралы" }
      : block);
    vi.mocked(getPersonnelOrder).mockResolvedValueOnce({
      ...detail,
      order: { ...detail.order, order_type_code: "TERMINATION", source_title: "legacy generated title", source_title_locale: "kk", storage_json: {} },
    });
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValueOnce(editorial);
    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Данные" }));
    expect((await screen.findAllByText("Еңбек шартын бұзу туралы")).length).toBeGreaterThan(0);
    const provenance = screen.getByTestId("personnel-order-provenance");
    expect(provenance).not.toHaveAttribute("open");
    fireEvent.click(screen.getByText("Источник и история восстановления"));
    expect(provenance).toHaveAttribute("open");
    expect(provenance).not.toHaveTextContent("legacy generated title");
  });

  it("keeps editorial BASIS and attachments on the complete data tab without the legacy basis form", async () => {
    const editorial = templateEditorial("new");
    const terminationDetail: PersonnelOrderDetailResponse = {
      ...detail,
      order: { ...detail.order, order_type_code: "TERMINATION" },
      items: [{
        item_id: 17,
        order_id: 42,
        item_number: 1,
        item_type_code: "TERMINATION",
        item_status: "ACTIVE",
        employee_id: 7,
        employee_name: "Historical employee",
        effective_date: "2026-07-01",
        payload: { basis_entries: [{ document_type: "EMPLOYEE_APPLICATION", basis_id: "application", other_text: "" }], basis_ids: ["application"] },
      }],
      attachments: [{ attachment_id: 1, order_id: 42, attachment_kind: "BASIS_DOCUMENT", storage_type: "LOCAL", file_path: "basis.pdf", file_url: null, file_comment: null, locale: "kk", created_by: 1, created_at: "2026-07-01T00:00:00Z" }],
    };
    vi.mocked(getPersonnelOrder).mockResolvedValue(terminationDetail);
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(editorial);

    render(<PersonnelOrderDetailDrawer orderId={42} open initialTab="data" onClose={vi.fn()} />);

    expect(await screen.findByText("Негіз (мәтін құжатта)")).toBeInTheDocument();
    expect(screen.getByText("new kk basis")).toBeInTheDocument();
    expect(screen.queryByTestId("personnel-order-basis-form")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Основание" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Сохранить изменения" })).not.toBeInTheDocument();
    expect(screen.getByText("Вложения (1)")).toBeInTheDocument();
  });

  it("suppresses and restores both closing blocks without changing the template blocks", async () => {
    const before = templateEditorial("new");
    const suppressed = withClosingSuppressed(before, true);
    const terminationDetail: PersonnelOrderDetailResponse = {
      ...detail,
      order: { ...detail.order, order_type_code: "TERMINATION" },
      items: [{
        item_id: 17,
        order_id: 42,
        item_number: 1,
        item_type_code: "TERMINATION",
        item_status: "ACTIVE",
        employee_id: 7,
        employee_name: "Historical employee",
        effective_date: "2026-07-01",
        payload: { basis_ids: ["application"] },
      }],
    };
    vi.mocked(getPersonnelOrder).mockResolvedValue(terminationDetail);
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValueOnce(before);
    vi.mocked(patchPersonnelOrderEditorialBlock)
      .mockResolvedValueOnce(withClosingSuppressed(before, false))
      .mockResolvedValueOnce(suppressed)
      .mockResolvedValueOnce(withClosingSuppressed(before, true))
      .mockResolvedValueOnce(before);

    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("tab", { name: "Данные" }));
    expect(screen.queryByTestId("personnel-order-closing-control")).not.toBeInTheDocument();
    expect((await screen.findAllByText("new kk closing")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByTestId("personnel-order-editorial-closing-toggle"));
    await waitFor(() => expect(patchPersonnelOrderEditorialBlock).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByRole("tab", { name: "Документ" }));
    const document = await screen.findByTestId("personnel-order-document");
    expect(document).not.toHaveTextContent("Қосымша өкімдер");
    expect(document).not.toHaveTextContent("new kk closing");
    expect(document).toHaveTextContent("new kk title");
    expect(document).toHaveTextContent("new kk preamble");
    expect(document).toHaveTextContent("new kk body");
    expect(document).toHaveTextContent("new kk basis");

    fireEvent.click(screen.getByRole("tab", { name: "Данные" }));
    fireEvent.click(await screen.findByTestId("personnel-order-editorial-closing-toggle"));
    await waitFor(() => expect(patchPersonnelOrderEditorialBlock).toHaveBeenCalledTimes(4));
    fireEvent.click(screen.getByRole("tab", { name: "Документ" }));
    await waitFor(() => expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("Қосымша өкімдер"));
    expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("new kk closing");
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

  it("uses the current editorial body in document and print instead of a stale payload fallback", async () => {
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
      expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("Перевести Иванова на должность медсестра.");
    });
    fireEvent.click(screen.getByRole("tab", { name: "Данные" }));
    expect(await screen.findByTestId("personnel-order-editorial-editor")).toHaveTextContent("Перевести Иванова на должность медсестра.");
    fireEvent.click(screen.getByRole("tab", { name: "Документ" }));
    fireEvent.click(screen.getByTestId("personnel-order-drawer-print"));
    await waitFor(() => expect(print).toHaveBeenCalled());
    expect(screen.getByTestId("personnel-order-active-print-root")).toHaveTextContent("Перевести Иванова на должность медсестра.");
    fireEvent(window, new Event("afterprint"));

    rerender(<PersonnelOrderDetailDrawer orderId={405} open={false} onClose={vi.fn()} />);
    rerender(<PersonnelOrderDetailDrawer orderId={405} open onClose={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Русский" }));
    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("Перевести Иванова на должность медсестра.");
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
      expect(screen.getAllByText("И. о. директора").length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText("К. Замещающий").length).toBeGreaterThan(0);
    expect(screen.queryByText("М. Тулеутаев")).not.toBeInTheDocument();
  });
});
