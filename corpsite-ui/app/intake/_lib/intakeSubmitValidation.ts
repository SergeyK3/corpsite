import type { IntakeDraftPayload } from "./intakeApi.client";
import { isIntakeListRowEmpty } from "./intakeEmptyRows";

export type IntakeSubmitIssue = { stepId: string; focusTestId: string; message: string };

const required = (value: unknown) => typeof value === "string" && value.trim().length > 0;

export function collectIntakeSubmitIssues(payload: IntakeDraftPayload): IntakeSubmitIssue[] {
  const issues: IntakeSubmitIssue[] = [];
  const add = (stepId: string, focusTestId: string, message: string, value: unknown) => {
    if (!required(value)) issues.push({ stepId, focusTestId, message });
  };

  if (!/^\+7\d{10}$/.test(payload.contacts.mobile_phone.trim())) {
    issues.push({ stepId: "contacts", focusTestId: "intake-mobile-phone", message: "Введите +7 и 10 цифр номера" });
  }
  payload.education.forEach((row, index) => {
    if (isIntakeListRowEmpty("education", row)) return;
    add("education", `intake-education-institution-${index}`, "Укажите учебное заведение", row.institution_original || row.institution);
  });
  payload.training.forEach((row, index) => {
    if (isIntakeListRowEmpty("training", row)) return;
    add("training", `intake-training-course-name-${index}`, "Укажите название курса", row.course_name_original || row.course_name);
  });
  payload.relatives.forEach((row, index) => {
    if (isIntakeListRowEmpty("relatives", row)) return;
    add("relatives", `intake-relative-relationship-${index}`, "Укажите степень родства", row.relationship);
    add("relatives", `intake-relative-full-name-${index}`, "Укажите ФИО", row.full_name);
  });
  payload.employment_biography.forEach((row, index) => {
    if (isIntakeListRowEmpty("employment_biography", row)) return;
    add("employment_biography", `intake-employment-organization-${index}`, "Укажите организацию", row.organization_original || row.organization);
    add("employment_biography", `intake-employment-position-${index}`, "Укажите должность", row.position_original || row.position);
    add("employment_biography", `intake-employment-year-from-${index}`, "Укажите дату начала", row.start_date || row.year_from);
  });
  payload.additional.foreign_languages.forEach((row, index) => {
    if (isIntakeListRowEmpty("foreign_languages", row)) return;
    add("additional", `intake-foreign-language-language-${index}`, "Укажите язык", row.language);
    add("additional", `intake-foreign-language-proficiency-${index}`, "Укажите уровень владения", row.proficiency);
  });
  payload.additional.awards.forEach((row, index) => {
    if (isIntakeListRowEmpty("awards", row)) return;
    add("additional", `intake-award-category-${index}`, "Укажите вид награды", row.category);
    add("additional", `intake-award-name-${index}`, "Укажите название награды", row.name || row.title);
  });
  payload.additional.academic_degrees.forEach((row, index) => {
    if (isIntakeListRowEmpty("academic_degrees", row)) return;
    add("additional", `intake-academic-degree-degree-${index}`, "Укажите учёную степень", row.degree || row.label);
  });
  payload.additional.academic_titles.forEach((row, index) => {
    if (isIntakeListRowEmpty("academic_titles", row)) return;
    add("additional", `intake-academic-title-academic-title-${index}`, "Укажите учёное звание", row.academic_title || row.label);
  });
  return issues;
}
