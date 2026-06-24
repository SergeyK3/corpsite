export type ScheduleType = "weekly" | "monthly" | "yearly";

export const DEFAULT_SCHEDULE_PARAMS: Readonly<Record<ScheduleType, Record<string, unknown>>> = {
  weekly: { byweekday: [1], time: "10:00" },
  monthly: { bymonthday: [1], time: "10:00" },
  yearly: { bymonth: [1], bymonthday: [1], time: "10:00" },
};

const HHMM_RE = /^([01]\d|2[0-3]):[0-5]\d$/;

export function normalizeScheduleType(value: string | null | undefined): ScheduleType | null {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (normalized === "weekly" || normalized === "monthly" || normalized === "yearly") {
    return normalized;
  }
  return null;
}

export function defaultScheduleParamsJson(scheduleType: string): string {
  const normalized = normalizeScheduleType(scheduleType);
  if (!normalized) return "{}";
  return JSON.stringify(DEFAULT_SCHEDULE_PARAMS[normalized], null, 2);
}

export function parseScheduleParamsText(text: string): {
  value: Record<string, unknown> | null;
  error: string | null;
} {
  const trimmed = String(text ?? "").trim();
  if (!trimmed) return { value: {}, error: null };

  try {
    const parsed = JSON.parse(trimmed);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { value: null, error: "Параметры расписания должны быть JSON-объектом." };
    }
    return { value: parsed as Record<string, unknown>, error: null };
  } catch {
    return { value: null, error: "Параметры расписания содержат некорректный JSON." };
  }
}

function isEmptyScheduleParams(params: Record<string, unknown>): boolean {
  return Object.keys(params).length === 0;
}

function scheduleParamsEqual(a: Record<string, unknown>, b: Record<string, unknown>): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

function asIntList(value: unknown): number[] {
  if (value == null) return [];
  if (Array.isArray(value)) {
    return value
      .map((item) => Number(item))
      .filter((item) => Number.isFinite(item))
      .map((item) => Math.trunc(item));
  }
  const single = Number(value);
  return Number.isFinite(single) ? [Math.trunc(single)] : [];
}

function hasWeekdayValue(value: unknown): boolean {
  if (value == null) return false;
  if (Array.isArray(value)) return value.length > 0;
  return String(value).trim().length > 0;
}

/**
 * When schedule_type changes, replace schedule_params only if the current JSON is empty
 * or still matches the default template for the previous schedule type.
 * Custom edits are preserved so the user is not surprised by silent data loss.
 */
export function resolveScheduleParamsOnTypeChange(
  previousType: string,
  newType: string,
  currentParamsText: string,
): string {
  const nextType = normalizeScheduleType(newType);
  if (!nextType) return currentParamsText;

  const parsed = parseScheduleParamsText(currentParamsText);
  if (parsed.error || parsed.value == null) return currentParamsText;

  const currentParams = parsed.value;
  const previousNormalized = normalizeScheduleType(previousType);
  const shouldReplace =
    isEmptyScheduleParams(currentParams) ||
    (previousNormalized != null &&
      scheduleParamsEqual(currentParams, DEFAULT_SCHEDULE_PARAMS[previousNormalized]));

  if (shouldReplace) {
    return defaultScheduleParamsJson(nextType);
  }

  return currentParamsText;
}

export function validateScheduleParams(
  scheduleType: string,
  scheduleParams: Record<string, unknown> | null | undefined,
): string | null {
  const normalizedType = normalizeScheduleType(scheduleType);
  if (!normalizedType) return null;

  const params = scheduleParams ?? {};

  if (normalizedType === "weekly") {
    if (!hasWeekdayValue(params.byweekday)) {
      return "Для еженедельного расписания обязателен параметр byweekday.";
    }
  }

  if (normalizedType === "monthly") {
    if (asIntList(params.bymonthday).length === 0) {
      return "Для ежемесячного расписания обязателен параметр bymonthday.";
    }
  }

  if (normalizedType === "yearly") {
    if (asIntList(params.bymonth).length === 0) {
      return "Для ежегодного расписания обязателен параметр bymonth.";
    }
    if (asIntList(params.bymonthday).length === 0) {
      return "Для ежегодного расписания обязателен параметр bymonthday.";
    }
  }

  if (params.time != null && String(params.time).trim() !== "") {
    if (!HHMM_RE.test(String(params.time).trim())) {
      return "Параметр time должен быть в формате HH:MM (например, 10:00).";
    }
  }

  return null;
}
