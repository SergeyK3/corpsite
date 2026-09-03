"use client";

import * as React from "react";

import { useCurrentUser } from "@/lib/currentUser";
import {
  ControlListExportUiError,
  exportControlListFile,
} from "../_lib/controlListExport.client";

function errorMessage(error: unknown): string {
  if (error instanceof ControlListExportUiError) {
    if (error.kind === "FORBIDDEN") {
      return "Недостаточно прав для экспорта контрольного списка";
    }
    if (error.kind === "CONFLICT") {
      return "Обнаружены ошибки основных назначений. Файл не сформирован.";
    }
    if (error.kind === "WRITE") {
      return "Не удалось записать выбранный файл. Повторный запрос к серверу не выполнялся.";
    }
    if (error.kind === "INTEGRITY") {
      return "Не удалось проверить целостность файла. Файл не сохранён.";
    }
  }
  return "Не удалось сформировать файл. Повторите попытку или обратитесь к администратору";
}

export default function ControlListExportPageClient() {
  const me = useCurrentUser();
  const [busy, setBusy] = React.useState(false);
  const [message, setMessage] = React.useState<string | null>(null);
  const [isError, setIsError] = React.useState(false);
  const inFlight = React.useRef(false);

  if (me?.has_control_list_export !== true) {
    return (
      <section className="p-4 sm:p-6" aria-labelledby="control-list-export-title">
        <h2 id="control-list-export-title" className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          Экспорт контрольного списка
        </h2>
        <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">
          Недостаточно прав для экспорта контрольного списка.
        </p>
      </section>
    );
  }

  async function onExportClick() {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setMessage(null);
    setIsError(false);
    try {
      const outcome = await exportControlListFile();
      if (outcome === "cancelled") return;
      setMessage(
        outcome === "saved"
          ? "Файл сформирован и сохранён в выбранном месте."
          : "Файл сформирован. Сохранение выполняется браузером.",
      );
    } catch (error) {
      setIsError(true);
      setMessage(errorMessage(error));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  return (
    <section className="p-4 sm:p-6" aria-labelledby="control-list-export-title">
      <div className="max-w-2xl rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-950 sm:p-5">
        <h2 id="control-list-export-title" className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          Экспорт контрольного списка
        </h2>
        <p className="mt-2 text-sm leading-6 text-zinc-700 dark:text-zinc-300">
          В файл выгружаются данные активного персонала в пределах доступного организационного охвата.
          Файл содержит персональные данные и требует защищённой обработки.
        </p>
        <button
          type="button"
          className="mt-4 inline-flex min-h-10 items-center justify-center rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-blue-600 dark:hover:bg-blue-500"
          disabled={busy}
          aria-busy={busy}
          onClick={() => void onExportClick()}
        >
          {busy ? "Формирование файла…" : "Экспортировать в Excel"}
        </button>
        {message ? (
          <p
            className={`mt-3 text-sm ${isError ? "text-red-800 dark:text-red-200" : "text-zinc-700 dark:text-zinc-300"}`}
            role={isError ? "alert" : "status"}
          >
            {message}
          </p>
        ) : null}
      </div>
    </section>
  );
}
