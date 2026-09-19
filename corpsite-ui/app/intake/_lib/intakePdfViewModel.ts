import { reconcileIntakeDraftPayload } from "./intakeDraftReconcile";
import {
  emptyIntakeDraftPayload,
  toIntakeFormPayload,
  type IntakeDraftPayload,
} from "./intakeApi.client";
import { formatIntakeFullName } from "./intakeContactHelpers";
import {
  buildIntakePdfGeneratedDateLabel,
  formatIntakePdfAsOfIso,
} from "./intakePdfDate";
import type { IntakePdfCalculatedSummaries } from "./intakePdfSummaries";
import {
  deriveIntakeSurnameAlphabet,
  normalizeIntakePersonnelNumber,
} from "./intakePersonalFields";

export type IntakePdfViewModel = {
  applicationId: number;
  fullName: string;
  generatedDateLabel: string;
  asOfIso: string;
  organizationShortName: string;
  personnelNumber: string;
  alphabet: string;
  birthPlace: string;
  iin: string | null;
  photoDataUrl: string | null;
  summaries: IntakePdfCalculatedSummaries;
  payload: IntakeDraftPayload;
};

export type BuildIntakePdfViewModelInput = {
  applicationId: number;
  payload: IntakeDraftPayload | Record<string, unknown> | null | undefined;
  generatedAt?: Date;
  summaries: IntakePdfCalculatedSummaries;
  photoDataUrl?: string | null;
  /** IIN is kept in the application/person record, not duplicated into public intake payload. */
  iin?: string | null;
};

export function buildIntakePdfViewModel(input: BuildIntakePdfViewModelInput): IntakePdfViewModel {
  const generatedAt = input.generatedAt ?? new Date();
  // PDF is a display boundary.  The persisted v2 payload remains untouched;
  // only this ephemeral view adapts nullable canonical values for legacy UI helpers.
  const payload = reconcileIntakeDraftPayload(toIntakeFormPayload(
    (input.payload as IntakeDraftPayload | undefined) ?? emptyIntakeDraftPayload(),
  ));
  return {
    applicationId: input.applicationId,
    fullName: formatIntakeFullName(payload.personal) || "—",
    generatedDateLabel: buildIntakePdfGeneratedDateLabel(generatedAt),
    asOfIso: formatIntakePdfAsOfIso(generatedAt),
    organizationShortName: "",
    personnelNumber: normalizeIntakePersonnelNumber(payload.personal.personnel_number),
    alphabet: deriveIntakeSurnameAlphabet(payload.personal.last_name),
    birthPlace: String(payload.personal.birth_place ?? "").trim(),
    iin: String(input.iin ?? "").trim() || null,
    photoDataUrl: input.photoDataUrl ?? null,
    summaries: input.summaries,
    payload,
  };
}
