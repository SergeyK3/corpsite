import { describe, expect, it, vi } from "vitest";

import { buildPersonnelOrderDocumentRequisitesDisplay } from "./personnelOrderDocumentRequisites";
import { buildPersonnelOrderPdfHtmlDocument } from "./personnelOrderPdfHtml";
import { buildPersonnelOrderPrintDocumentHtml } from "./personnelOrderPrintDocumentHtml";
import {
  buildPersonnelOrderPrintNameMaps,
  loadPersonnelOrderPrintViewModelClient,
} from "./personnelOrderPrintLoad.client";
import {
  buildPersonnelOrderPrintViewModel,
  type PersonnelOrderPrintViewModel,
} from "./personnelOrderPrintViewModel";
import type {
  PersonnelOrderDetailResponse,
  PersonnelOrderEditorialState,
} from "./personnelOrdersApi.client";

vi.mock("./personnelOrdersApi.client", async () => {
  const actual = await vi.importActual<typeof import("./personnelOrdersApi.client")>(
    "./personnelOrdersApi.client",
  );
  return {
    ...actual,
    getPersonnelOrder: vi.fn(),
    getPersonnelOrderEditorial: vi.fn(),
  };
});

vi.mock("@/app/directory/org-units/_lib/api.client", () => ({
  getOrgUnitsTree: vi.fn(async () => ({ items: [] })),
}));

vi.mock("@/app/directory/employees/_lib/api.client", () => ({
  getPositions: vi.fn(async () => ({ items: [] })),
}));

import { getPersonnelOrder, getPersonnelOrderEditorial } from "./personnelOrdersApi.client";

const CLOSING_TEXT = "Контроль за исполнением приказа оставляю за собой.";

function sampleDetail(
  overrides?: Partial<PersonnelOrderDetailResponse["order"]>,
): PersonnelOrderDetailResponse {
  return {
    order: {
      order_id: 42,
      order_number: "12-К",
      order_date: "2026-07-18",
      order_type_code: "HIRE",
      order_class: "SIMPLE",
      status: "DRAFT",
      source_mode: "PAPER",
      signed_by_name: "М. Тулеутаев",
      signed_by_position: "Директор",
      created_by: 1,
      ...overrides,
    },
    items: [],
    localized_texts: [],
    attachments: [],
    prints: [],
    events: [],
  };
}

function sampleEditorial(): PersonnelOrderEditorialState {
  return {
    order_id: 42,
    order_status: "DRAFT",
    editable: true,
    order_blocks: [
      {
        block_id: 50,
        scope: "order",
        locale: "ru",
        block_type: "closing",
        effective_text: CLOSING_TEXT,
        review_status: "CURRENT",
        editable: true,
        revision: 1,
      },
    ],
    items: [],
  };
}

function buildPipelineModel(
  overrides?: Partial<PersonnelOrderDetailResponse["order"]>,
): PersonnelOrderPrintViewModel {
  return buildPersonnelOrderPrintViewModel(sampleDetail(overrides), {
    editorial: sampleEditorial(),
  });
}

function countOccurrences(haystack: string, needle: string): number {
  if (!needle) return 0;
  return haystack.split(needle).length - 1;
}

describe("personnelOrder requisites pipeline", () => {
  it("maps saved order header into view model signatory and date", () => {
    const model = buildPipelineModel();
    expect(model.orderDate).toBe("2026-07-18");
    expect(model.signatory?.position?.ru).toBe("Директор");
    expect(model.signatory?.fio).toBe("М. Тулеутаев");
  });

  it("uses manual signatory override in view model instead of director defaults", () => {
    const model = buildPipelineModel({
      signed_by_position: "И. о. директора",
      signed_by_name: "К. Замещающий",
    });
    expect(model.signatory?.position?.ru).toBe("И. о. директора");
    expect(model.signatory?.fio).toBe("К. Замещающий");
    expect(model.signatory?.fio).not.toBe("М. Тулеутаев");
  });

  it("renders screen requisites display from saved order snapshots", () => {
    const display = buildPersonnelOrderDocumentRequisitesDisplay(
      sampleDetail().order,
      "ru",
    );
    expect(display.formattedDate).toBe("18 июля 2026 года");
    expect(display.signatory.position).toBe("Директор");
    expect(display.signatory.fio).toBe("М. Тулеутаев");
  });

  it("renders HTML with closing then date then signatory without duplication", () => {
    const html = buildPersonnelOrderPrintDocumentHtml(buildPipelineModel(), "ru");

    expect(html.indexOf("personnel-order-print-closing")).toBeGreaterThan(-1);
    expect(html.indexOf("personnel-order-print-tail-date")).toBeGreaterThan(-1);
    expect(html.indexOf("personnel-order-print-signature")).toBeGreaterThan(-1);
    expect(html.indexOf("personnel-order-print-closing")).toBeLessThan(
      html.indexOf("personnel-order-print-tail-date"),
    );
    expect(html.indexOf("personnel-order-print-tail-date")).toBeLessThan(
      html.indexOf("personnel-order-print-signature"),
    );

    expect(html).toContain(CLOSING_TEXT);
    expect(html).toContain("18 июля 2026 года");
    expect(html).toContain("Директор");
    expect(html).toContain("М. Тулеутаев");

    const closingSection = html.slice(
      html.indexOf('data-testid="personnel-order-print-closing"'),
      html.indexOf('data-testid="personnel-order-print-tail-date"'),
    );
    expect(closingSection).not.toContain("18 июля 2026 года");
    expect(closingSection).not.toContain("М. Тулеутаев");

    expect(countOccurrences(html, "18 июля 2026 года")).toBe(1);
    expect(countOccurrences(html, "М. Тулеутаев")).toBe(1);
    expect(countOccurrences(html, "Директор")).toBe(1);
  });

  it("renders manual signatory values in HTML without substituting director", () => {
    const html = buildPersonnelOrderPrintDocumentHtml(
      buildPipelineModel({
        signed_by_position: "И. о. директора",
        signed_by_name: "К. Замещающий",
      }),
      "ru",
    );

    expect(html).toContain("И. о. директора");
    expect(html).toContain("К. Замещающий");
    expect(html).not.toContain("М. Тулеутаев");
  });

  it("generates PDF HTML with requisites and without editor placeholder text", () => {
    const pdfHtml = buildPersonnelOrderPdfHtmlDocument({
      model: buildPipelineModel(),
      language: "ru",
    });

    expect(pdfHtml).toContain("18 июля 2026 года");
    expect(pdfHtml).toContain("Директор");
    expect(pdfHtml).toContain("М. Тулеутаев");
    expect(pdfHtml).not.toContain("Заполните дату приказа");
    expect(pdfHtml).not.toContain("Подписант не указан");
  });

  it("generates PDF HTML for empty signatory without official placeholder leakage", () => {
    const pdfHtml = buildPersonnelOrderPdfHtmlDocument({
      model: buildPersonnelOrderPrintViewModel(
        sampleDetail({
          signed_by_name: null,
          signed_by_position: null,
        }),
        { editorial: sampleEditorial() },
      ),
      language: "ru",
    });

    expect(pdfHtml).toContain('data-testid="personnel-order-print-signature"');
    expect(pdfHtml).not.toContain("М. Тулеутаев");
    expect(pdfHtml).not.toContain("Заполните дату приказа");
    expect(pdfHtml).not.toContain("Подписант не указан");
  });

  it("renders HTML signatory row as position, line, then FIO", () => {
    const html = buildPersonnelOrderPrintDocumentHtml(buildPipelineModel(), "ru");
    const signatureStart = html.indexOf('data-testid="personnel-order-print-signature"');
    const signatureChunk = html.slice(signatureStart, signatureStart + 900);
    expect(signatureChunk.indexOf("personnel-order-print-signature-position")).toBeLessThan(
      signatureChunk.indexOf("personnel-order-print-signature-line"),
    );
    expect(signatureChunk.indexOf("personnel-order-print-signature-line")).toBeLessThan(
      signatureChunk.indexOf("personnel-order-print-signature-fio"),
    );
    expect(signatureChunk).toContain("Директор");
    expect(signatureChunk).toContain("М. Тулеутаев");
  });

  it("keeps same requisites after simulated re-open (detail → model → html)", () => {
    const detail = sampleDetail();
    const firstModel = buildPersonnelOrderPrintViewModel(detail, { editorial: sampleEditorial() });
    const secondModel = buildPersonnelOrderPrintViewModel(
      { ...detail, order: { ...detail.order } },
      { editorial: sampleEditorial() },
    );
    const html = buildPersonnelOrderPrintDocumentHtml(secondModel, "ru");

    expect(firstModel.signatory?.fio).toBe(secondModel.signatory?.fio);
    expect(html).toContain("М. Тулеутаев");
    expect(html).toContain("18 июля 2026 года");
  });

  it("loads print model through the same client path as the preview button", async () => {
    const detail = sampleDetail();
    vi.mocked(getPersonnelOrder).mockResolvedValue(detail);
    vi.mocked(getPersonnelOrderEditorial).mockResolvedValue(sampleEditorial());

    const { model, detail: loadedDetail } = await loadPersonnelOrderPrintViewModelClient(42);
    const html = buildPersonnelOrderPrintDocumentHtml(model, "ru");

    expect(loadedDetail.order.signed_by_position).toBe("Директор");
    expect(loadedDetail.order.signed_by_name).toBe("М. Тулеутаев");
    expect(loadedDetail.order.order_date).toBe("2026-07-18");
    expect(model.orderDate).toBe("2026-07-18");
    expect(model.signatory?.position?.ru).toBe("Директор");
    expect(model.signatory?.fio).toBe("М. Тулеутаев");

    expect(html).toContain("18 июля 2026 года");
    expect(html).toContain("Директор");
    expect(html).toContain("М. Тулеутаев");
    expect(html).not.toContain("Петрова");
    expect(html).not.toContain("Director Test");

    const signatureStart = html.indexOf('data-testid="personnel-order-print-signature"');
    const signatureChunk = html.slice(signatureStart, signatureStart + 900);
    expect(signatureChunk.indexOf("personnel-order-print-signature-position")).toBeLessThan(
      signatureChunk.indexOf("personnel-order-print-signature-line"),
    );
    expect(signatureChunk.indexOf("personnel-order-print-signature-line")).toBeLessThan(
      signatureChunk.indexOf("personnel-order-print-signature-fio"),
    );
  });

  it("buildPersonnelOrderPrintNameMaps passes saved header snapshots into view model", async () => {
    const detail = sampleDetail({
      signed_by_position: "И. о. директора",
      signed_by_name: "К. Замещающий",
    });
    const model = buildPersonnelOrderPrintViewModel(
      detail,
      await buildPersonnelOrderPrintNameMaps(detail, sampleEditorial()),
    );
    const html = buildPersonnelOrderPrintDocumentHtml(model, "ru");

    expect(model.signatory?.fio).toBe("К. Замещающий");
    expect(model.signatory?.position?.ru).toBe("И. о. директора");
    expect(html).toContain("К. Замещающий");
    expect(html).not.toContain("М. Тулеутаев");
  });
});
