import {
  formatPersonnelDayDateForDisplay,
  isValidPersonnelDayDateIso,
} from "@/lib/personnelDayDate";
import {
  normalizeIntakeTrainingEntry,
  reconcileTrainingEntryHours,
  resolveIntakeTrainingYearTo,
  type IntakeTrainingEntry,
} from "@/app/intake/_lib/intakeTraining";

export const TRAINING_WINDOW_YEARS = 5;
export const CERTIFICATE_VALIDITY_YEARS = 5;
export const CERTIFICATE_EXPIRY_LOOKAHEAD_MONTHS = 6;
export const TRAINING_DOCUMENT_TYPE_CERTIFICATE = "certificate";

export type TrainingSummaryRecord = {
  title: string | null;
  completedAt: string | null;
  hours: number | null;
  documentType: string | null;
  lifecycleStatus: string | null;
};

export type ExpiringCertificateSummary = {
  title: string;
  expiresAt: string;
  daysRemaining: number;
};

export type TrainingHoursLast5ySummary = {
  asOf: string;
  windowStart: string;
  trainingHoursLast5y: number;
  qualifyingRecordsCount: number;
};

function parseIsoDateOnly(value: string | null | undefined): string | null {
  const trimmed = String(value ?? "").trim();
  if (!trimmed || !isValidPersonnelDayDateIso(trimmed)) return null;
  return trimmed.slice(0, 10);
}

function toUtcDate(isoDate: string): Date {
  const [year, month, day] = isoDate.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

function isoFromUtcDate(date: Date): string {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function trainingWindowStart(asOfIso: string): string {
  const asOf = toUtcDate(asOfIso);
  const targetYear = asOf.getUTCFullYear() - TRAINING_WINDOW_YEARS;
  const month = asOf.getUTCMonth();
  const day = asOf.getUTCDate();
  const lastDay = new Date(Date.UTC(targetYear, month + 1, 0)).getUTCDate();
  return isoFromUtcDate(new Date(Date.UTC(targetYear, month, Math.min(day, lastDay))));
}

export function addCalendarYears(isoDate: string, years: number): string {
  const date = toUtcDate(isoDate);
  const targetYear = date.getUTCFullYear() + years;
  const month = date.getUTCMonth();
  const day = date.getUTCDate();
  const lastDay = new Date(Date.UTC(targetYear, month + 1, 0)).getUTCDate();
  return isoFromUtcDate(new Date(Date.UTC(targetYear, month, Math.min(day, lastDay))));
}

export function addCalendarMonths(isoDate: string, months: number): string {
  const date = toUtcDate(isoDate);
  const absoluteMonth = date.getUTCMonth() + months;
  const year = date.getUTCFullYear() + Math.floor(absoluteMonth / 12);
  const month = ((absoluteMonth % 12) + 12) % 12;
  const lastDay = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const day = Math.min(date.getUTCDate(), lastDay);
  return isoFromUtcDate(new Date(Date.UTC(year, month, day)));
}

export function parseTrainingHours(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const text = String(value).trim().replace(",", ".");
  if (!text) return null;
  const parsed = Number(text);
  if (!Number.isFinite(parsed) || parsed < 0) return null;
  return parsed;
}

function normalizeDocumentType(value: string | null | undefined): string | null {
  const text = String(value ?? "").trim().toLowerCase();
  return text || null;
}

export function isActiveTrainingRecord(record: TrainingSummaryRecord): boolean {
  const status = String(record.lifecycleStatus ?? "active").trim().toLowerCase();
  return status === "active";
}

export function isCertificateRecord(record: TrainingSummaryRecord): boolean {
  return normalizeDocumentType(record.documentType) === TRAINING_DOCUMENT_TYPE_CERTIFICATE;
}

export function trainingSummaryRecordFromIntakeEntry(item: IntakeTrainingEntry): TrainingSummaryRecord {
  const normalized = reconcileTrainingEntryHours(normalizeIntakeTrainingEntry(item));
  return {
    title: normalized.course_name.trim() || null,
    completedAt: parseIsoDateOnly(resolveIntakeTrainingYearTo(normalized)),
    hours: parseTrainingHours(normalized.hours),
    documentType: normalizeDocumentType(normalized.document_type),
    lifecycleStatus: "ACTIVE",
  };
}

export type PprTrainingSummarySource = {
  title: string | null;
  completed_at: string | null;
  hours: string | number | null;
  document_type?: string | null;
  lifecycle_status?: string | null;
};

export function trainingSummaryRecordFromPprRecord(record: PprTrainingSummarySource): TrainingSummaryRecord {
  return {
    title: String(record.title ?? "").trim() || null,
    completedAt: parseIsoDateOnly(record.completed_at),
    hours: parseTrainingHours(record.hours),
    documentType: normalizeDocumentType(record.document_type),
    lifecycleStatus: String(record.lifecycle_status ?? "ACTIVE").trim() || "ACTIVE",
  };
}

export function calculateTrainingHoursLast5y(
  records: readonly TrainingSummaryRecord[],
  asOfIso?: string,
): TrainingHoursLast5ySummary {
  const asOf = parseIsoDateOnly(asOfIso ?? isoFromUtcDate(new Date()))!;
  const windowStart = trainingWindowStart(asOf);
  let total = 0;
  let qualifyingRecordsCount = 0;

  for (const record of records) {
    if (!isActiveTrainingRecord(record)) continue;
    const completedAt = parseIsoDateOnly(record.completedAt);
    if (!completedAt || completedAt < windowStart || completedAt > asOf) continue;
    if (record.hours === null) continue;
    total += record.hours;
    qualifyingRecordsCount += 1;
  }

  return {
    asOf,
    windowStart,
    trainingHoursLast5y: total,
    qualifyingRecordsCount,
  };
}

export function calculateExpiringCertificates(
  records: readonly TrainingSummaryRecord[],
  asOfIso?: string,
): ExpiringCertificateSummary[] {
  const asOf = parseIsoDateOnly(asOfIso ?? isoFromUtcDate(new Date()))!;
  const lookaheadEnd = addCalendarMonths(asOf, CERTIFICATE_EXPIRY_LOOKAHEAD_MONTHS);
  const results: ExpiringCertificateSummary[] = [];

  for (const record of records) {
    if (!isActiveTrainingRecord(record)) continue;
    if (!isCertificateRecord(record)) continue;
    const title = String(record.title ?? "").trim();
    const completedAt = parseIsoDateOnly(record.completedAt);
    if (!title || !completedAt) continue;

    const expiresAt = addCalendarYears(completedAt, CERTIFICATE_VALIDITY_YEARS);
    if (expiresAt <= asOf || expiresAt > lookaheadEnd) continue;

    const daysRemaining = Math.floor((toUtcDate(expiresAt).getTime() - toUtcDate(asOf).getTime()) / 86_400_000);
    if (daysRemaining <= 0) continue;

    results.push({ title, expiresAt, daysRemaining });
  }

  return results.sort((left, right) => {
    const byDate = left.expiresAt.localeCompare(right.expiresAt);
    return byDate !== 0 ? byDate : left.title.localeCompare(right.title, "ru");
  });
}

export function formatTrainingSummaryDate(isoDate: string): string {
  return formatPersonnelDayDateForDisplay(isoDate.slice(0, 10), "document") || isoDate;
}
