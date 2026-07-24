import { buildIntakePdfHtmlDocument } from "./intakePdfDocumentHtml";
import { withPersonnelOrderPdfPage } from "@/app/directory/personnel/_lib/personnelOrderPdfBrowser";
import { PERSONNEL_ORDER_PDF_OPTIONS } from "@/app/directory/personnel/_lib/personnelOrderPdfRenderer";
import type { IntakePdfViewModel } from "./intakePdfViewModel";

export type IntakePdfRenderer = {
  render(model: IntakePdfViewModel): Promise<Buffer>;
};

export const INTAKE_PDF_OPTIONS = PERSONNEL_ORDER_PDF_OPTIONS;

export const playwrightIntakePdfRenderer: IntakePdfRenderer = {
  async render(model) {
    const html = buildIntakePdfHtmlDocument(model);
    return withPersonnelOrderPdfPage(async (page) => {
      await page.setContent(html, { waitUntil: "load" });
      const pdf = await page.pdf(INTAKE_PDF_OPTIONS);
      return Buffer.from(pdf);
    });
  },
};

export function getIntakePdfRenderer(): IntakePdfRenderer {
  return playwrightIntakePdfRenderer;
}
