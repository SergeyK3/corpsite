// FILE: corpsite-ui/app/admin/system/_components/personnel-lifecycle/PersonnelLifecycleClient.tsx
"use client";

import Link from "next/link";
import { useState } from "react";

import type { MeInfo } from "@/lib/types";

import EffectivePersonViewer from "./EffectivePersonViewer";
import LifecycleDashboard from "./LifecycleDashboard";
import LifecycleRunPanel from "./LifecycleRunPanel";
import LifecycleRunsTable from "./LifecycleRunsTable";
import OverridesPanel from "./OverridesPanel";
import PersonnelEventsPanel from "./PersonnelEventsPanel";
import ValidationPanel from "./ValidationPanel";

type MainTab = "overview" | "runs" | "events" | "overrides";

const TABS: { id: MainTab; label: string }[] = [
  { id: "overview", label: "Обзор" },
  { id: "runs", label: "Запуски цикла" },
  { id: "events", label: "События персонала" },
  { id: "overrides", label: "Исключения" },
];

function tabButtonClass(active: boolean): string {
  return [
    "rounded-lg px-3 py-1.5 text-sm font-medium transition",
    active
      ? "bg-blue-600 text-white"
      : "bg-zinc-100 text-zinc-800 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
  ].join(" ");
}

type PersonnelLifecycleClientProps = {
  me: MeInfo | null;
};

export default function PersonnelLifecycleClient({ me }: PersonnelLifecycleClientProps) {
  const [activeTab, setActiveTab] = useState<MainTab>("overview");
  const [refreshToken, setRefreshToken] = useState(0);

  const hasHrGovernance = me?.has_hr_governance === true || me?.is_privileged === true;

  function bumpRefresh(): void {
    setRefreshToken((v) => v + 1);
  }

  return (
    <div className="space-y-4" data-testid="personnel-lifecycle-client">
      <header>
        <div className="flex flex-wrap items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
          <Link href="/admin/system" className="hover:underline">
            Кабинет системного администратора
          </Link>
          <span>/</span>
          <span className="text-zinc-900 dark:text-zinc-100">Жизненный цикл персонала</span>
        </div>
        <h1 className="mt-2 text-2xl font-semibold">Жизненный цикл персонала</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Запуски HR-цикла, события персонала, исключения и effective canonical (ADR-043 Phase C4.2).
        </p>
      </header>

      <nav className="flex flex-wrap gap-2" aria-label="Разделы жизненного цикла персонала">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={tabButtonClass(activeTab === tab.id)}
            data-testid={`personnel-lifecycle-tab-${tab.id}`}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="space-y-6 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-950">
        {activeTab === "overview" ? (
          <>
            <LifecycleDashboard refreshToken={refreshToken} />
            <hr className="border-zinc-200 dark:border-zinc-700" />
            <LifecycleRunPanel onRunComplete={bumpRefresh} />
            <hr className="border-zinc-200 dark:border-zinc-700" />
            <ValidationPanel />
            <hr className="border-zinc-200 dark:border-zinc-700" />
            <EffectivePersonViewer />
          </>
        ) : null}
        {activeTab === "runs" ? <LifecycleRunsTable refreshToken={refreshToken} /> : null}
        {activeTab === "events" ? <PersonnelEventsPanel /> : null}
        {activeTab === "overrides" ? <OverridesPanel hasHrGovernance={hasHrGovernance} /> : null}
      </div>
    </div>
  );
}
