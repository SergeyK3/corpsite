"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { mapPersonnelOrdersApiError, PERSONNEL_ORDERS_BASE_PATH } from "../../_lib/personnelOrdersApi.client";
import {
  PERSONNEL_ORDER_PRINT_LANGUAGE_DEFAULT,
  buildPersonnelOrderPrintHref,
  parsePersonnelOrderPrintLanguage,
  type PersonnelOrderPrintLanguage,
} from "../../_lib/personnelOrderPrintLanguage";
import { openPersonnelOrderPdf } from "../../_lib/personnelOrderPdfOpen.client";
import { loadPersonnelOrderPrintViewModelClient } from "../../_lib/personnelOrderPrintLoad.client";
import type { PersonnelOrderPrintViewModel } from "../../_lib/personnelOrderPrintViewModel";
import PersonnelOrderPrintDocument from "./PersonnelOrderPrintDocument";
import PersonnelOrderPrintToolbar from "./PersonnelOrderPrintToolbar";

type Props = {
  orderId: number;
};

export default function PersonnelOrderPrintPageClient({ orderId }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const languageParam = searchParams.get("language");
  const freshParam = searchParams.get("v");
  const parsedLanguage = parsePersonnelOrderPrintLanguage(languageParam, {
    fallbackToDefault: false,
  });
  const languageInvalid = Boolean(languageParam && parsedLanguage == null);
  const language: PersonnelOrderPrintLanguage =
    parsedLanguage ?? PERSONNEL_ORDER_PRINT_LANGUAGE_DEFAULT;

  const [model, setModel] = React.useState<PersonnelOrderPrintViewModel | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [pdfBusy, setPdfBusy] = React.useState(false);
  const [pdfError, setPdfError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const { model: nextModel } = await loadPersonnelOrderPrintViewModelClient(orderId);
        if (cancelled) return;
        setModel(nextModel);
      } catch (e) {
        if (cancelled) return;
        setModel(null);
        setError(mapPersonnelOrdersApiError(e, "Не удалось загрузить приказ для печати."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [orderId, freshParam]);

  function handleLanguageChange(next: PersonnelOrderPrintLanguage) {
    router.replace(buildPersonnelOrderPrintHref(orderId, next));
  }

  async function handleOpenPdf() {
    setPdfBusy(true);
    setPdfError(null);
    const result = await openPersonnelOrderPdf(orderId, language);
    setPdfBusy(false);
    if (!result.ok) setPdfError(result.error);
  }

  return (
    <div className="personnel-order-print-page min-h-screen bg-zinc-100 px-3 py-4 text-zinc-900 dark:bg-zinc-900 dark:text-zinc-50">
      <div className="mx-auto max-w-[210mm]">
        <PersonnelOrderPrintToolbar
          backHref={`${PERSONNEL_ORDERS_BASE_PATH}?order_id=${orderId}`}
          language={language}
          onLanguageChange={handleLanguageChange}
          onOpenPdf={handleOpenPdf}
          pdfBusy={pdfBusy}
        />

        {languageInvalid ? (
          <div
            className="print:hidden mb-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
            data-testid="personnel-order-print-language-fallback"
          >
            Неизвестный язык «{languageParam}». Показан русский вариант.
          </div>
        ) : null}

        {loading ? (
          <div className="rounded-xl border border-zinc-200 bg-white px-4 py-8 text-sm text-zinc-500">
            Загрузка печатной формы…
          </div>
        ) : null}

        {error ? (
          <div
            className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
            data-testid="personnel-order-print-error"
          >
            {error}
          </div>
        ) : null}

        {pdfError ? (
          <div
            className="print:hidden mb-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
            data-testid="personnel-order-pdf-error"
          >
            {pdfError}
          </div>
        ) : null}

        {model ? (
          <div className="personnel-order-print-sheet rounded-sm border border-zinc-200 bg-white p-8 shadow-sm dark:border-zinc-700 sm:p-10">
            <PersonnelOrderPrintDocument model={model} language={language} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
