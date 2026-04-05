// FILE: corpsite-ui/app/regular-tasks/_components/TemplateDrawer.tsx
"use client";

import * as React from "react";

type TemplateDrawerProps = {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: React.ReactNode;
};

export default function TemplateDrawer({
  open,
  title,
  subtitle,
  onClose,
  children,
}: TemplateDrawerProps) {
  React.useEffect(() => {
    if (!open) return;

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }

    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto p-4 sm:p-6">
      <button
        type="button"
        aria-label="Закрыть"
        className="fixed inset-0 bg-zinc-600/35 dark:bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="template-drawer-title"
        className="relative z-10 flex w-full max-w-[920px] flex-col rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-2xl max-h-[min(920px,calc(100vh-2rem))] min-h-0"
      >
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-zinc-200 dark:border-zinc-800 px-6 py-5">
          <div className="min-w-0">
            <h2 id="template-drawer-title" className="truncate text-2xl font-semibold leading-tight text-zinc-900 dark:text-zinc-50">
              {title}
            </h2>
            {subtitle ? <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{subtitle}</p> : null}
          </div>

          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
          >
            Закрыть
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}