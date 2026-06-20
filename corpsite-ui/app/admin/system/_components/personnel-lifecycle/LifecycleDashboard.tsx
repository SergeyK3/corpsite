// FILE: corpsite-ui/app/admin/system/_components/personnel-lifecycle/LifecycleDashboard.tsx
"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchLifecycleRuns,
  mapPersonnelLifecycleApiError,
  type LifecycleRunSummary,
} from "../../_lib/personnelLifecycleApi.client";
import {
  formatDurationBetween,
  lifecycleStatusClass,
} from "../../_lib/personnelLifecycleLabels";
import { formatActorLabel, formatDateTime } from "../../_lib/adminSystemLabels";
import ErrorBanner from "../shared/ErrorBanner";

type LifecycleDashboardProps = {
  refreshToken?: number;
};

export default function LifecycleDashboard({ refreshToken = 0 }: LifecycleDashboardProps) {
  const [latest, setLatest] = useState<LifecycleRunSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchLifecycleRuns({ limit: 1, offset: 0, sort_by: "started_at", sort_dir: "desc" });
      setLatest(res.items[0] ?? null);
    } catch (err) {
      setError(mapPersonnelLifecycleApiError(err, "Не удалось загрузить последний lifecycle run"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load, refreshToken]);

  return (
    <section className="space-y-3" data-testid="lifecycle-dashboard">
      <h2 className="text-lg font-semibold">Personnel Lifecycle</h2>
      <ErrorBanner message={error} />

      {loading ? (
        <p className="text-sm text-zinc-500" data-testid="lifecycle-dashboard-loading">
          Загрузка…
        </p>
      ) : !latest ? (
        <p className="text-sm text-zinc-500" data-testid="lifecycle-dashboard-empty">
          Lifecycle runs ещё не выполнялись.
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard label="Run ID" value={`#${latest.run_id}`} />
          <MetricCard
            label="Status"
            value={
              <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${lifecycleStatusClass(latest.status)}`}>
                {latest.status}
              </span>
            }
          />
          <MetricCard label="Started" value={formatDateTime(latest.started_at)} />
          <MetricCard label="Completed" value={formatDateTime(latest.completed_at)} />
          <MetricCard label="Duration" value={formatDurationBetween(latest.started_at, latest.completed_at)} />
          <MetricCard label="Events created" value={String(latest.events_created)} />
          <MetricCard label="Persons created" value={String(latest.persons_created)} />
          <MetricCard label="Assignments created" value={String(latest.assignments_created)} />
          <MetricCard label="Warnings" value={String(latest.warnings_count)} />
          <MetricCard label="Errors" value={String(latest.errors_count)} />
          <MetricCard
            label="Snapshots"
            value={`${latest.previous_snapshot_id} → ${latest.snapshot_id}`}
          />
          <MetricCard
            label="Actor"
            value={formatActorLabel(latest.actor_user_id)}
          />
        </div>
      )}
    </section>
  );
}

function MetricCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  );
}
