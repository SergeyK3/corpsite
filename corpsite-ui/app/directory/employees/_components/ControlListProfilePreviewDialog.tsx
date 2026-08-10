"use client";

import * as React from "react";

import ImportProfileCardSections from "../../personnel/_components/ImportProfileCardSections";
import type { EducationProfileDetail } from "../../personnel/_lib/importApi.client";

type Props = {
  detail: EducationProfileDetail | null;
  open: boolean;
  onClose: () => void;
};

export default function ControlListProfilePreviewDialog({ detail, open, onClose }: Props) {
  React.useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open || !detail) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-zinc-600/35 dark:bg-black/50" onClick={onClose} />
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="control-list-profile-preview-title"
        className="relative flex max-h-[calc(100vh-2rem)] w-full max-w-5xl flex-col rounded-2xl border border-zinc-200 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-950"
      >
        <header className="flex items-start justify-between gap-4 border-b border-zinc-200 p-5 dark:border-zinc-800">
          <div>
            <h2 id="control-list-profile-preview-title" className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              Предварительный просмотр импортной карточки
            </h2>
            <p className="mt-1 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
              Предварительный просмотр данных контрольного списка. Данные ещё не перенесены в постоянную личную карточку.
            </p>
          </div>
          <button type="button" onClick={onClose} className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-50">
            Закрыть
          </button>
        </header>
        <div className="overflow-y-auto p-5">
          <p className="mb-4 text-sm text-zinc-600 dark:text-zinc-400">
            Импорт {detail.batch_id} · исходная строка {detail.row_id}
          </p>
          <ImportProfileCardSections
            profile={detail.profile}
            departmentCanonical={detail.department_recoding?.org_unit_name}
            onProfileChange={() => undefined}
          />
        </div>
      </section>
    </div>
  );
}
