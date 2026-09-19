import {
  calculateExpiringCertificates,
  calculateTrainingHoursLast5y,
  trainingSummaryRecordFromIntakeEntry,
  type ExpiringCertificateSummary,
  type TrainingHoursLast5ySummary,
} from "@/lib/trainingSummary";

import type { IntakeDraftPayload } from "./intakeApi.client";
import type { EmploymentTenureCalculation } from "./employmentTenureApi.client";
import { formatIntakePdfAsOfIso } from "./intakePdfDate";

export type IntakePdfCalculatedSummaries = {
  asOfIso: string;
  trainingHours: TrainingHoursLast5ySummary;
  expiringCertificates: ExpiringCertificateSummary[];
  employmentTenure: EmploymentTenureCalculation | null;
};

export function buildIntakePdfTrainingSummaries(
  payload: IntakeDraftPayload,
  asOfIso: string,
): Pick<IntakePdfCalculatedSummaries, "trainingHours" | "expiringCertificates"> {
  const records = payload.training.map((item) => trainingSummaryRecordFromIntakeEntry(item));
  return {
    trainingHours: calculateTrainingHoursLast5y(records, asOfIso),
    expiringCertificates: calculateExpiringCertificates(records, asOfIso),
  };
}

export async function buildIntakePdfCalculatedSummaries(
  payload: IntakeDraftPayload,
  generatedAt: Date = new Date(),
): Promise<IntakePdfCalculatedSummaries> {
  const asOfIso = formatIntakePdfAsOfIso(generatedAt);
  const training = buildIntakePdfTrainingSummaries(payload, asOfIso);
  return {
    asOfIso,
    ...training,
    // Tenure is an HR-only working calculation.  A personal-card PDF must
    // never request, embed, or imply a preliminary tenure decision.
    employmentTenure: null,
  };
}
