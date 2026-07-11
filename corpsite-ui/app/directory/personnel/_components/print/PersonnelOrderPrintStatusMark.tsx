import type { PersonnelOrderPrintLanguage } from "../../_lib/personnelOrderPrintLanguage";
import { statusMarkLinesForLanguage } from "../../_lib/personnelOrderPrintLocale";
import type { PersonnelOrderPrintStatusMark } from "../../_lib/personnelOrderPrintViewModel";

type Props = {
  statusMark: PersonnelOrderPrintStatusMark;
  language: PersonnelOrderPrintLanguage;
};

export default function PersonnelOrderPrintStatusMark({ statusMark, language }: Props) {
  if (statusMark === "none") return null;

  const lines = statusMarkLinesForLanguage(statusMark, language);

  return (
    <div
      className="personnel-order-print-watermark pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden"
      aria-hidden="true"
      data-testid="personnel-order-print-status-mark"
      data-status-mark={statusMark}
    >
      <div className="rotate-[-28deg] text-center text-3xl font-bold uppercase tracking-widest text-zinc-400/55 select-none sm:text-4xl print:text-zinc-300/70">
        {lines.map((line) => (
          <div key={line} className="leading-tight">
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}
