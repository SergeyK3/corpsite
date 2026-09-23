"use client";

import {
  formatPersonnelOrderDate,
  formatPersonnelOrderNumber,
  type PersonnelOrderDetailResponse,
} from "../_lib/personnelOrdersApi.client";
import {
  renderPersonnelOrderDocument,
  type PersonnelOrderDocumentLanguage,
} from "./personnelOrderDocumentTemplates";

export type { PersonnelOrderDocumentLanguage } from "./personnelOrderDocumentTemplates";

const labels = {
  kk: {
    document: "БҰЙРЫҚ",
    number: "№",
    date: "Күні",
    basis: "Негіз",
    noTemplate: "Осы құрылымдалған деректер үшін бекітілген құжат шаблоны таңдалмаған.",
    additional: "Қосымша өкімдер",
    signatory: "Қол қоюшы",
  },
  ru: {
    document: "ПРИКАЗ",
    number: "№",
    date: "Дата",
    basis: "Основание",
    noTemplate: "Для этих структурированных данных не выбран утверждённый шаблон документа.",
    additional: "Дополнительные распоряжения",
    signatory: "Подписант",
  },
} as const;

export function personnelOrderDocumentAvailable(
  detail: PersonnelOrderDetailResponse | null,
  language: PersonnelOrderDocumentLanguage,
): boolean {
  return Boolean(detail && renderPersonnelOrderDocument(detail, language));
}

export default function PersonnelOrderDocumentView({
  detail,
  language,
}: {
  detail: PersonnelOrderDetailResponse;
  language: PersonnelOrderDocumentLanguage;
}) {
  const ui = labels[language];
  const document = renderPersonnelOrderDocument(detail, language);
  if (!document) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950 dark:border-amber-900/60 dark:bg-amber-950/35 dark:text-amber-100" data-testid="personnel-order-document-missing-template">
        {ui.noTemplate}
      </div>
    );
  }

  return (
    <article id="personnel-order-document-print" className="mx-auto max-w-3xl space-y-6 rounded-xl border border-zinc-200 bg-white p-6 text-zinc-900 shadow-sm dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100" data-testid="personnel-order-document">
      <header className="text-center">
        <div className="text-base font-semibold tracking-wide">{ui.document}</div>
        <div className="mt-3 flex flex-wrap justify-between gap-2 text-sm">
          <span>{ui.number} {formatPersonnelOrderNumber(detail.order.order_number)}</span>
          <span>{ui.date}: {formatPersonnelOrderDate(detail.order.order_date)}</span>
        </div>
        <h3 className="mt-6 text-lg font-semibold">{document.title}</h3>
      </header>

      <p className="whitespace-pre-wrap text-sm leading-6">{document.preamble}</p>
      <div className="font-semibold">{document.directive}</div>

      <ol className="list-decimal space-y-4 pl-6">
        {document.points.map((point, index) => (
          <li key={index} className="pl-1 text-sm leading-6">
            <p>{point.text}</p>
            {point.basis.length ? (
              <p className="mt-2"><span className="font-medium">{ui.basis}:</span> {point.basis.join("; ")}.</p>
            ) : null}
          </li>
        ))}
      </ol>

      {document.additionalInstructions.length ? (
        <section className="space-y-2 text-sm leading-6">
          <h4 className="font-semibold">{ui.additional}</h4>
          {document.additionalInstructions.map((instruction, index) => <p key={index}>{instruction}</p>)}
        </section>
      ) : null}

      <footer className="grid gap-3 pt-6 text-sm sm:grid-cols-[1fr_auto]">
        <div className="font-medium">{detail.order.signed_by_position || ui.signatory}</div>
        <div className="text-right">{detail.order.signed_by_name || "—"}</div>
      </footer>
    </article>
  );
}
