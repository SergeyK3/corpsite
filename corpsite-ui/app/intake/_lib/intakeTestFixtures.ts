import type { IntakeRelative } from "./intakeApi.client";
import { normalizeIntakeEducationEntry } from "./intakeEducation";
import { normalizeIntakeTrainingEntry } from "./intakeTraining";
import { normalizeIntakeEmploymentBiographyEntry } from "./intakeEmploymentBiography";
import { emptyIntakeRelativeEntry } from "./intakeRelatives";

/** Test data is normalized through the same contracts used by the form. */
export const intakeEducationFixture = normalizeIntakeEducationEntry;
export const intakeTrainingFixture = normalizeIntakeTrainingEntry;
export const intakeEmploymentFixture = (value: Record<string, unknown>, index = 0) =>
  ({ ...normalizeIntakeEmploymentBiographyEntry(value, index), ...value });
export function intakeRelativeFixture(value: Partial<IntakeRelative>): IntakeRelative {
  return {
    ...emptyIntakeRelativeEntry(),
    ...value,
    birth_date: value.birth_date ?? value.birth_year ?? "",
    workplace: value.workplace ?? value.work_place ?? "",
  };
}
