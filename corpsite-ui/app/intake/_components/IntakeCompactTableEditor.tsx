"use client";

import * as React from "react";

export function IntakeCompactTableEditorCell({
  children,
  className = "",
  nowrap = false,
}: {
  children: React.ReactNode;
  className?: string;
  nowrap?: boolean;
}) {
  return (
    <td className={`px-3 py-2 align-top ${nowrap ? "whitespace-nowrap" : ""} ${className}`.trim()}>
      {children}
    </td>
  );
}

export const INTAKE_COMPACT_TABLE_EDITOR_ROW_CLASS =
  "border-b border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/40";

export const INTAKE_COMPACT_MOBILE_EDITOR_GRID_CLASS =
  "grid grid-cols-1 gap-3 border-t border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40 sm:grid-cols-2 lg:hidden";
