"use client";

import {
  buildPersonnelOrderDocumentRequisitesDisplay,
  hasPersonnelOrderRequisitesDate,
  hasPersonnelOrderSignatory,
} from "../_lib/personnelOrderDocumentRequisites";
import type { PersonnelOrderEditorialUiLocale } from "../_lib/personnelOrderEditorialUi";
import type { PersonnelOrderHeader } from "../_lib/personnelOrdersApi.client";

type Props = {
  order: Pick<PersonnelOrderHeader, "order_date" | "signed_by_name" | "signed_by_position">;
  locale: PersonnelOrderEditorialUiLocale;
};

const REQUISITES_HINT =
  "Дата и подписант задаются в блоке «Реквизиты» заголовка приказа, а не в заключительной части.";

export default function PersonnelOrderDocumentRequisitesPreview({ order, locale }: Props) {
  const display = buildPersonnelOrderDocumentRequisitesDisplay(order, locale);
  const showDate = hasPersonnelOrderRequisitesDate(display.orderDate);
  const showSignatory = hasPersonnelOrderSignatory(display.signatory);

  if (!showDate && !showSignatory) {
    return (
      <div
        className="rounded-lg border border-dashed border-zinc-300 bg-zinc-50/60 px-3 py-2 text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900/30 dark:text-zinc-400"
        data-testid="personnel-order-requisites-preview-empty"
      >
        <p>{REQUISITES_HINT}</p>
        <p className="mt-1 text-xs">Заполните дату приказа и подписанта в разделе «Заголовок».</p>
      </div>
    );
  }

  return (
    <div
      className="space-y-4 rounded-lg border border-zinc-200 bg-white px-3 py-3 dark:border-zinc-800 dark:bg-zinc-950/40"
      data-testid="personnel-order-requisites-preview"
    >
      <p className="text-xs text-zinc-500">{REQUISITES_HINT}</p>

      {showDate ? (
        <div
          className="text-sm text-zinc-900 dark:text-zinc-100"
          data-testid="personnel-order-requisites-date"
        >
          {display.formattedDate}
        </div>
      ) : (
        <p
          className="text-sm text-zinc-400 dark:text-zinc-500"
          data-testid="personnel-order-requisites-date-missing"
        >
          Дата приказа не указана
        </p>
      )}

      {showSignatory ? (
        <div
          className="grid grid-cols-[minmax(0,1.2fr)_minmax(7rem,1fr)_minmax(0,1.2fr)] items-end gap-x-4 gap-y-1 text-sm"
          data-testid="personnel-order-requisites-signatory"
        >
          <div
            className="min-w-0 leading-snug text-zinc-900 dark:text-zinc-100"
            data-testid="personnel-order-requisites-signatory-position"
          >
            {display.signatory.position || "\u00a0"}
          </div>
          <div
            className="border-b border-zinc-400 pb-0.5 dark:border-zinc-600"
            aria-hidden="true"
          />
          <div
            className="min-w-0 text-right font-medium leading-snug text-zinc-900 dark:text-zinc-100"
            data-testid="personnel-order-requisites-signatory-fio"
          >
            {display.signatory.fio || "\u00a0"}
          </div>
        </div>
      ) : (
        <p
          className="text-sm text-zinc-400 dark:text-zinc-500"
          data-testid="personnel-order-requisites-signatory-missing"
        >
          Подписант не указан
        </p>
      )}
    </div>
  );
}
