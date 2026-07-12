"use client";

import type { DocumentTimelineStep } from "../_lib/documentTimeline";

type Props = { steps: DocumentTimelineStep[] };

const STATE_CLASS: Record<string, string> = {
  completed: "border-emerald-300 bg-emerald-50 text-emerald-900",
  current: "border-blue-400 bg-blue-50 text-blue-900 ring-2 ring-blue-200",
  future: "border-zinc-200 bg-zinc-50 text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900",
  deferred: "border-dashed border-zinc-300 bg-zinc-50 text-zinc-400 dark:border-zinc-600",
};

export default function DocumentLifecycleTimeline({ steps }: Props) {
  return (
    <section className="rounded-xl border p-4 dark:border-zinc-800" data-testid="document-lifecycle-timeline">
      <h3 className="mb-3 text-sm font-semibold">Жизненный цикл документа</h3>
      <ol className="space-y-2">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className={`rounded-lg border px-3 py-2 text-sm ${STATE_CLASS[step.state]}`}
            data-testid={`document-timeline-step-${step.id}`}
            data-state={step.state}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs opacity-60">{index + 1}.</span>
              <span className="font-medium">{step.label}</span>
              {step.state === "deferred" ? (
                <span className="rounded bg-zinc-200 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-zinc-600">
                  {step.note ?? "Ещё не реализовано"}
                </span>
              ) : null}
            </div>
            {step.note && step.state !== "deferred" ? (
              <div className="mt-1 text-xs opacity-80">{step.note}</div>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
