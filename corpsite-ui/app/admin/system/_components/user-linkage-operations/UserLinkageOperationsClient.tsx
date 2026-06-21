// FILE: corpsite-ui/app/admin/system/_components/user-linkage-operations/UserLinkageOperationsClient.tsx
"use client";

import Link from "next/link";
import { useCallback, useState } from "react";

import OperationsDashboard from "./OperationsDashboard";
import OperationsItemDetailDrawer from "./OperationsItemDetailDrawer";
import OperationsItemsTable from "./OperationsItemsTable";
import OperationsRunDetailDrawer from "./OperationsRunDetailDrawer";
import OperationsRunsTable from "./OperationsRunsTable";
import RepairPreviewPanel from "./RepairPreviewPanel";
import RerunExecutePanel from "./RerunExecutePanel";

type MainTab = "overview" | "runs" | "items" | "repair" | "rerun";

const TABS: { id: MainTab; label: string }[] = [
  { id: "overview", label: "Dashboard" },
  { id: "runs", label: "History Runs" },
  { id: "items", label: "Item History" },
  { id: "repair", label: "Repair Preview" },
  { id: "rerun", label: "Re-run Execute" },
];

function tabButtonClass(active: boolean): string {
  return [
    "rounded-lg px-3 py-1.5 text-sm font-medium transition",
    active
      ? "bg-blue-600 text-white"
      : "bg-zinc-100 text-zinc-800 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
  ].join(" ");
}

export default function UserLinkageOperationsClient() {
  const [activeTab, setActiveTab] = useState<MainTab>("overview");
  const [refreshToken, setRefreshToken] = useState(0);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null);

  const bumpRefresh = useCallback(() => {
    setRefreshToken((v) => v + 1);
  }, []);

  const openRun = useCallback((runId: number) => {
    setSelectedRunId(runId);
    setSelectedItemId(null);
  }, []);

  const openItem = useCallback((itemId: number) => {
    setSelectedItemId(itemId);
    setSelectedRunId(null);
  }, []);

  const closeRunDrawer = useCallback(() => setSelectedRunId(null), []);
  const closeItemDrawer = useCallback(() => setSelectedItemId(null), []);

  return (
    <div className="space-y-4" data-testid="user-linkage-operations-client">
      <header>
        <div className="flex flex-wrap items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
          <Link href="/admin/system" className="hover:underline">
            Admin
          </Link>
          <span>/</span>
          <Link href="/directory/personnel" className="hover:underline">
            Personnel
          </Link>
          <span>/</span>
          <span>Identity</span>
          <span>/</span>
          <span className="text-zinc-900 dark:text-zinc-100">Operations</span>
        </div>
        <h1 className="mt-2 text-2xl font-semibold">User Linkage Operations</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Observability and safe operations for personnel identity linkage (ADR-044 R2.5g).
        </p>
      </header>

      <nav className="flex flex-wrap gap-2" aria-label="Разделы user linkage operations">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={tabButtonClass(activeTab === tab.id)}
            data-testid={`user-linkage-operations-tab-${tab.id}`}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="space-y-6 rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-950">
        {activeTab === "overview" ? (
          <OperationsDashboard
            refreshToken={refreshToken}
            onOpenRun={openRun}
            onOpenItem={openItem}
          />
        ) : null}
        {activeTab === "runs" ? (
          <OperationsRunsTable refreshToken={refreshToken} onOpenRun={openRun} />
        ) : null}
        {activeTab === "items" ? (
          <OperationsItemsTable refreshToken={refreshToken} onOpenItem={openItem} />
        ) : null}
        {activeTab === "repair" ? <RepairPreviewPanel /> : null}
        {activeTab === "rerun" ? <RerunExecutePanel onComplete={bumpRefresh} /> : null}
      </div>

      <OperationsRunDetailDrawer
        runId={selectedRunId}
        onClose={closeRunDrawer}
        onOpenItem={(itemId) => {
          openItem(itemId);
        }}
      />

      <OperationsItemDetailDrawer
        itemId={selectedItemId}
        onClose={closeItemDrawer}
        onOpenRun={(runId) => {
          openRun(runId);
        }}
      />
    </div>
  );
}
