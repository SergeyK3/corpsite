import {
  calculateExpiringCertificates,
  calculateTrainingHoursLast5y,
  trainingSummaryRecordFromIntakeEntry,
  type ExpiringCertificateSummary,
  type TrainingHoursLast5ySummary,
} from "@/lib/trainingSummary";

import type { IntakeDraftPayload } from "./intakeApi.client";
import { calculateEmploymentTenure, type EmploymentTenureCalculation } from "./employmentTenureApi.client";
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
  const employmentTenure =
    payload.employment_biography.length > 0
      ? await calculateEmploymentTenure(payload.employment_biography, {
          calculationDate: asOfIso,
          serverSide: true,
        })
      : null;

  return {
    asOfIso,
    ...training,
    employmentTenure,
  };
}
