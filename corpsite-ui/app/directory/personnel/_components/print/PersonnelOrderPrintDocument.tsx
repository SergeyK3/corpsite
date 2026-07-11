import type { PersonnelOrderPrintLanguage } from "../../_lib/personnelOrderPrintLanguage";
import { PERSONNEL_ORDER_PRINT_DOCUMENT_CSS } from "../../_lib/personnelOrderPrintDocumentCss";
import { buildPersonnelOrderPrintDocumentHtml } from "../../_lib/personnelOrderPrintDocumentHtml";
import type { PersonnelOrderPrintViewModel } from "../../_lib/personnelOrderPrintViewModel";

type Props = {
  model: PersonnelOrderPrintViewModel;
  language: PersonnelOrderPrintLanguage;
};

/**
 * Screen preview of the official print document.
 * Markup comes from the shared server-safe HTML template (same as PDF).
 */
export default function PersonnelOrderPrintDocument({ model, language }: Props) {
  const html = buildPersonnelOrderPrintDocumentHtml(model, language);
  return (
    <>
      <style data-testid="personnel-order-print-document-style">{PERSONNEL_ORDER_PRINT_DOCUMENT_CSS}</style>
      <div dangerouslySetInnerHTML={{ __html: html }} />
    </>
  );
}
