import { afterAll, describe, expect, it } from "vitest";

import {
  buildPersonnelOrderPdfContentDisposition,
  buildPersonnelOrderPdfFilename,
  buildPersonnelOrderPdfHref,
  sanitizePersonnelOrderPdfFilenamePart,
} from "./personnelOrderPdfFilename";
import { buildPersonnelOrderPdfHtmlDocument } from "./personnelOrderPdfHtml";
import { PERSONNEL_ORDER_PDF_OPTIONS, getPersonnelOrderPdfRenderer } from "./personnelOrderPdfRenderer";
import { closePersonnelOrderPdfBrowser } from "./personnelOrderPdfBrowser";
import { extractPersonnelOrderPdfAuth, isPersonnelOrderPdfAuthenticated } from "./personnelOrderPdfAuth";
import { parsePersonnelOrderPrintLanguage } from "./personnelOrderPrintLanguage";
import { statusMarkLinesForLanguage } from "./personnelOrderPrintLocale";
import { buildPersonnelOrderPrintDocumentHtml } from "./personnelOrderPrintDocumentHtml";
import {
  buildPersonnelOrderPrintViewModel,
  type PersonnelOrderPrintViewModel,
} from "./personnelOrderPrintViewModel";
import type { PersonnelOrderDetailResponse } from "./personnelOrdersApi.client";

function sampleDetail(
  overrides?: Partial<PersonnelOrderDetailResponse["order"]>,
): PersonnelOrderDetailResponse {
  return {
    order: {
      order_id: 125,
      order_number: "125-К",
      order_date: "2026-07-10",
      order_type_code: "HIRE",
      order_class: "SIMPLE",
      status: "DRAFT",
      source_mode: "PAPER",
      legal_basis_article: "ст. 33 ТК РК",
      basis_summary: "Заявление работника",
      signed_by_name: "Иванов И.И.",
      signed_by_position: "Директор",
      created_by: 1,
      ...overrides,
    },
    items: [
      {
        item_id: 1,
        order_id: 125,
        item_number: 1,
        item_type_code: "HIRE",
        item_status: "ACTIVE",
        employee_id: 7,
        employee_name: "Петрова Анна",
        effective_date: "2026-07-15",
        payload: { org_unit_id: 10, position_id: 20, employment_rate: 1 },
      },
    ],
    localized_texts: [
      {
        localized_text_id: 1,
        order_id: 125,
        locale: "kk",
        title: "Жұмысқа қабылдау туралы",
        preamble: null,
        body_text: null,
        render_version: 1,
        is_authoritative: true,
      },
      {
        localized_text_id: 2,
        order_id: 125,
        locale: "ru",
        title: "О приёме на работу",
        preamble: null,
        body_text: null,
        render_version: 1,
        is_authoritative: false,
      },
    ],
    attachments: [],
    prints: [],
    events: [],
  };
}

function sampleModel(
  overrides?: Partial<PersonnelOrderDetailResponse["order"]>,
): PersonnelOrderPrintViewModel {
  return buildPersonnelOrderPrintViewModel(sampleDetail(overrides), {
    organizationName: "Многопрофильный медицинский центр г. Астана",
    orgUnitNames: { 10: "Отдел кадров" },
    positionNames: { 20: "Медсестра" },
  });
}

describe("personnelOrderPdfFilename", () => {
  it("builds sanitized filenames for ru, kk, kk-ru", () => {
    expect(buildPersonnelOrderPdfFilename("125-К", 125, "ru")).toBe("personnel-order-125-k-ru.pdf");
    expect(buildPersonnelOrderPdfFilename("125-К", 125, "kk")).toBe("personnel-order-125-k-kk.pdf");
    expect(buildPersonnelOrderPdfFilename("125-К", 125, "kk-ru")).toBe(
      "personnel-order-125-k-kk-ru.pdf",
    );
  });

  it("strips unsafe filename characters", () => {
    expect(sanitizePersonnelOrderPdfFilenamePart('12/5\\"к')).toBe("12-5-k");
    expect(buildPersonnelOrderPdfContentDisposition('personnel-order-125-k-ru.pdf')).toBe(
      'inline; filename="personnel-order-125-k-ru.pdf"',
    );
  });

  it("builds pdf href", () => {
    expect(buildPersonnelOrderPdfHref(125, "kk-ru")).toBe(
      "/directory/personnel/orders/125/pdf?language=kk-ru",
    );
  });
});

describe("personnelOrderPdf language and watermark", () => {
  it("rejects unknown language", () => {
    expect(parsePersonnelOrderPrintLanguage("en", { fallbackToDefault: false })).toBeNull();
  });

  it("maps watermark labels for statuses", () => {
    expect(statusMarkLinesForLanguage("draft", "ru")).toEqual(["ПРОЕКТ"]);
    expect(statusMarkLinesForLanguage("draft", "kk")).toEqual(["ЖОБА"]);
    expect(statusMarkLinesForLanguage("unsigned", "ru")).toEqual(["НА ПОДПИСЬ"]);
    expect(statusMarkLinesForLanguage("unsigned", "kk")).toEqual(["ҚОЛ ҚОЮҒА"]);
    expect(statusMarkLinesForLanguage("cancelled", "ru")).toEqual(["АННУЛИРОВАН"]);
    expect(statusMarkLinesForLanguage("cancelled", "kk")).toEqual(["КҮШІ ЖОЙЫЛҒАН"]);
    expect(sampleModel({ status: "REGISTERED" }).statusMark).toBe("none");
    expect(sampleModel({ status: "SIGNED" }).statusMark).toBe("none");
  });

  it("includes draft watermark and order text in HTML, excludes site chrome", () => {
    const html = buildPersonnelOrderPdfHtmlDocument({
      model: sampleModel({ status: "DRAFT" }),
      language: "ru",
    });
    expect(html).toContain("ПРОЕКТ");
    expect(html).toContain("О приёме на работу");
    expect(html).toContain("Times New Roman");
    expect(html).not.toContain("localhost");
    expect(html).not.toContain("Система личных кабинетов");
    expect(html).not.toContain("personnel-order-print-toolbar");
  });

  it("omits watermark for REGISTERED", () => {
    const html = buildPersonnelOrderPdfHtmlDocument({
      model: sampleModel({ status: "REGISTERED" }),
      language: "ru",
    });
    expect(html).not.toContain("ПРОЕКТ");
    expect(html).not.toContain("НА ПОДПИСЬ");
    expect(html).not.toContain("АННУЛИРОВАН");
  });

  it("includes signatory requisites in PDF HTML document", () => {
    const html = buildPersonnelOrderPdfHtmlDocument({
      model: sampleModel({
        order_date: "2026-07-18",
        signed_by_name: "М. Тулеутаев",
        signed_by_position: "Директор",
      }),
      language: "ru",
    });
    expect(html).toContain("18 июля 2026 года");
    expect(html).toContain("Директор");
    expect(html).toContain("М. Тулеутаев");
    expect(html).toContain('data-testid="personnel-order-print-signature"');
  });

  it("includes manual signatory override in PDF HTML document", () => {
    const html = buildPersonnelOrderPdfHtmlDocument({
      model: sampleModel({
        order_date: "2026-07-18",
        signed_by_name: "К. Замещающий",
        signed_by_position: "И. о. директора",
      }),
      language: "ru",
    });
    expect(html).toContain("И. о. директора");
    expect(html).toContain("К. Замещающий");
    expect(html).not.toContain("М. Тулеутаев");
  });

  it("pdf pipeline uses the same requisites in print HTML and PDF HTML document", () => {
    const model = sampleModel({
      order_date: "2026-07-18",
      signed_by_name: "М. Тулеутаев",
      signed_by_position: "Директор",
    });
    const pdfHtml = buildPersonnelOrderPdfHtmlDocument({ model, language: "ru" });
    const printHtml = buildPersonnelOrderPrintDocumentHtml(model, "ru");

    for (const value of ["18 июля 2026 года", "Директор", "М. Тулеутаев"]) {
      expect(pdfHtml).toContain(value);
      expect(printHtml).toContain(value);
    }
  });
});

describe("personnelOrderPdfAuth", () => {
  it("requires bearer or dev user", () => {
    const empty = extractPersonnelOrderPdfAuth(new Request("http://localhost/pdf"));
    expect(isPersonnelOrderPdfAuthenticated(empty)).toBe(false);

    const withBearer = extractPersonnelOrderPdfAuth(
      new Request("http://localhost/pdf", {
        headers: { Authorization: "Bearer abc.def.ghi" },
      }),
    );
    expect(withBearer.bearerToken).toBe("abc.def.ghi");
    expect(isPersonnelOrderPdfAuthenticated(withBearer)).toBe(true);
  });
});

describe("personnelOrderPdfRenderer options", () => {
  it("disables browser header/footer and uses A4 margins", () => {
    expect(PERSONNEL_ORDER_PDF_OPTIONS.displayHeaderFooter).toBe(false);
    expect(PERSONNEL_ORDER_PDF_OPTIONS.format).toBe("A4");
    expect(PERSONNEL_ORDER_PDF_OPTIONS.margin).toEqual({
      top: "15mm",
      right: "18mm",
      bottom: "18mm",
      left: "25mm",
    });
  });
});

describe("personnelOrderPdfRenderer integration", () => {
  afterAll(async () => {
    await closePersonnelOrderPdfBrowser();
  });

  it(
    "renders a non-empty A4 PDF without browser chrome strings",
    async () => {
      const renderer = getPersonnelOrderPdfRenderer();
      const started = Date.now();
      const pdf = await renderer.render({
        model: sampleModel({ status: "DRAFT", order_number: "125-К" }),
        language: "ru",
      });
      const durationMs = Date.now() - started;

      expect(pdf.subarray(0, 5).toString("utf8")).toBe("%PDF-");
      expect(pdf.byteLength).toBeGreaterThan(1000);
      // Soft size/time signals for the WP report (not hard flaky asserts).
      expect(durationMs).toBeLessThan(30_000);
      // eslint-disable-next-line no-console
      console.info(
        JSON.stringify({
          event: "personnel_order_pdf_fixture_metrics",
          bytes: pdf.byteLength,
          duration_ms: durationMs,
        }),
      );

      const asLatin = pdf.toString("latin1");
      expect(asLatin).not.toMatch(/localhost/i);
      expect(asLatin).not.toContain("Система личных кабинетов");

      // Watermark / body text may be compressed; HTML path already asserts content.
      // Font name often appears in PDF font dictionaries when embedded/used.
      expect(/Times|TimesNewRoman|Times New Roman/i.test(asLatin)).toBe(true);
    },
    45_000,
  );

  it(
    "renders kk and kk-ru PDFs",
    async () => {
      const renderer = getPersonnelOrderPdfRenderer();
      for (const language of ["kk", "kk-ru"] as const) {
        const pdf = await renderer.render({
          model: sampleModel({ status: "READY_FOR_SIGNATURE" }),
          language,
        });
        expect(pdf.subarray(0, 5).toString("utf8")).toBe("%PDF-");
        expect(pdf.byteLength).toBeGreaterThan(1000);
      }
    },
    60_000,
  );

  it(
    "propagates renderer timeout as PDF_TIMEOUT",
    async () => {
      const prev = process.env.PERSONNEL_ORDER_PDF_TIMEOUT_MS;
      process.env.PERSONNEL_ORDER_PDF_TIMEOUT_MS = "1";
      try {
        const { getPersonnelOrderPdfRenderer: getRenderer } = await import(
          "./personnelOrderPdfRenderer"
        );
        const { closePersonnelOrderPdfBrowser: closeBrowser } = await import(
          "./personnelOrderPdfBrowser"
        );
        await expect(
          getRenderer().render({
            model: sampleModel(),
            language: "ru",
          }),
        ).rejects.toMatchObject({ code: "PDF_TIMEOUT" });
        await closeBrowser();
      } finally {
        if (prev == null) delete process.env.PERSONNEL_ORDER_PDF_TIMEOUT_MS;
        else process.env.PERSONNEL_ORDER_PDF_TIMEOUT_MS = prev;
      }
    },
    30_000,
  );
});
