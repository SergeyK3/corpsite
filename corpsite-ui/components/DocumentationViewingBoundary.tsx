"use client";

import { useEffect, useRef, type ReactNode } from "react";

// Convenience only. The server's operation policy and read-only transactions
// enforce the restriction, including requests outside this UI.
const MUTATION_ACTION = /^(сохранить|опубликовать|удалить|применить|зарегистрировать|подписать|заблокировать|разблокировать|подтвердить|отклонить|аннулировать|архивировать|восстановить|выдать|назначить|отозвать|сформировать текст|требовать смену пароля)/i;

const ASSISTANT_MUTATION_ACTION = /^(добавить|создать|изменить|редактировать|переименовать|переместить|деактивировать|активировать|импортировать|загрузить|очистить|сохранить|опубликовать|удалить|применить|зарегистрировать|подписать|заблокировать|разблокировать|подтвердить|отклонить|аннулировать|архивировать|восстановить|выдать|назначить|отозвать|сформировать текст|требовать смену пароля)/i;

export default function DocumentationViewingBoundary({ children, assistant = false }: { children: ReactNode; assistant?: boolean }) {
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!assistant || !root.current) return;
    const disableMutations = () => root.current?.querySelectorAll("button").forEach(button => {
      if (ASSISTANT_MUTATION_ACTION.test(button.textContent?.trim() ?? "")) {
        button.disabled = true;
        button.hidden = true;
        button.style.display = "none";
        button.title = "Для помощника этот раздел доступен только для просмотра и выгрузки.";
      }
    });
    disableMutations();
    const observer = new MutationObserver(disableMutations);
    observer.observe(root.current, { childList: true, subtree: true, characterData: true });
    return () => observer.disconnect();
  }, [assistant]);
  return <div ref={root} onSubmitCapture={event => {
    const form = event.target as HTMLFormElement;
    const submitter = (event.nativeEvent as SubmitEvent).submitter ?? form.querySelector("button[type=submit]");
    if (assistant && /^(обновить|найти|поиск)/i.test(submitter?.textContent?.trim() ?? "")) return;
    event.preventDefault(); event.stopPropagation();
  }}
    onClickCapture={event => {
      const target = event.target as HTMLElement;
      const button = target.closest("button");
      if (button && (assistant ? ASSISTANT_MUTATION_ACTION : MUTATION_ACTION).test(button.textContent?.trim() ?? "")) {
        event.preventDefault(); event.stopPropagation();
      }
    }}>
    <p role="status" className="mb-3 rounded-lg border border-blue-300 bg-blue-50 p-3 text-sm text-blue-950 dark:bg-blue-950 dark:text-blue-100">
      {assistant ? "Этот раздел доступен помощнику для просмотра и Excel-выгрузок. Изменение справочников, шаблонов, настроек и аккаунтов закрыто."
        : "Подготовка руководства: режим просмотра. Формы можно открывать и изучать; изменения не сохраняются."}
    </p>
    {children}
  </div>;
}
