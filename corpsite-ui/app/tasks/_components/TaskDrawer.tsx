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
    <div className="fixed inset-0 z-50 flex">
      <button
        type="button"
        aria-label="Закрыть"
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      <div className="relative ml-auto flex h-full w-full max-w-[840px] flex-col border-l border-zinc-800 bg-[#050816] shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-zinc-800 px-5 py-4">
          <div className="min-w-0">
            <h2 className="truncate text-2xl font-semibold leading-tight text-zinc-100">{title}</h2>
            {subtitle ? <p className="mt-0.5 text-sm text-zinc-400">{subtitle}</p> : null}
          </div>

          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-1.5 text-sm text-zinc-200 transition hover:bg-zinc-900/60"
          >
            Закрыть
          </button>
        </div>

        <div className="min-h-0 flex-1">{children}</div>
      </div>
    </div>
  );
}