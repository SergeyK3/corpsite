import type { PprMilitaryServiceRecordWrite } from "./pprCommandApi.client";
import {
  PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE,
  PPR_MILITARY_RECORD_KIND_REGISTRATION,
} from "./pprQueryTypes";

export type MilitaryServiceFormState = {
  record_kind: string;
  obligation_status: string;
  registration_category: string;
  military_rank: string;
  military_specialty_code: string;
  personnel_composition: string;
  fitness_category: string;
  registration_status: string;
  commissariat_name: string;
  registered_at: string;
  deregistered_at: string;
  military_id_book_series: string;
  military_id_book_number: string;
  registration_certificate_series: string;
  registration_certificate_number: string;
  notes: string;
};

export const ALLOWED_MILITARY_SERVICE_WRITE_KEYS = new Set([
  "record_kind",
  "employee_context_id",
  "obligation_status",
  "registration_category",
  "military_rank",
  "military_specialty_code",
  "personnel_composition",
  "fitness_category",
  "registration_status",
  "commissariat_name",
  "registered_at",
  "deregistered_at",
  "military_id_book_series",
  "military_id_book_number",
  "registration_certificate_series",
  "registration_certificate_number",
  "notes",
  "source_type",
  "provenance",
  "metadata",
]);

function trimOrNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

export function buildMilitaryServiceRecordPayload(
  form: MilitaryServiceFormState,
): PprMilitaryServiceRecordWrite {
  if (form.record_kind === PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE) {
    const payload: PprMilitaryServiceRecordWrite = {
      record_kind: form.record_kind,
    };
    const notes = trimOrNull(form.notes);
    if (notes) payload.notes = notes;
    return payload;
  }

  const payload: PprMilitaryServiceRecordWrite = {
    record_kind: form.record_kind,
  };

  const optionalFields: Array<keyof MilitaryServiceFormState> = [
    "obligation_status",
    "registration_category",
    "military_rank",
    "military_specialty_code",
    "personnel_composition",
    "fitness_category",
    "registration_status",
    "commissariat_name",
    "registered_at",
    "deregistered_at",
    "military_id_book_series",
    "military_id_book_number",
    "registration_certificate_series",
    "registration_certificate_number",
    "notes",
  ];

  for (const field of optionalFields) {
    const value = form[field];
    if (typeof value !== "string") continue;
    const normalized = field.endsWith("_at") ? value || null : trimOrNull(value);
    if (normalized) {
      (payload as Record<string, string | null>)[field] = normalized;
    }
  }

  return payload;
}

export function validateMilitaryServiceFormForSubmit(
  form: MilitaryServiceFormState,
): { ok: true } | { ok: false; message: string } {
  if (form.record_kind === PPR_MILITARY_RECORD_KIND_REGISTRATION) {
    const hasStructuredField = [
      form.obligation_status,
      form.registration_category,
      form.military_rank,
      form.registration_status,
    ].some((value) => Boolean(value.trim()));

    if (!hasStructuredField) {
      return {
        ok: false,
        message:
          "Укажите хотя бы одно из полей: воинская обязанность, категория учёта, звание или статус учёта.",
      };
    }
  }

  if (
    form.record_kind === PPR_MILITARY_RECORD_KIND_REGISTRATION &&
    form.registered_at &&
    form.deregistered_at &&
    form.deregistered_at < form.registered_at
  ) {
    return { ok: false, message: "Дата снятия с учёта не может быть раньше даты постановки." };
  }

  return { ok: true };
}

export function assertAllowedMilitaryServiceWritePayload(payload: PprMilitaryServiceRecordWrite): void {
  for (const key of Object.keys(payload)) {
    if (!ALLOWED_MILITARY_SERVICE_WRITE_KEYS.has(key)) {
      throw new Error(`Unexpected write field: ${key}`);
    }
  }
}

export function isStaleMutationError(error: unknown): boolean {
  const api = error as { status?: number };
  return api.status === 409;
}
