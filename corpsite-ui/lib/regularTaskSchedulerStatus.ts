// FILE: corpsite-ui/lib/regularTaskSchedulerStatus.ts

import { runStatusLabel } from "./i18n";
import {
  fmtDateTime,
  resolveRunKind,
  resolveRunMode,
  type RegularTaskRunRow,
} from "./regularTaskRunJournal";

/** Допустимое окно наблюдения для «Работает» (см. OPS-025.1). */
export const SCHEDULER_OBSERVATION_WINDOW_DAYS = 8;

export type SchedulerHealthStatus = "working" | "needs_attention" | "no_data";

export type SchedulerResultTone = "success" | "warning" | "error" | "neutral";

export type SchedulerStatusView = {
  status: SchedulerHealthStatus;
  status_label: string;
  last_run_at_label: string;
  last_successful_run_at_label: string;
  last_result_label: string;
  last_result_tone: SchedulerResultTone;
};

const STATUS_LABELS: Record<SchedulerHealthStatus, string> = {
  working: "Работает",
  needs_attention: "Требует внимания",
  no_data: "Нет данных",
};

export function isAutomaticLiveRun(run: RegularTaskRunRow): boolean {
  const stats = run.stats ?? {};
  const runKind = resolveRunKind(stats);
  if (runKind === "catch_up" || runKind === "preview") return false;
  if (stats.catch_up) return false;
  if (resolveRunMode(stats) === "dry") return false;
  return true;
}

export function isSuccessfulAutomaticRun(run: RegularTaskRunRow): boolean {
  const status = String(run.status ?? "").trim().toLowerCase();
  const errors = Number(run.stats?.errors ?? 0);
  return status === "ok" && errors === 0;
}

export function automaticRunHasIssues(run: RegularTaskRunRow): boolean {
  const status = String(run.status ?? "").trim().toLowerCase();
  const errors = Number(run.stats?.errors ?? 0);
  return status === "partial" || errors > 0;
}

export function resolveAutomaticRunResultLabel(run: RegularTaskRunRow): string {
  if (automaticRunHasIssues(run)) {
    const status = String(run.status ?? "").trim().toLowerCase();
    if (status === "partial") return runStatusLabel("partial");
    if (Number(run.stats?.errors ?? 0) > 0) return "С ошибками";
  }
  return runStatusLabel(run.status);
}

export function resolveAutomaticRunResultTone(run: RegularTaskRunRow): SchedulerResultTone {
  if (automaticRunHasIssues(run)) {
    const status = String(run.status ?? "").trim().toLowerCase();
    if (status === "partial") return "warning";
    return "error";
  }

  const status = String(run.status ?? "").trim().toLowerCase();
  if (status === "ok") return "success";
  return "neutral";
}

function compareRunsByStartedAtDesc(a: RegularTaskRunRow, b: RegularTaskRunRow): number {
  const aTime = Date.parse(a.started_at);
  const bTime = Date.parse(b.started_at);
  if (Number.isFinite(aTime) && Number.isFinite(bTime) && aTime !== bTime) {
    return bTime - aTime;
  }
  return b.run_id - a.run_id;
}

function isWithinObservationWindow(
  startedAt: string,
  now: Date,
  windowDays: number,
): boolean {
  const started = Date.parse(startedAt);
  if (!Number.isFinite(started)) return false;
  const windowMs = windowDays * 24 * 60 * 60 * 1000;
  return now.getTime() - started <= windowMs;
}

export function buildSchedulerStatusView(
  runs: readonly RegularTaskRunRow[],
  options?: {
    now?: Date;
    observationWindowDays?: number;
  },
): SchedulerStatusView {
  const now = options?.now ?? new Date();
  const observationWindowDays = options?.observationWindowDays ?? SCHEDULER_OBSERVATION_WINDOW_DAYS;

  const automaticLiveRuns = runs.filter(isAutomaticLiveRun).sort(compareRunsByStartedAtDesc);

  if (automaticLiveRuns.length === 0) {
    return {
      status: "no_data",
      status_label: STATUS_LABELS.no_data,
      last_run_at_label: "—",
      last_successful_run_at_label: "—",
      last_result_label: "—",
      last_result_tone: "neutral",
    };
  }

  const lastRun = automaticLiveRuns[0];
  const lastSuccessfulRun = automaticLiveRuns.find(isSuccessfulAutomaticRun) ?? null;

  let status: SchedulerHealthStatus;
  if (automaticRunHasIssues(lastRun)) {
    status = "needs_attention";
  } else if (
    lastSuccessfulRun &&
    isWithinObservationWindow(lastSuccessfulRun.started_at, now, observationWindowDays)
  ) {
    status = "working";
  } else {
    status = "needs_attention";
  }

  return {
    status,
    status_label: STATUS_LABELS[status],
    last_run_at_label: fmtDateTime(lastRun.started_at),
    last_successful_run_at_label: lastSuccessfulRun
      ? fmtDateTime(lastSuccessfulRun.started_at)
      : "—",
    last_result_label: resolveAutomaticRunResultLabel(lastRun),
    last_result_tone: resolveAutomaticRunResultTone(lastRun),
  };
}
