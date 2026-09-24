"use client";

import {
  formatPersonnelOrderDate,
  formatPersonnelOrderNumber,
  type PersonnelOrderEditorialState,
  type PersonnelOrderDetailResponse,
} from "../_lib/personnelOrdersApi.client";
import {
  renderPersonnelOrderDocument,
  type PersonnelOrderDocumentLanguage,
} from "./personnelOrderDocumentTemplates";
import {
  normalizePersonnelOrderSignatoryRole,
  personnelOrderSignatoryRoleLabel,
} from "../_lib/personnelOrderSignatoryRole";

export type { PersonnelOrderDocumentLanguage } from "./personnelOrderDocumentTemplates";

const labels = {
  kk: {
    document: "БҰЙРЫҚ",
    number: "№",
    date: "Күні",
    basis: "Негіз",
    noTemplate: "Бұл бұйрық түрі үшін бекітілген шаблон әзірге жоқ.",
    additional: "Қосымша өкімдер",
  },
  ru: {
    document: "ПРИКАЗ",
    number: "№",
    date: "Дата",
    basis: "Основание",
    noTemplate: "Для этого типа приказа утверждённый шаблон пока отсутствует.",
    additional: "Дополнительные распоряжения",
  },
} as const;

function signatoryPosition(position: string, language: PersonnelOrderDocumentLanguage): string {
  const role = normalizePersonnelOrderSignatoryRole(position);
  return role ? personnelOrderSignatoryRoleLabel(role, language) : position;
}

export function personnelOrderDocumentAvailable(
  detail: PersonnelOrderDetailResponse | null,
  language: PersonnelOrderDocumentLanguage,
  editorial?: PersonnelOrderEditorialState | null,
): boolean {
  return Boolean(detail && renderPersonnelOrderDocument(detail, language, editorial));
}

export default function PersonnelOrderDocumentView({
  detail,
  language,
  editorial = null,
  printRoot = false,
}: {
  detail: PersonnelOrderDetailResponse;
  language: PersonnelOrderDocumentLanguage;
  editorial?: PersonnelOrderEditorialState | null;
  /** The sole direct-body document included in an in-place browser print. */
  printRoot?: boolean;
}) {
  const ui = labels[language];
  const document = renderPersonnelOrderDocument(detail, language, editorial);
  if (!document) {
    return (
      <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950 dark:border-amber-900/60 dark:bg-amber-950/35 dark:text-amber-100" data-testid="personnel-order-document-missing-template">
        {ui.noTemplate}
      </div>
    );
  }

  return (
    <article
      id={printRoot ? "personnel-order-active-print-root" : undefined}
      className="mx-auto max-w-3xl space-y-6 rounded-xl border border-zinc-200 bg-white p-6 text-zinc-900 shadow-sm dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100"
      data-personnel-order-active-print-root={printRoot ? "true" : undefined}
      data-testid={printRoot ? "personnel-order-active-print-root" : "personnel-order-document"}
    >
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

      {detail.order.signed_by_position && detail.order.signed_by_name ? (
        <footer className="grid gap-3 pt-6 text-sm sm:grid-cols-[1fr_auto]">
          <div className="font-medium">{signatoryPosition(detail.order.signed_by_position, language)}</div>
          <div className="text-right">{detail.order.signed_by_name}</div>
        </footer>
      ) : (
        <p className="print:hidden rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-900/60 dark:bg-amber-950/35 dark:text-amber-100" role="alert">
          {language === "kk" ? "Басшының қолы анықталмады: құжат DOCX-пен тексерілген деп саналмайды." : "Подпись руководителя не установлена: документ не считается проверенным по DOCX."}
        </p>
      )}
    </article>
  );
}
