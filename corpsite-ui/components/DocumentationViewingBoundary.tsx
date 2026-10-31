"use client";

import type { ReactNode } from "react";

// Convenience only. The server's operation policy and read-only transactions
// enforce the restriction, including requests outside this UI.
const MUTATION_ACTION = /^(сохранить|опубликовать|удалить|применить|зарегистрировать|подписать|заблокировать|разблокировать|подтвердить|отклонить|аннулировать|архивировать|восстановить|выдать|назначить|отозвать|сформировать текст|требовать смену пароля)/i;

export default function DocumentationViewingBoundary({ children }: { children: ReactNode }) {
  return <div onSubmitCapture={event => { event.preventDefault(); event.stopPropagation(); }}
    onClickCapture={event => {
      const target = event.target as HTMLElement;
      const button = target.closest("button");
      if (button && MUTATION_ACTION.test(button.textContent?.trim() ?? "")) {
        event.preventDefault(); event.stopPropagation();
      }
    }}>
    <p role="status" className="mb-3 rounded-lg border border-blue-300 bg-blue-50 p-3 text-sm text-blue-950 dark:bg-blue-950 dark:text-blue-100">
      Подготовка руководства: режим просмотра. Формы можно открывать и изучать; изменения не сохраняются.
    </p>
    {children}
  </div>;
}
