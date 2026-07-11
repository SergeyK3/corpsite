import type { PersonnelOrderPrintLanguage } from "../../_lib/personnelOrderPrintLanguage";
import { primaryPrintDictionary, printDictionariesForLanguage } from "../../_lib/personnelOrderPrintLocale";
import { resolveLocalizedLines } from "../../_lib/personnelOrderPrintLocalized";
import type { PersonnelOrderPrintViewModel } from "../../_lib/personnelOrderPrintViewModel";
import PersonnelOrderPrintItem from "./PersonnelOrderPrintItem";

type Props = {
  model: PersonnelOrderPrintViewModel;
  language: PersonnelOrderPrintLanguage;
};

export default function PersonnelOrderPrintItems({ model, language }: Props) {
  const dictionaries = printDictionariesForLanguage(language);
  const preambleLines = model.preamble
    ? resolveLocalizedLines(model.preamble, language)
    : [];

  return (
    <section className="space-y-5" data-testid="personnel-order-print-items">
      {preambleLines.length > 0 ? (
        <div className="personnel-order-print-block space-y-1.5 text-left">
          {preambleLines.map((line) => (
            <p key={line} className="m-0">
              {line}
            </p>
          ))}
        </div>
      ) : null}

      <div className="personnel-order-print-block personnel-order-print-order-verb space-y-0.5 text-center uppercase tracking-wide">
        {dictionaries.map((dict) => (
          <div key={dict.orderVerb}>{dict.orderVerb}</div>
        ))}
      </div>

      {model.items.length === 0 ? (
        <p>{primaryPrintDictionary(language).itemsEmpty}</p>
      ) : (
        <ol className="m-0 list-none space-y-5 p-0">
          {model.items.map((item) => (
            <PersonnelOrderPrintItem key={item.itemId} item={item} language={language} />
          ))}
        </ol>
      )}
    </section>
  );
}
