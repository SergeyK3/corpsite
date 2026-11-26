"use client";

import { useCurrentUser } from "@/lib/currentUser";

type Props = { testIdPrefix: string };

export default function HiringDocumentChecklistActions({ testIdPrefix }: Props) {
  const me = useCurrentUser();
  const canEditChecklist =
    me?.has_personnel_admin === true || me?.is_system_admin === true || me?.is_privileged === true || String(me?.role_code ?? "").toUpperCase() === "HR_HEAD";

  return <div className="flex flex-wrap gap-2" data-testid={`${testIdPrefix}-checklist-actions`}>
    <button
      type="button"
      onClick={() => window.open("/directory/personnel/hiring-document-checklist", "_blank", "noopener,noreferrer")}
      className="rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
      data-testid={`${testIdPrefix}-print-checklist`}
    >
      Распечатать перечень документов
    </button>
    {canEditChecklist ? <button
      type="button"
      onClick={() => window.open("/directory/personnel/hiring-document-checklist?edit=1", "_blank", "noopener,noreferrer")}
      className="rounded-lg border border-zinc-300 px-3 py-2 text-sm hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
      data-testid={`${testIdPrefix}-edit-checklist`}
    >
      Редактировать шаблон
    </button> : null}
  </div>;
}
