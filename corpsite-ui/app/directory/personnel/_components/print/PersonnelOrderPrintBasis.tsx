import type { PersonnelOrderPrintLanguage } from "../../_lib/personnelOrderPrintLanguage";
import { printDictionariesForLanguage } from "../../_lib/personnelOrderPrintLocale";
import { resolveLocalizedLines } from "../../_lib/personnelOrderPrintLocalized";
import type { LocalizedText } from "../../_lib/personnelOrderPrintLocalized";

type Props = {
  basis: LocalizedText[];
  language: PersonnelOrderPrintLanguage;
};

export default function PersonnelOrderPrintBasis({ basis, language }: Props) {
  if (!basis.length) return null;
  const dictionaries = printDictionariesForLanguage(language);
  const lines = basis.flatMap((entry) => resolveLocalizedLines(entry, language));
  if (!lines.length) return null;

  return (
    <section
      className="personnel-order-print-block mt-6 space-y-2 break-inside-avoid"
      data-testid="personnel-order-print-basis"
    >
      <div className="space-y-0.5 font-semibold">
        {dictionaries.map((dict) => (
          <div key={dict.basis}>{dict.basis}:</div>
        ))}
      </div>
      <ul className="list-disc space-y-1 pl-5 text-left leading-relaxed">
        {lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </section>
  );
}
