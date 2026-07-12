"use client";

import type { MeInfo } from "@/lib/types";

import {
  explainOperationalOrdersSectionAccessDenied,
  formatAccessDiagnosticsForDeveloper,
  isOperationalOrdersDeveloperDiagnosticsEnabled,
  type OperationalOrdersAccessDiagnostics,
} from "../_lib/accessDiagnostics";

type Props = {
  me: MeInfo | null | undefined;
  diagnostics?: OperationalOrdersAccessDiagnostics;
  title?: string;
  message?: string;
};

export default function AccessDeniedPanel({ me, diagnostics: diagnosticsOverride, title, message }: Props) {
  const explained = explainOperationalOrdersSectionAccessDenied(me);
  const diagnostics = diagnosticsOverride ?? explained.diagnostics;
  const showDev = isOperationalOrdersDeveloperDiagnosticsEnabled();
  const devLines = formatAccessDiagnosticsForDeveloper(diagnostics);

  return (
    <div
      className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-6 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100"
      data-testid="oo-access-denied"
    >
      <h2 className="text-base font-semibold">{title ?? explained.title}</h2>
      <p className="mt-2">{message ?? explained.message}</p>

      {showDev ? (
        <details className="mt-4 rounded-lg border border-amber-300/60 bg-white/60 p-3 dark:border-amber-800 dark:bg-zinc-950/40">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-200">
            Developer diagnostics
          </summary>
          <ul className="mt-2 space-y-1 font-mono text-xs text-amber-900 dark:text-amber-100" data-testid="oo-access-diagnostics">
            {devLines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
