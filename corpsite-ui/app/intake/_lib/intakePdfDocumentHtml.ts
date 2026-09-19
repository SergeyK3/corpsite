import {
  formatIntakeAcademicDegreeReviewLine,
  formatIntakeAcademicTitleReviewLine,
  formatIntakeAdditionalSubsectionReviewSummary,
  formatIntakeAwardReviewLine,
  formatIntakeForeignLanguageReviewLine,
} from "./intakeAdditional";
import {
  formatIntakeEducationPeriodCell,
  formatIntakeEducationSpecialtyCell,
  getIntakeEducationDocumentTypeLabel,
  getIntakeEducationTypeLabel,
  intakeEducationCellValue,
} from "./intakeEducation";
import { personalCardSectionTitle } from "./personalCardSections";
import { formatIntakeBirthDateForDisplay, formatIntakePeriodRange } from "./intakePeriodFormat";
import {
  formatIntakeTrainingHoursCell,
  formatIntakeTrainingPeriodCell,
  getIntakeTrainingDocumentTypeLabel,
  intakeTrainingCellValue,
} from "./intakeTraining";
import {
  formatIntakeRelativeBirthCell,
  intakeRelativeCellValue,
} from "./intakeRelatives";
import { intakeMilitaryCompositionLabel } from "./intakeMilitaryDictionary";
import { INTAKE_PDF_DOCUMENT_CSS, INTAKE_PDF_SECTION_FLOW_CLASS } from "./intakePdfDocumentCss";
import type { IntakePdfViewModel } from "./intakePdfViewModel";

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function cell(value: string | null | undefined): string {
  return escapeHtml(String(value ?? "").trim() || "—");
}

function optionalCell(value: string | null | undefined): string {
  return escapeHtml(String(value ?? "").trim());
}

function buildIntakePdfPhotoSlotHtml(photoDataUrl: string | null | undefined): string {
  if (photoDataUrl) {
    return `<div class="intake-pdf-photo-slot" data-testid="intake-pdf-photo-slot">
    <img src="${photoDataUrl}" alt="" class="intake-pdf-photo-image" data-testid="intake-pdf-photo-image" />
  </div>`;
  }
  return `<div class="intake-pdf-photo-slot" data-testid="intake-pdf-photo-slot">
    <span class="intake-pdf-photo-caption">Место для фотографии 3×4</span>
  </div>`;
}

function buildIntakePdfHeaderHtml(model: IntakePdfViewModel): string {
  const personal = model.payload.personal;
  const orgLine = model.organizationShortName
    ? cell(model.organizationShortName)
    : "&nbsp;";
  const generatedDate = cell(model.generatedDateLabel.replace(/^Дата формирования:\s*/, ""));
  return `<header class="intake-pdf-header" data-testid="intake-pdf-header">
<div class="intake-pdf-header-top">
  <div class="intake-pdf-organization" data-testid="intake-pdf-organization">${orgLine}</div>
  <div class="intake-pdf-title-block">
    <h1 class="intake-pdf-title">ЛИЧНАЯ КАРТОЧКА</h1>
    <p class="intake-pdf-generated-date" data-testid="intake-pdf-generated-date">Дата формирования: ${generatedDate}</p>
  </div>
  <div class="intake-pdf-index-box">
    <table class="intake-pdf-index-values"><tbody><tr>
      <td data-testid="intake-pdf-personnel-number">${optionalCell(model.personnelNumber)}</td>
      <td class="intake-pdf-alphabet" data-testid="intake-pdf-alphabet">${optionalCell(model.alphabet)}</td>
    </tr></tbody></table>
    <div class="intake-pdf-index-labels">
      <span>таб.номер</span>
      <span>алфавит</span>
    </div>
  </div>
</div>
<div class="intake-pdf-header-main">
  ${buildIntakePdfPhotoSlotHtml(model.photoDataUrl)}
  <table class="intake-pdf-header-fields"><tbody>
    <tr><td class="intake-pdf-field-label">ФИО</td><td colspan="3" data-testid="intake-pdf-full-name">${cell(model.fullName === "—" ? "" : model.fullName)}</td></tr>
    <tr><td class="intake-pdf-field-label">ИИН</td><td colspan="3" data-testid="intake-pdf-iin">${cell(model.iin)}</td></tr>
    <tr><td class="intake-pdf-field-label">Место рождения</td><td colspan="3" data-testid="intake-pdf-birth-place">${cell(model.birthPlace)}</td></tr>
    <tr class="intake-pdf-split-row">
      <td class="intake-pdf-field-label">Пол</td><td>${cell(personal.gender)}</td>
      <td class="intake-pdf-field-label">Дата рождения</td><td>${cell(formatIntakeBirthDateForDisplay(personal.birth_date))}</td>
    </tr>
    <tr><td class="intake-pdf-field-label">Гражданство</td><td colspan="3">${cell(personal.citizenship)}</td></tr>
    <tr><td class="intake-pdf-field-label">Национальность</td><td colspan="3">${cell(personal.nationality)}</td></tr>
  </tbody></table>
</div>
</header>`;
}

function section(title: string, testId: string, body: string): string {
  return `<section class="intake-pdf-section ${INTAKE_PDF_SECTION_FLOW_CLASS}" data-testid="${escapeHtml(testId)}">
<h2 class="intake-pdf-section-title">${escapeHtml(title)}</h2>
${body}
</section>`;
}

function fieldsTable(rows: Array<[string, string]>): string {
  const body = rows
    .map(
      ([label, value]) =>
        `<tr><td>${escapeHtml(label)}</td><td>${cell(value)}</td></tr>`,
    )
    .join("");
  return `<table class="intake-pdf-fields"><tbody>${body}</tbody></table>`;
}

function dataTable(headers: string[], rows: string[][]): string {
  if (rows.length === 0) {
    return `<p class="intake-pdf-empty">Нет записей</p>`;
  }
  const head = headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("");
  const body = rows
    .map((row) => `<tr>${row.map((value) => `<td>${cell(value)}</td>`).join("")}</tr>`)
    .join("");
  return `<table class="intake-pdf-data-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function militaryStatusLabel(status: string | null | undefined): string {
  switch (String(status ?? "").trim()) {
    case "not_provided": return "Сведения не предоставлены";
    case "not_applicable": return "Не подлежит воинскому учёту";
    case "not_registered": return "Не состоит на воинском учёте";
    case "registered": return "Состоит на воинском учёте";
    default: return String(status ?? "");
  }
}

function additionalSubsection(title: string, testId: string, summary: string): string {
  const normalized = String(summary ?? "").trim();
  if (normalized === "0 зап." || normalized === "Нет сведений") {
    return `<div class="intake-pdf-additional-subsection" data-testid="${escapeHtml(testId)}">
<h3 class="intake-pdf-subsection-title">${escapeHtml(title)}: ${escapeHtml(normalized)}</h3>
</div>`;
  }
  return `<div class="intake-pdf-additional-subsection" data-testid="${escapeHtml(testId)}">
<h3 class="intake-pdf-subsection-title">${escapeHtml(title)}</h3>
<p>${cell(summary)}</p>
</div>`;
}

export function buildIntakePdfDocumentHtml(model: IntakePdfViewModel): string {
  const { payload } = model;
  const contacts = payload.contacts;
  const military = payload.military;
  const additional = payload.additional;

  const generalSection = section(
    personalCardSectionTitle("general"),
    "intake-pdf-section-general",
    [
      buildIntakePdfHeaderHtml(model),
      fieldsTable([
      ["Мобильный телефон", contacts.mobile_phone],
      ["Email", contacts.email],
      ["Адрес регистрации", contacts.registration_address],
      ["Адрес проживания", contacts.residence_address],
      ]),
    ].join(""),
  );

  const educationSection = section(
    personalCardSectionTitle("education"),
    "intake-pdf-section-education",
    dataTable(
      [
        "Тип",
        "Учебное заведение",
        "Период",
        "Специальность / квалификация",
        "Документ",
        "№ документа",
      ],
      payload.education.map((item) => [
        getIntakeEducationTypeLabel(item.education_type),
        intakeEducationCellValue(item.institution),
        formatIntakeEducationPeriodCell(item.year_from, item.year_to),
        formatIntakeEducationSpecialtyCell(item.specialty, item.qualification),
        getIntakeEducationDocumentTypeLabel(item.document_type),
        intakeEducationCellValue(item.diploma_number),
      ]),
    ),
  );

  const trainingSection = section(
    personalCardSectionTitle("training"),
    "intake-pdf-section-training",
    [
      dataTable(
        ["Курс", "Организация", "Период", "Документ", "№ документа", "Часы"],
        payload.training.map((item) => [
          intakeTrainingCellValue(item.course_name),
          intakeTrainingCellValue(item.institution),
          formatIntakeTrainingPeriodCell(item),
          getIntakeTrainingDocumentTypeLabel(item.document_type),
          intakeTrainingCellValue(item.document_number),
          formatIntakeTrainingHoursCell(item.hours),
        ]),
      ),
    ].join(""),
  );

  const relativesSection = section(
    personalCardSectionTitle("relatives"),
    "intake-pdf-section-relatives",
    dataTable(
      ["Степень родства", "ФИО", "Дата рождения", "Место работы"],
      payload.relatives.map((item) => [
        intakeRelativeCellValue(item.relationship),
        intakeRelativeCellValue(item.full_name),
        formatIntakeRelativeBirthCell(item.birth_year),
        intakeRelativeCellValue(item.work_place),
      ]),
    ),
  );

  const employmentSection = section(
    personalCardSectionTitle("employment_biography"),
    "intake-pdf-section-employment",
    [
      dataTable(
        ["Организация", "Должность", "Период", "Причина увольнения"],
        payload.employment_biography.map((item) => [
          item.organization_normalized || item.organization_original,
          item.position_normalized || item.position_original,
          item.end_date ? formatIntakePeriodRange(item.start_date, item.end_date) : `${formatIntakePeriodRange(item.start_date, null)} по настоящее время`,
          item.reason_for_leaving ?? "",
        ]),
      ),
    ].join(""),
  );

  const categorySection = section(
    personalCardSectionTitle("qualification_category"),
    "intake-pdf-section-category",
    "<p class=\"intake-pdf-empty\">Квалификационная категория не указана</p>",
  );
  const currentOrganizationSection = section(
    personalCardSectionTitle("current_organization"),
    "intake-pdf-section-current-organization",
    "<p class=\"intake-pdf-empty\">Работа в текущей организации ещё не начата</p>",
  );

  const militaryBody = String(military.status ?? "").trim() === "not_provided"
    ? '<p class="intake-pdf-empty">Сведения о воинском учёте не предоставлены</p>'
    : fieldsTable([
        ["Статус", militaryStatusLabel(military.status)],
        ["Звание", military.rank],
        ["Категория", military.category],
        ["Состав", intakeMilitaryCompositionLabel(military.composition)],
      ]);
  const militarySection = section(
    personalCardSectionTitle("military"),
    "intake-pdf-section-military",
    militaryBody,
  );

  const languagesSection = section(
    personalCardSectionTitle("foreign_languages"),
    "intake-pdf-section-languages",
    additionalSubsection(
      "Иностранные языки",
      "intake-pdf-additional-languages",
      formatIntakeAdditionalSubsectionReviewSummary(
        additional.foreign_languages,
        additional.foreign_languages_none,
        (item) => formatIntakeForeignLanguageReviewLine(item),
      ),
    ),
  );

  const noteSection = section(
    personalCardSectionTitle("note"),
    "intake-pdf-section-note",
    '<p class="intake-pdf-empty">Нет примечаний</p>',
  );

  const additionalSection = section(
    personalCardSectionTitle("additional"),
    "intake-pdf-section-additional",
    [
      additionalSubsection(
        "Награды",
        "intake-pdf-additional-awards",
        formatIntakeAdditionalSubsectionReviewSummary(
          additional.awards,
          additional.awards_none,
          (item) => formatIntakeAwardReviewLine(item),
        ),
      ),
      additionalSubsection(
        "Учёные степени",
        "intake-pdf-additional-degrees",
        formatIntakeAdditionalSubsectionReviewSummary(
          additional.academic_degrees,
          additional.academic_degrees_none,
          (item) => formatIntakeAcademicDegreeReviewLine(item),
        ),
      ),
      additionalSubsection(
        "Учёные звания",
        "intake-pdf-additional-titles",
        formatIntakeAdditionalSubsectionReviewSummary(
          additional.academic_titles,
          additional.academic_titles_none,
          (item) => formatIntakeAcademicTitleReviewLine(item),
        ),
      ),
    ].join(""),
  );

  const body = `<div class="intake-pdf-document">
${generalSection}
${educationSection}
${trainingSection}
${categorySection}
${employmentSection}
${currentOrganizationSection}
${militarySection}
${relativesSection}
${languagesSection}
${noteSection}
${additionalSection}
</div>`;

  return body;
}

export function buildIntakePdfHtmlDocument(model: IntakePdfViewModel): string {
  const body = buildIntakePdfDocumentHtml(model);
  return `<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>${INTAKE_PDF_DOCUMENT_CSS}</style>
</head>
<body>
${body}
</body>
</html>`;
}

export const INTAKE_PDF_SECTION_TEST_IDS = [
  "intake-pdf-section-general",
  "intake-pdf-section-education",
  "intake-pdf-section-training",
  "intake-pdf-section-category",
  "intake-pdf-section-employment",
  "intake-pdf-section-current-organization",
  "intake-pdf-section-military",
  "intake-pdf-section-relatives",
  "intake-pdf-section-languages",
  "intake-pdf-section-note",
  "intake-pdf-section-additional",
] as const;
