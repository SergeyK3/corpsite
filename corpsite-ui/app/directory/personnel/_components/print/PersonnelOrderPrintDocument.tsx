import type { PersonnelOrderPrintLanguage } from "../../_lib/personnelOrderPrintLanguage";
import type { PersonnelOrderPrintViewModel } from "../../_lib/personnelOrderPrintViewModel";
import PersonnelOrderPrintAcknowledgement from "./PersonnelOrderPrintAcknowledgement";
import PersonnelOrderPrintBasis from "./PersonnelOrderPrintBasis";
import PersonnelOrderPrintHeader from "./PersonnelOrderPrintHeader";
import PersonnelOrderPrintItems from "./PersonnelOrderPrintItems";
import PersonnelOrderPrintSignature from "./PersonnelOrderPrintSignature";
import PersonnelOrderPrintStatusMark from "./PersonnelOrderPrintStatusMark";

type Props = {
  model: PersonnelOrderPrintViewModel;
  language: PersonnelOrderPrintLanguage;
};

export default function PersonnelOrderPrintDocument({ model, language }: Props) {
  return (
    <article
      className="personnel-order-print-document relative mx-auto bg-white text-black"
      data-testid="personnel-order-print-document"
      data-language={language}
      data-status={model.status}
    >
      <PersonnelOrderPrintStatusMark statusMark={model.statusMark} language={language} />
      <div className="relative z-10 space-y-8">
        <PersonnelOrderPrintHeader model={model} language={language} />
        <PersonnelOrderPrintItems model={model} language={language} />
        <PersonnelOrderPrintBasis basis={model.basis} language={language} />
        <PersonnelOrderPrintSignature signatory={model.signatory} language={language} />
        <PersonnelOrderPrintAcknowledgement
          acknowledgements={model.acknowledgements}
          language={language}
        />
      </div>
    </article>
  );
}
