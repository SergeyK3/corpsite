import type { PersonnelOrderPrintLanguage } from "../../_lib/personnelOrderPrintLanguage";
import { resolveLocalizedLines } from "../../_lib/personnelOrderPrintLocalized";
import type { PersonnelOrderPrintViewModel } from "../../_lib/personnelOrderPrintViewModel";

type Props = {
  signatory: PersonnelOrderPrintViewModel["signatory"];
  language: PersonnelOrderPrintLanguage;
};

export default function PersonnelOrderPrintSignature({ signatory, language }: Props) {
  const positionLines = signatory?.position
    ? resolveLocalizedLines(signatory.position, language)
    : [];
  const fio = String(signatory?.fio || "").trim();

  return (
    <section
      className="personnel-order-print-signature personnel-order-print-block mt-12 break-inside-avoid"
      data-testid="personnel-order-print-signature"
    >
      <div className="grid grid-cols-[minmax(0,1.2fr)_minmax(7rem,1fr)_minmax(0,1.2fr)] items-end gap-x-4 gap-y-1">
        <div className="min-w-0 space-y-0.5 leading-snug">
          {positionLines.length > 0
            ? positionLines.map((line) => <div key={line}>{line}</div>)
            : (
              <div className="min-h-[1.25rem]">&nbsp;</div>
            )}
        </div>
        <div className="border-b border-black pb-0.5 text-center leading-none">&nbsp;</div>
        <div className="min-w-0 text-right font-medium leading-snug">
          {fio || <span className="inline-block min-w-[8rem]">&nbsp;</span>}
        </div>
      </div>
    </section>
  );
}
