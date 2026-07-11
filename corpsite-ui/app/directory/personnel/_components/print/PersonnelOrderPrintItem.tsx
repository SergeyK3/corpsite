import type { PersonnelOrderPrintLanguage } from "../../_lib/personnelOrderPrintLanguage";
import { renderPersonnelOrderPrintItemText } from "../../_lib/personnelOrderPrintItemText";
import type { PersonnelOrderPrintItemViewModel } from "../../_lib/personnelOrderPrintViewModel";

type Props = {
  item: PersonnelOrderPrintItemViewModel;
  language: PersonnelOrderPrintLanguage;
};

export default function PersonnelOrderPrintItem({ item, language }: Props) {
  const lines = renderPersonnelOrderPrintItemText(item.context, language);

  return (
    <li
      className="personnel-order-print-item break-inside-avoid"
      data-testid={`personnel-order-print-item-${item.itemId}`}
    >
      <div className="grid grid-cols-[2rem_minmax(0,1fr)] gap-x-1">
        <div className="pt-0.5 text-right font-semibold tabular-nums">{item.itemNumber}.</div>
        <div className="min-w-0 space-y-2.5 text-left">
          {lines.map((line, index) => (
            <p key={`${item.itemId}-${index}`} className="m-0">
              {line}
            </p>
          ))}
        </div>
      </div>
    </li>
  );
}
