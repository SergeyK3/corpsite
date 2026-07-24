import { reconcileIntakeDraftPayload } from "./intakeDraftReconcile";
import { emptyIntakeDraftPayload, type IntakeDraftPayload } from "./intakeApi.client";
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
};

export function buildIntakePdfViewModel(input: BuildIntakePdfViewModelInput): IntakePdfViewModel {
  const generatedAt = input.generatedAt ?? new Date();
  const payload = reconcileIntakeDraftPayload(
    (input.payload as IntakeDraftPayload | undefined) ?? emptyIntakeDraftPayload(),
  );
  return {
    applicationId: input.applicationId,
    fullName: formatIntakeFullName(payload.personal) || "—",
    generatedDateLabel: buildIntakePdfGeneratedDateLabel(generatedAt),
    asOfIso: formatIntakePdfAsOfIso(generatedAt),
    organizationShortName: "",
    personnelNumber: normalizeIntakePersonnelNumber(payload.personal.personnel_number),
    alphabet: deriveIntakeSurnameAlphabet(payload.personal.last_name),
    birthPlace: String(payload.personal.birth_place ?? "").trim(),
    photoDataUrl: input.photoDataUrl ?? null,
    summaries: input.summaries,
    payload,
  };
}
