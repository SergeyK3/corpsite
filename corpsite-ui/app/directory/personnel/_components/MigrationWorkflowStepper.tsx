// PMF-4C / PMF-4D — workflow stepper shell (HR labels).
"use client";

import {
  MIGRATION_SESSION_WORKFLOW_STEPS,
  type MigrationSessionWorkflowStepId,
} from "../_lib/personnelMigrationHrLabels";

type MigrationWorkflowStepperProps = {
  activeStepId: MigrationSessionWorkflowStepId;
  disabledStepIds?: MigrationSessionWorkflowStepId[];
};

export default function MigrationWorkflowStepper({
  activeStepId,
  disabledStepIds = [],
}: MigrationWorkflowStepperProps) {
  const activeIndex = MIGRATION_SESSION_WORKFLOW_STEPS.findIndex((step) => step.id === activeStepId);
  const disabledSet = new Set(disabledStepIds);

  return (
    <section aria-label="Этапы переноса" className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <ol className="flex flex-wrap gap-2" data-testid="migration-workflow-steps">
        {MIGRATION_SESSION_WORKFLOW_STEPS.map((step, index) => {
          const isActive = step.id === activeStepId;
          const isDone = activeIndex > index;
          const isDisabled = disabledSet.has(step.id) && !isActive && !isDone;
          const isFuture = activeIndex < index && !isDisabled;

          return (
            <li
              key={step.id}
              className={[
                "rounded-full px-3 py-1 text-xs font-medium",
                isActive
                  ? "bg-blue-600 text-white"
                  : isDone
                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200"
                    : isDisabled
                      ? "bg-zinc-100 text-zinc-400 dark:bg-zinc-900 dark:text-zinc-500"
                      : "bg-zinc-200 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
              ].join(" ")}
              aria-current={isActive ? "step" : undefined}
              aria-disabled={isDisabled ? true : undefined}
            >
              {index + 1}. {step.title}
              {isFuture ? (
                <span className="ml-1 font-normal opacity-80">(далее)</span>
              ) : isDisabled ? (
                <span className="ml-1 font-normal opacity-80">(позже)</span>
              ) : null}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
