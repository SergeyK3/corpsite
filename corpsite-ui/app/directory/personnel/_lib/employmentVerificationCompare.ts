/** Field-level comparison helpers for employment revision review (WP-VER-005B). */

import { formatPersonnelDateRange } from "@/lib/personnelDateFormat";

import type { EmploymentRecordSnapshot } from "./personnelVerificationApi.client";

export type EmploymentCompareFieldKey =
  | "employer_name"
  | "department_name"
  | "position_title"
  | "employment_type"
  | "period"
  | "termination_reason"
  | "document_reference"
  | "notes";

export type EmploymentCompareRow = {
  key: EmploymentCompareFieldKey;
  label: string;
  priorValue: string;
  revisionValue: string;
  changed: boolean;
};

const EMPTY = "—";

function displayText(value: string | null | undefined): string {
  const trimmed = (value ?? "").trim();
  return trimmed || EMPTY;
}

function periodLabel(record: EmploymentRecordSnapshot): string {
  const range = formatPersonnelDateRange(record.started_at, record.ended_at, {
    empty: "",
  });
  return range.trim() || EMPTY;
}

export function summarizeEmploymentRecord(record: EmploymentRecordSnapshot): string {
  const employer = displayText(record.employer_name);
  const position = displayText(record.position_title);
  if (employer === EMPTY && position === EMPTY) {
    return "Запись без работодателя и должности";
  }
  if (position === EMPTY) return employer;
  if (employer === EMPTY) return position;
  return `${employer} — ${position}`;
}

export function buildEmploymentCompareRows(
  prior: EmploymentRecordSnapshot,
  revision: EmploymentRecordSnapshot,
): EmploymentCompareRow[] {
  const rows: Array<{
    key: EmploymentCompareFieldKey;
    label: string;
    priorValue: string;
    revisionValue: string;
  }> = [
    {
      key: "employer_name",
      label: "Работодатель",
      priorValue: displayText(prior.employer_name),
      revisionValue: displayText(revision.employer_name),
    },
    {
      key: "department_name",
      label: "Подразделение",
      priorValue: displayText(prior.department_name),
      revisionValue: displayText(revision.department_name),
    },
    {
      key: "position_title",
      label: "Должность",
      priorValue: displayText(prior.position_title),
      revisionValue: displayText(revision.position_title),
    },
    {
      key: "employment_type",
      label: "Тип занятости",
      priorValue: displayText(prior.employment_type),
      revisionValue: displayText(revision.employment_type),
    },
    {
      key: "period",
      label: "Период",
      priorValue: periodLabel(prior),
      revisionValue: periodLabel(revision),
    },
    {
      key: "termination_reason",
      label: "Основание увольнения",
      priorValue: displayText(prior.termination_reason),
      revisionValue: displayText(revision.termination_reason),
    },
    {
      key: "document_reference",
      label: "Документ",
      priorValue: displayText(prior.document_reference),
      revisionValue: displayText(revision.document_reference),
    },
    {
      key: "notes",
      label: "Примечание",
      priorValue: displayText(prior.notes),
      revisionValue: displayText(revision.notes),
    },
  ];

  return rows.map((row) => ({
    ...row,
    changed: row.priorValue !== row.revisionValue,
  }));
}

export function formatTaskCreatedAt(iso: string | null | undefined): string {
  if (!iso) return EMPTY;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
