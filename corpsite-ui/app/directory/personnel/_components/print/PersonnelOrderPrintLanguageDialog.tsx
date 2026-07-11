"use client";

import * as React from "react";

import {
  PERSONNEL_ORDER_PRINT_LANGUAGE_DEFAULT,
  PERSONNEL_ORDER_PRINT_LANGUAGE_LABELS,
  PERSONNEL_ORDER_PRINT_LANGUAGES,
  type PersonnelOrderPrintLanguage,
} from "../../_lib/personnelOrderPrintLanguage";

type Props = {
  open: boolean;
  onClose: () => void;
  onConfirm: (language: PersonnelOrderPrintLanguage) => void;
  initialLanguage?: PersonnelOrderPrintLanguage;
};

export default function PersonnelOrderPrintLanguageDialog({
  open,
  onClose,
  onConfirm,
  initialLanguage = PERSONNEL_ORDER_PRINT_LANGUAGE_DEFAULT,
}: Props) {
  const [language, setLanguage] = React.useState<PersonnelOrderPrintLanguage>(initialLanguage);

  React.useEffect(() => {
    if (open) setLanguage(initialLanguage);
  }, [open, initialLanguage]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4"
      data-testid="personnel-order-print-language-dialog"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="personnel-order-print-dialog-title"
        className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-5 shadow-xl dark:border-zinc-800 dark:bg-zinc-950"
      >
        <h2
          id="personnel-order-print-dialog-title"
          className="text-lg font-semibold text-zinc-900 dark:text-zinc-50"
        >
          Печатная форма
        </h2>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Язык документа:</p>

        <div className="mt-4 space-y-2">
          {PERSONNEL_ORDER_PRINT_LANGUAGES.map((value) => (
            <label
              key={value}
              className="flex cursor-pointer items-center gap-2 rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800"
            >
              <input
                type="radio"
                name="personnel-order-print-language"
                value={value}
                checked={language === value}
                onChange={() => setLanguage(value)}
              />
              <span>{PERSONNEL_ORDER_PRINT_LANGUAGE_LABELS[value]}</span>
            </label>
          ))}
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700"
          >
            Отмена
          </button>
          <button
            type="button"
            data-testid="personnel-order-print-open"
            onClick={() => onConfirm(language)}
            className="rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
          >
            Открыть печатную форму
          </button>
        </div>
      </div>
    </div>
  );
}
