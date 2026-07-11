import type { PersonnelOrderPrintLanguage } from "./personnelOrderPrintLanguage";
import type { PersonnelOrderPrintViewModel } from "./personnelOrderPrintViewModel";
import { PERSONNEL_ORDER_PDF_DOCUMENT_CSS } from "./personnelOrderPrintDocumentCss";
import { buildPersonnelOrderPrintDocumentHtml } from "./personnelOrderPrintDocumentHtml";

export type PersonnelOrderPdfHtmlInput = {
  model: PersonnelOrderPrintViewModel;
  language: PersonnelOrderPrintLanguage;
};

/**
 * Build a standalone HTML document for Chromium PDF rendering.
 * Uses the shared print document HTML template (no react-dom/server).
 */
export function buildPersonnelOrderPdfHtmlDocument(input: PersonnelOrderPdfHtmlInput): string {
  const { model, language } = input;
  const body = buildPersonnelOrderPrintDocumentHtml(model, language);

  return `<!DOCTYPE html>
<html lang="${language === "kk" ? "kk" : "ru"}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>${PERSONNEL_ORDER_PDF_DOCUMENT_CSS}</style>
</head>
<body>
${body}
</body>
</html>`;
}
