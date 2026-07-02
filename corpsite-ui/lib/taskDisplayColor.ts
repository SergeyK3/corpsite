// FILE: corpsite-ui/lib/taskDisplayColor.ts

export type TaskDisplayColor = "default" | "green" | "orange" | "red";

export type TaskDisplayColorSource = {
  due_date?: string | null;
  due_at?: string | null;
  deadline?: string | null;
  deadline_at?: string | null;
  deadline_date?: string | null;
  due?: string | null;
  report_approved_at?: string | null;
  status_code?: string | null;
};

const MS_PER_DAY = 24 * 60 * 60 * 1000;

export function resolveTaskDueDateRaw(source: TaskDisplayColorSource): string | null {
  const raw =
    source.due_at ??
    source.due_date ??
    source.deadline ??
    source.deadline_at ??
    source.deadline_date ??
    source.due ??
    null;

  const value = String(raw ?? "").trim();
  return value || null;
}

function parseCalendarDate(raw: string | null | undefined): Date | null {
  const value = String(raw ?? "").trim();
  if (!value) return null;

  const dateOnly = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (dateOnly) {
    const year = Number(dateOnly[1]);
    const month = Number(dateOnly[2]);
    const day = Number(dateOnly[3]);
    const parsed = new Date(year, month - 1, day);
    if (
      parsed.getFullYear() === year &&
      parsed.getMonth() === month - 1 &&
      parsed.getDate() === day
    ) {
      return parsed;
    }
  }

  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime())) return null;
  return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate());
}

function calendarDaysAfter(from: Date, to: Date): number {
  return Math.floor((to.getTime() - from.getTime()) / MS_PER_DAY);
}

function isTaskAcceptedByManager(source: TaskDisplayColorSource): boolean {
  return Boolean(String(source.report_approved_at ?? "").trim());
}

function isTaskStillOpen(source: TaskDisplayColorSource): boolean {
  const code = String(source.status_code ?? "").trim().toUpperCase();
  return code !== "DONE" && code !== "ARCHIVED";
}

export function getTaskDisplayColor(
  source: TaskDisplayColorSource,
  today: Date = new Date(),
): TaskDisplayColor {
  const deadlineRaw = resolveTaskDueDateRaw(source);
  const deadlineDay = parseCalendarDate(deadlineRaw);
  if (!deadlineDay) return "default";

  const todayDay = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const daysAfterDeadline = calendarDaysAfter(deadlineDay, todayDay);

  if (daysAfterDeadline <= 0) return "default";

  if (isTaskAcceptedByManager(source)) {
    const acceptedDay = parseCalendarDate(source.report_approved_at);
    const completedOnTime = acceptedDay != null && acceptedDay.getTime() <= deadlineDay.getTime();
    if (completedOnTime && daysAfterDeadline <= 7) {
      return "green";
    }
    return "default";
  }

  if (!isTaskStillOpen(source)) return "default";

  if (daysAfterDeadline > 7) return "red";
  return "orange";
}

export function taskDisplayColorTitleClass(color: TaskDisplayColor): string {
  switch (color) {
    case "green":
      return "text-emerald-800 dark:text-emerald-200";
    case "orange":
      return "text-amber-800 dark:text-amber-200";
    case "red":
      return "text-red-700 dark:text-red-300";
    default:
      return "text-zinc-900 dark:text-zinc-50";
  }
}

export function taskDisplayColorDeadlineClass(color: TaskDisplayColor): string {
  switch (color) {
    case "green":
      return "text-emerald-800 dark:text-emerald-200";
    case "orange":
      return "text-amber-800 dark:text-amber-200";
    case "red":
      return "text-red-700 dark:text-red-300";
    default:
      return "text-zinc-600 dark:text-zinc-400";
  }
}
