import type { PersonnelOrderPrintLanguage } from "./personnelOrderPrintLanguage";
import type { PersonnelOrderPrintViewModel } from "./personnelOrderPrintViewModel";
import { buildPersonnelOrderPdfHtmlDocument } from "./personnelOrderPdfHtml";
import { withPersonnelOrderPdfPage } from "./personnelOrderPdfBrowser";

export type PersonnelOrderPdfRenderInput = {
  model: PersonnelOrderPrintViewModel;
  language: PersonnelOrderPrintLanguage;
};

export type PersonnelOrderPdfRenderer = {
  render(input: PersonnelOrderPdfRenderInput): Promise<Buffer>;
};

export const PERSONNEL_ORDER_PDF_OPTIONS = {
  format: "A4" as const,
  printBackground: true,
  preferCSSPageSize: true,
  displayHeaderFooter: false,
  margin: {
    top: "15mm",
    right: "18mm",
    bottom: "18mm",
    left: "25mm",
  },
};

/**
 * Official PDF renderer: ViewModel → HTML → Chromium page.pdf().
 * Storage / hash / signature stay outside this interface (future snapshot phase).
 */
export const playwrightPersonnelOrderPdfRenderer: PersonnelOrderPdfRenderer = {
  async render(input) {
    const html = buildPersonnelOrderPdfHtmlDocument(input);
    return withPersonnelOrderPdfPage(async (page) => {
      await page.setContent(html, { waitUntil: "load" });
      const pdf = await page.pdf(PERSONNEL_ORDER_PDF_OPTIONS);
      return Buffer.from(pdf);
    });
  },
};

export function getPersonnelOrderPdfRenderer(): PersonnelOrderPdfRenderer {
  return playwrightPersonnelOrderPdfRenderer;
}
