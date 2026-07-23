import type { IntakeDraftPayload } from "./intakeApi.client";
import { INTAKE_STEPS } from "./intakeApi.client";
import { formatIntakeFullName } from "./intakeContactHelpers";
import {
  isInvalidIntakeTrainingPeriodRange,
  resolveIntakeTrainingYearTo,
} from "./intakeTraining";
import {
  formatPersonnelDayDateForDisplay,
  isIncompletePersonnelBirthDate,
  isIncompletePersonnelDocumentDate,
  PERSONNEL_DAY_DATE_PLACEHOLDER as INTAKE_DATE_PLACEHOLDER,
  PERSONNEL_INCOMPLETE_DATE_HINT as INTAKE_INCOMPLETE_DATE_HINT,
  PERSONNEL_INCOMPLETE_DATE_SUFFIX as INTAKE_INCOMPLETE_DATE_REVIEW_SUFFIX,
  type PersonnelDayDateMode,
} from "@/lib/personnelDayDate";

export {
  INTAKE_DATE_PLACEHOLDER,
  INTAKE_INCOMPLETE_DATE_HINT,
  INTAKE_INCOMPLETE_DATE_REVIEW_SUFFIX,
};

export type IntakeDateFieldKind = "birth" | "period";

function intakeDateMode(kind: IntakeDateFieldKind): PersonnelDayDateMode {
  return kind === "birth" ? "birth" : "document";
}

export {
  isValidPersonnelDayDateIso as isValidIntakeFullDateIso,
  isIncompletePersonnelBirthDate as isIncompleteIntakeBirthDate,
  isIncompletePersonnelDocumentDate as isIncompleteIntakePeriodDate,
} from "@/lib/personnelDayDate";

export function isIncompleteIntakeDateValue(
  value: string | null | undefined,
  kind: IntakeDateFieldKind,
): boolean {
  return kind === "birth"
    ? isIncompletePersonnelBirthDate(value)
    : isIncompletePersonnelDocumentDate(value);
}

export function formatIntakeDateForDisplay(
  value: string | null | undefined,
  kind: IntakeDateFieldKind,
): string {
  return formatPersonnelDayDateForDisplay(value, intakeDateMode(kind));
}

export type IntakeDateValidationIssue = {
  field: string;
  message: string;
  stepId: string;
  focusTestId: string;
};

function recordLabel(value: string, fallback: string): string {
  const text = (value || "").trim();
  return text || fallback;
}

function formatIssueMessage(section: string, record: string, fieldLabel: string): string {
  return `${section} → ${record} → ${fieldLabel}`;
}

function pushIssue(issues: Map<string, IntakeDateValidationIssue>, issue: IntakeDateValidationIssue): void {
  if (!issues.has(issue.field)) {
    issues.set(issue.field, issue);
  }
}

export function resolveIntakeDateIssueStepIndex(issue: Pick<IntakeDateValidationIssue, "stepId">): number {
  const index = INTAKE_STEPS.findIndex((step) => step.id === issue.stepId);
  return index >= 0 ? index : 0;
}

export function collectIntakeDateValidationIssues(payload: IntakeDraftPayload): IntakeDateValidationIssue[] {
  const issues = new Map<string, IntakeDateValidationIssue>();

  if (isIncompletePersonnelBirthDate(payload.personal?.birth_date)) {
    pushIssue(issues, {
      field: "personal.birth_date",
      stepId: "personal",
      focusTestId: "intake-birth-date",
      message: formatIssueMessage(
        "Персональные данные",
        recordLabel(formatIntakeFullName(payload.personal), "Персональные данные"),
        "дата рождения",
      ),
    });
  }

  payload.education?.forEach((item, index) => {
    const record = recordLabel(item.institution, `Запись ${index + 1}`);
    if (isIncompletePersonnelDocumentDate(item.year_from)) {
      pushIssue(issues, {
        field: `education[${index}].year_from`,
        stepId: "education",
        focusTestId: `intake-education-year-from-${index}`,
        message: formatIssueMessage("Образование", record, "дата поступления"),
      });
    }
    if (isIncompletePersonnelDocumentDate(item.year_to)) {
      pushIssue(issues, {
        field: `education[${index}].year_to`,
        stepId: "education",
        focusTestId: `intake-education-year-to-${index}`,
        message: formatIssueMessage("Образование", record, "дата окончания"),
      });
    }
  });

  payload.training?.forEach((item, index) => {
    const record = recordLabel(item.course_name || item.institution, `Запись ${index + 1}`);
    const yearTo = resolveIntakeTrainingYearTo(item);
    if (isIncompletePersonnelDocumentDate(item.year_from)) {
      pushIssue(issues, {
        field: `training[${index}].year_from`,
        stepId: "training",
        focusTestId: `intake-training-year-from-${index}`,
        message: formatIssueMessage("Обучение", record, "дата начала"),
      });
    }
    if (isIncompletePersonnelDocumentDate(yearTo)) {
      pushIssue(issues, {
        field: `training[${index}].year_to`,
        stepId: "training",
        focusTestId: `intake-training-year-to-${index}`,
        message: formatIssueMessage("Обучение", record, "дата окончания"),
      });
    }
    if (isInvalidIntakeTrainingPeriodRange(item)) {
      pushIssue(issues, {
        field: `training[${index}].year_from`,
        stepId: "training",
        focusTestId: `intake-training-year-from-${index}`,
        message: formatIssueMessage("Обучение", record, "некорректный период"),
      });
    }
  });

  payload.relatives?.forEach((item, index) => {
    const record = recordLabel(item.full_name, `Запись ${index + 1}`);
    if (isIncompletePersonnelDocumentDate(item.birth_year)) {
      pushIssue(issues, {
        field: `relatives[${index}].birth_year`,
        stepId: "relatives",
        focusTestId: `intake-relative-birth-year-${index}`,
        message: formatIssueMessage("Родственники", record, "дата рождения"),
      });
    }
  });

  payload.employment_biography?.forEach((item, index) => {
    const record = recordLabel(item.organization, `Запись ${index + 1}`);
    if (isIncompletePersonnelDocumentDate(item.year_from)) {
      pushIssue(issues, {
        field: `employment_biography[${index}].year_from`,
        stepId: "employment_biography",
        focusTestId: `intake-employment-year-from-${index}`,
        message: formatIssueMessage("Трудовая биография", record, "дата начала"),
      });
    }
    if (isIncompletePersonnelDocumentDate(item.year_to)) {
      pushIssue(issues, {
        field: `employment_biography[${index}].year_to`,
        stepId: "employment_biography",
        focusTestId: `intake-employment-year-to-${index}`,
        message: formatIssueMessage("Трудовая биография", record, "дата окончания"),
      });
    }
  });

  return Array.from(issues.values());
}

export function hasBlockingIntakeDateIssues(payload: IntakeDraftPayload): boolean {
  return collectIntakeDateValidationIssues(payload).length > 0;
}
