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
        className="fixed inset-0 bg-zinc-600/35 backdrop-blur-sm"
        onClick={onClose}
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="task-drawer-title"
        className="relative z-10 flex w-full max-w-[840px] flex-col rounded-2xl border border-zinc-200 bg-white shadow-2xl max-h-[min(920px,calc(100vh-2rem))] min-h-0"
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-zinc-200 px-5 py-4">
          <div className="min-w-0">
            <h2 id="task-drawer-title" className="truncate text-2xl font-semibold leading-tight text-zinc-900">
              {title}
            </h2>
            {subtitle ? <p className="mt-0.5 text-sm text-zinc-600">{subtitle}</p> : null}
          </div>

          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-lg border border-zinc-200 bg-zinc-100 px-3 py-1.5 text-sm text-zinc-800 transition hover:bg-zinc-200"
          >
            Закрыть
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}