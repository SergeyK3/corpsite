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
import { buildPersonnelOrderPrintViewModel } from "../_lib/personnelOrderPrintViewModel";

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

function acknowledgementName(fullName: string | null, language: PersonnelOrderDocumentLanguage): string {
  const parts = String(fullName || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length < 2) return "";
  return language === "kk" ? `${parts[1][0]}. ${parts[0]}` : `${parts[0]} ${parts[1][0]}.`;
}

function acknowledgementDate(value: string | null, language: PersonnelOrderDocumentLanguage): string {
  if (value) return new Date(`${value}T00:00:00`).toLocaleDateString("ru-RU");
  return language === "kk" ? "«___» ______________ 20___ ж." : "«___» ______________ 20___ г.";
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
  const printModel = buildPersonnelOrderPrintViewModel(detail, { editorial });
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
      <div className="text-center font-semibold">{document.directive}</div>

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

      {document.informationLines?.length ? (
        <section className="space-y-2 text-sm leading-6" data-testid="personnel-order-document-information">
          {document.informationLines.map((line, index) => <p key={index}>{line}</p>)}
        </section>
      ) : null}

      {document.additionalInstructions.length ? (
        <section className="space-y-2 text-sm leading-6">
          <h4 className="font-semibold">{ui.additional}</h4>
          {document.additionalInstructions.map((instruction, index) => <p key={index}>{instruction}</p>)}
        </section>
      ) : null}

      <footer className="space-y-5 pt-6 text-sm" data-testid="personnel-order-document-footer">
        <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto]">
          <div className="font-medium">
            {printModel.signatory.position?.[language]
              || (detail.order.signed_by_position ? signatoryPosition(detail.order.signed_by_position, language) : "Директор")}
          </div>
          <div className="border-b border-zinc-500 px-12" aria-label="Подпись директора" />
          <div>{printModel.signatory.fio || detail.order.signed_by_name || ""}</div>
        </div>
        <section className="space-y-4" data-testid="personnel-order-document-acknowledgement">
          {(printModel.acknowledgements.length ? printModel.acknowledgements : [{ employeeId: null, employeeName: null, acknowledgedOn: null }]).map((row, index) => (
            <div key={`${row.employeeId ?? "unresolved"}-${index}`} className="space-y-1">
              <p>{language === "kk" ? "Бұйрықпен таныстым:" : "С приказом ознакомлен(а):"} <span className="inline-block min-w-48 border-b border-zinc-500" />&nbsp;&nbsp;{acknowledgementName(row.employeeName, language)}</p>
              <p>{acknowledgementDate(row.acknowledgedOn, language)}</p>
            </div>
          ))}
        </section>
        <p data-testid="personnel-order-document-executor">{language === "kk" ? "Орындаушы" : "Исполнитель"}: {printModel.executorName}</p>
      </footer>
    </article>
  );
}
