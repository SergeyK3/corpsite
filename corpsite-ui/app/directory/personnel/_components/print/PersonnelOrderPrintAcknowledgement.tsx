import type { PersonnelOrderPrintLanguage } from "../../_lib/personnelOrderPrintLanguage";
import {
  primaryPrintDictionary,
  printDictionariesForLanguage,
} from "../../_lib/personnelOrderPrintLocale";
import type { PersonnelOrderPrintViewModel } from "../../_lib/personnelOrderPrintViewModel";

type Props = {
  acknowledgements: PersonnelOrderPrintViewModel["acknowledgements"];
  language: PersonnelOrderPrintLanguage;
};

export default function PersonnelOrderPrintAcknowledgement({
  acknowledgements,
  language,
}: Props) {
  if (!acknowledgements.length) return null;
  const dictionaries = printDictionariesForLanguage(language);
  const primary = primaryPrintDictionary(language);

  return (
    <section
      className="personnel-order-print-block mt-12 space-y-4"
      data-testid="personnel-order-print-acknowledgement"
    >
      <div className="space-y-0.5 font-medium">
        {dictionaries.map((dict) => (
          <div key={dict.familiarization}>{dict.familiarization}</div>
        ))}
      </div>

      {acknowledgements.map((row, index) => {
        const name = String(row.employeeName || "").trim() || `№${row.employeeId ?? index + 1}`;
        return (
          <div
            key={`${row.employeeId ?? "n"}-${name}`}
            className="personnel-order-print-ack-row break-inside-avoid space-y-1"
          >
            <div className="grid grid-cols-[minmax(7rem,1fr)_minmax(0,1.6fr)_auto] items-end gap-x-4 gap-y-1">
              <div>
                <div className="border-b border-black pb-0.5 leading-none">&nbsp;</div>
                <div className="personnel-order-print-ack-caption pt-0.5 text-center text-zinc-600">
                  {primary.signatureCaption}
                </div>
              </div>
              <div className="pb-4 font-medium leading-snug">{name}</div>
              <div className="whitespace-nowrap pb-4">{primary.familiarizationDate}</div>
            </div>
          </div>
        );
      })}
    </section>
  );
}
