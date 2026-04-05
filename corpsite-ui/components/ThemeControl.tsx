// FILE: corpsite-ui/components/ThemeControl.tsx
"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "corpsite_ui_theme";

export type UiThemeMode = "work" | "document";

function applyMode(mode: UiThemeMode) {
  const root = document.documentElement;
  if (mode === "document") root.classList.remove("dark");
  else root.classList.add("dark");
}

export default function ThemeControl() {
  const [mounted, setMounted] = useState(false);
  const [mode, setMode] = useState<UiThemeMode>("work");

  useEffect(() => {
    setMounted(true);
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as UiThemeMode | null;
      const initial: UiThemeMode = stored === "document" ? "document" : "work";
      setMode(initial);
      applyMode(initial);
    } catch {
      setMode("work");
      applyMode("work");
    }
  }, []);

  const toggle = () => {
    const next: UiThemeMode = mode === "document" ? "work" : "document";
    setMode(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
    applyMode(next);
  };

  if (!mounted) {
    return (
      <span
        className="inline-block h-7 min-w-[11rem] rounded-md border border-transparent"
        aria-hidden
      />
    );
  }

  const label =
    mode === "document" ? "Рабочая тема" : "Режим для документов";

  return (
    <button
      type="button"
      onClick={toggle}
      className="rounded-md border border-zinc-200 bg-zinc-100 px-2.5 py-1 text-xs font-medium text-zinc-800 hover:bg-zinc-200 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
      title={
        mode === "document"
          ? "Вернуть тёмную тему для ежедневной работы"
          : "Временно включить светлую тему для скриншотов и печати"
      }
    >
      {label}
    </button>
  );
}
