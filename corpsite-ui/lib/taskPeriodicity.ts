import { scheduleTypeLabel } from "@/lib/i18n";

export type TaskPeriodicitySource = {
  task_kind?: string | null;
  schedule_type?: string | null;
};

function normalizeTaskKind(value: unknown): string {
  const s = String(value ?? "").trim().toLowerCase();
  if (s === "adhoc" || s === "regular") return s;
  return s ? "other" : "";
}

/** Human-readable periodicity for task list/detail; uses schedule_type, not title text. */
export function taskPeriodicityLabel(task: TaskPeriodicitySource | null | undefined): string {
  const kind = normalizeTaskKind(task?.task_kind);
  if (kind === "adhoc") return "Разовая";

  const scheduleType = String(task?.schedule_type ?? "").trim();
  if (scheduleType) {
    return scheduleTypeLabel(scheduleType) || scheduleType;
  }

  return "—";
}
