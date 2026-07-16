import type { PprExternalEmploymentRecordWrite } from "./pprCommandApi.client";
import {
  PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE,
  PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE,
  PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY,
} from "./pprQueryTypes";

export type EmploymentBiographyFormState = {
  record_kind: string;
  employer_name: string;
  department_name: string;
  position_title: string;
  started_at: string;
  ended_at: string;
  notes: string;
};

export const ALLOWED_EXTERNAL_EMPLOYMENT_WRITE_KEYS = new Set([
  "record_kind",
  "employee_context_id",
  "employer_name",
  "department_name",
  "position_title",
  "employment_type",
  "started_at",
  "ended_at",
  "termination_reason",
  "document_reference",
  "source_system",
  "source_id",
  "provenance",
  "notes",
  "metadata",
]);

export function buildExternalEmploymentRecordPayload(
  form: EmploymentBiographyFormState,
): PprExternalEmploymentRecordWrite {
  if (form.record_kind === PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE) {
    return {
      record_kind: form.record_kind,
      employer_name: form.employer_name.trim() || null,
      department_name: form.department_name.trim() || null,
      position_title: form.position_title.trim() || null,
      started_at: form.started_at || null,
      ended_at: form.ended_at || null,
    };
  }

  if (form.record_kind === PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE) {
    const payload: PprExternalEmploymentRecordWrite = {
      record_kind: form.record_kind,
    };
    const notes = form.notes.trim();
    if (notes) payload.notes = notes;
    return payload;
  }

  return {
    record_kind: form.record_kind,
    notes: form.notes.trim(),
  };
}

export function validateExternalEmploymentFormForSubmit(
  form: EmploymentBiographyFormState,
): { ok: true } | { ok: false; message: string } {
  if (form.record_kind === PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY) {
    if (!form.notes.trim()) {
      return { ok: false, message: "Укажите текст сводной записи о стаже." };
    }
  }
  return { ok: true };
}

export function assertAllowedExternalEmploymentWritePayload(
  payload: PprExternalEmploymentRecordWrite,
): void {
  for (const key of Object.keys(payload)) {
    if (!ALLOWED_EXTERNAL_EMPLOYMENT_WRITE_KEYS.has(key)) {
      throw new Error(`Unexpected write field: ${key}`);
    }
  }
}

export function isStaleMutationError(error: unknown): boolean {
  const api = error as { status?: number };
  return api.status === 409;
}
