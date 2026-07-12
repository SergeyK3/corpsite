"use client";

import type { WorkspaceTimelineStep } from "../_lib/workspaceTimeline";

type Props = { steps: WorkspaceTimelineStep[] };

const STATE_CLASS: Record<string, string> = {
  completed: "border-emerald-300 bg-emerald-50 text-emerald-900",
  current: "border-blue-400 bg-blue-50 text-blue-900 ring-2 ring-blue-200",
  blocked: "border-amber-400 bg-amber-50 text-amber-900 ring-2 ring-amber-200",
  future: "border-zinc-200 bg-zinc-50 text-zinc-400 dark:border-zinc-700 dark:bg-zinc-900",
};

export default function WorkspaceProgressTimeline({ steps }: Props) {
  return (
    <section className="rounded-xl border p-4 dark:border-zinc-800" data-testid="workspace-progress-timeline">
      <h3 className="mb-3 text-sm font-semibold">Ход обработки</h3>
      <ol className="flex flex-wrap gap-2">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className={`rounded-lg border px-3 py-2 text-xs font-medium ${STATE_CLASS[step.state]}`}
            data-testid={`workspace-timeline-step-${step.id}`}
            data-state={step.state}
          >
            <span className="mr-1 text-[10px] opacity-60">{index + 1}.</span>
            {step.label}
          </li>
        ))}
      </ol>
    </section>
  );
}
