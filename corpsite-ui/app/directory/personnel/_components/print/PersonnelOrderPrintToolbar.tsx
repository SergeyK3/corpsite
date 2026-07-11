"use client";

import * as React from "react";
import Link from "next/link";

import {
  PERSONNEL_ORDER_PRINT_LANGUAGE_LABELS,
  PERSONNEL_ORDER_PRINT_LANGUAGES,
  type PersonnelOrderPrintLanguage,
} from "../../_lib/personnelOrderPrintLanguage";

type Props = {
  backHref: string;
  language: PersonnelOrderPrintLanguage;
  onLanguageChange: (language: PersonnelOrderPrintLanguage) => void;
  onOpenPdf?: () => void;
  pdfBusy?: boolean;
};

export default function PersonnelOrderPrintToolbar({
  backHref,
  language,
  onLanguageChange,
  onOpenPdf,
  pdfBusy = false,
}: Props) {
  return (
    <div
      className="print:hidden mb-4 space-y-2 rounded-xl border border-zinc-200 bg-white px-3 py-2 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
      data-testid="personnel-order-print-toolbar"
    >
      <div className="flex flex-wrap items-center gap-3">
        <Link
          href={backHref}
          className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
        >
          Назад
        </Link>
        <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
          <span>Язык:</span>
          <select
            value={language}
            onChange={(e) => onLanguageChange(e.target.value as PersonnelOrderPrintLanguage)}
            className="rounded-lg border border-zinc-300 bg-white px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            data-testid="personnel-order-print-language-select"
          >
            {PERSONNEL_ORDER_PRINT_LANGUAGES.map((value) => (
              <option key={value} value={value}>
                {PERSONNEL_ORDER_PRINT_LANGUAGE_LABELS[value]}
              </option>
            ))}
          </select>
        </label>
        {onOpenPdf ? (
          <button
            type="button"
            onClick={onOpenPdf}
            disabled={pdfBusy}
            className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
            data-testid="personnel-order-print-pdf-button"
          >
            {pdfBusy ? "PDF…" : "PDF / Печать"}
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => window.print()}
          className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
          data-testid="personnel-order-print-button"
        >
          Печать HTML
        </button>
      </div>
      <p
        className="print:hidden max-w-3xl text-xs leading-snug text-zinc-500 dark:text-zinc-400"
        data-testid="personnel-order-print-headers-hint"
      >
        Для печати из HTML без даты, URL и номера страницы отключите «Дополнительные настройки →
        Колонтитулы» в диалоге браузера. Официальный документ — кнопка «PDF / Печать».
      </p>
    </div>
  );
}
