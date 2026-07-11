import type { PersonnelOrderPrintLanguage } from "../../_lib/personnelOrderPrintLanguage";
import { formatPersonnelOrderPrintDateLines } from "../../_lib/personnelOrderPrintFormat";
import {
  primaryPrintDictionary,
  printDictionariesForLanguage,
} from "../../_lib/personnelOrderPrintLocale";
import { resolveLocalizedLines } from "../../_lib/personnelOrderPrintLocalized";
import type { PersonnelOrderPrintViewModel } from "../../_lib/personnelOrderPrintViewModel";

type Props = {
  model: PersonnelOrderPrintViewModel;
  language: PersonnelOrderPrintLanguage;
};

export default function PersonnelOrderPrintHeader({ model, language }: Props) {
  const dictionaries = printDictionariesForLanguage(language);
  const primary = primaryPrintDictionary(language);
  const orgLines = resolveLocalizedLines(model.organization, language);
  const titleLines = resolveLocalizedLines(model.title, language);
  const placeLines = resolveLocalizedLines(model.placeOfIssue, language);
  const dateLines = formatPersonnelOrderPrintDateLines(model.orderDate, language);
  const orderNumber = model.orderNumber?.trim() || "—";

  return (
    <header
      className="personnel-order-print-block space-y-5 text-center"
      data-testid="personnel-order-print-header"
    >
      {orgLines.length > 0 ? (
        <div className="personnel-order-print-org mx-auto max-w-[90%] space-y-0.5 tracking-wide">
          {orgLines.map((line) => (
            <div key={line}>{line}</div>
          ))}
        </div>
      ) : null}

      <div className="personnel-order-print-doc-type space-y-0.5 pt-1 uppercase tracking-[0.18em]">
        {dictionaries.map((dict) => (
          <div key={dict.documentType}>{dict.documentType}</div>
        ))}
      </div>

      <div className="grid grid-cols-2 items-start gap-6 pt-1 text-left">
        <div className="font-medium">
          {primary.orderNumber} {orderNumber}
        </div>
        <div className="text-right">
          {dateLines.map((line, index) => (
            <div key={`date-${index}`}>{line}</div>
          ))}
          {placeLines.map((line, index) => (
            <div key={`place-${index}`}>{line}</div>
          ))}
        </div>
      </div>

      {titleLines.length > 0 ? (
        <div className="personnel-order-print-title space-y-0.5 pt-1">
          {titleLines.map((line, index) => (
            <div key={`title-${index}`}>{line}</div>
          ))}
        </div>
      ) : null}
    </header>
  );
}
