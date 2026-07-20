"use client";

import * as React from "react";

import ImportMonthlyDiffRemovedSection from "./ImportMonthlyDiffRemovedSection";
import ImportRemovalDecisionHistorySection from "./ImportRemovalDecisionHistorySection";
import type { MonthlyDiffRemoval } from "../_lib/importApi.client";
import type { RemovedEntryDecisionKind } from "../_lib/importRemovedEntryDecisions";

export type RemovalDecisionTab = "pending" | "restored" | "confirmed";

type Props = {
  pending: MonthlyDiffRemoval[];
  restored: MonthlyDiffRemoval[];
  confirmed: MonthlyDiffRemoval[];
  decisionsEnabled?: boolean;
  onDecision?: (item: MonthlyDiffRemoval, kind: RemovedEntryDecisionKind) => void | Promise<void>;
  onRevert?: (item: MonthlyDiffRemoval) => void | Promise<void>;
  onOpen?: (removalId: number) => void;
};

const TAB_LABELS: Record<RemovalDecisionTab, string> = {
  pending: "Ожидают решения",
  restored: "Восстановленные записи",
  confirmed: "Подтверждённые удаления",
};

export default function ImportRemovalDecisionsPanel({
  pending,
  restored,
  confirmed,
  decisionsEnabled = false,
  onDecision,
  onRevert,
  onOpen,
}: Props) {
  const [tab, setTab] = React.useState<RemovalDecisionTab>("pending");
  const counts: Record<RemovalDecisionTab, number> = {
    pending: pending.length,
    restored: restored.length,
    confirmed: confirmed.length,
  };

  if (!pending.length && !restored.length && !confirmed.length) {
    return null;
  }

  return (
    <section className="space-y-3" data-testid="import-removal-decisions-panel">
      <div className="flex flex-wrap gap-2">
        {(Object.keys(TAB_LABELS) as RemovalDecisionTab[]).map((key) => (
          <button
            key={key}
            type="button"
            data-testid={`removal-decisions-tab-${key}`}
            onClick={() => setTab(key)}
            className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition ${
              tab === key
                ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
                : "border-zinc-300 text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
            }`}
          >
            {TAB_LABELS[key]} ({counts[key].toLocaleString("ru-RU")})
          </button>
        ))}
      </div>

      {tab === "pending" ? (
        <ImportMonthlyDiffRemovedSection
          items={pending}
          decisionsEnabled={decisionsEnabled}
          onDecision={onDecision}
          onOpen={onOpen}
        />
      ) : null}

      {tab === "restored" ? (
        <ImportRemovalDecisionHistorySection
          variant="restored"
          items={restored}
          decisionsEnabled={decisionsEnabled}
          onRevert={onRevert}
        />
      ) : null}

      {tab === "confirmed" ? (
        <ImportRemovalDecisionHistorySection
          variant="confirmed"
          items={confirmed}
          decisionsEnabled={decisionsEnabled}
          onRevert={onRevert}
        />
      ) : null}
    </section>
  );
}
