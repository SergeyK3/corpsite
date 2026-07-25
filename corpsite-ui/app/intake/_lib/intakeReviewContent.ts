import type { IntakeDraftPayload } from "./intakeApi.client";
import {
  normalizeIntakeAcademicDegreeEntry,
  normalizeIntakeAcademicTitleEntry,
  normalizeIntakeAwardEntry,
  normalizeIntakeForeignLanguageEntry,
  resolveIntakeAcademicDegreeDisplay,
  resolveIntakeAcademicTitleDisplay,
  resolveIntakeAwardCategoryDisplay,
  resolveIntakeAwardNameDisplay,
  resolveIntakeForeignLanguageDisplay,
} from "./intakeAdditional";
import { formatIntakeFullName } from "./intakeContactHelpers";
import {
  getIntakeEducationDocumentTypeLabel,
  getIntakeEducationTypeLabel,
  normalizeIntakeEducationEntry,
} from "./intakeEducation";
import { isIntakeEmploymentCurrent } from "./intakeEmploymentBiography";
import { formatIntakeDateForDisplay } from "./intakeDateValidation";
import { normalizeIntakeGenderValue } from "./intakePersonalDictionary";
import { deriveIntakeSurnameAlphabet } from "./intakePersonalFields";
import {
  formatIntakeBirthDateForDisplay,
  formatIntakePeriodForDisplay,
  formatIntakePeriodRange,
} from "./intakePeriodFormat";
import { getIntakeTrainingDocumentTypeLabel, normalizeIntakeTrainingEntry, resolveIntakeTrainingYearTo } from "./intakeTraining";
import { intakeMilitaryCompositionLabel } from "@/lib/militaryDictionary";

export type IntakeReviewField = {
  label: string;
  value: string;
};

export type IntakeReviewRecordCard = {
  title: string;
  lines: IntakeReviewField[];
};

export type IntakeReviewSectionContent = {
  stepId: string;
  title: string;
  testId: string;
  editTestId: string;
  empty: boolean;
  fields: IntakeReviewField[];
  records: IntakeReviewRecordCard[];
  subsections: Array<{
    title: string;
    testId: string;
    empty: boolean;
    records: IntakeReviewRecordCard[];
  }>;
};

function trimValue(value: string | null | undefined): string | null {
  const trimmed = String(value ?? "").trim();
  return trimmed || null;
}

function pushField(fields: IntakeReviewField[], label: string, value: string | null | undefined): void {
  const trimmed = trimValue(value);
  if (!trimmed) return;
  fields.push({ label, value: trimmed });
}

function buildRecordCard(title: string, pairs: Array<[string, string | null | undefined]>): IntakeReviewRecordCard {
  const lines: IntakeReviewField[] = [];
  for (const [label, value] of pairs) {
    pushField(lines, label, value);
  }
  return { title, lines };
}

export function buildIntakePersonalReviewSection(
  payload: IntakeDraftPayload,
  showPersonnelNumber: boolean,
): IntakeReviewSectionContent {
  const personal = payload.personal;
  const fields: IntakeReviewField[] = [];
  pushField(fields, "ФИО", formatIntakeFullName(personal));
  pushField(fields, "Дата рождения", formatIntakeBirthDateForDisplay(personal.birth_date));
  pushField(fields, "Место рождения", personal.birth_place);
  pushField(fields, "Пол", normalizeIntakeGenderValue(personal.gender));
  pushField(fields, "Гражданство", personal.citizenship);
  pushField(fields, "Национальность", personal.nationality);
  if (showPersonnelNumber) {
    pushField(fields, "Табельный номер", personal.personnel_number);
  }
  const alphabet = deriveIntakeSurnameAlphabet(personal.last_name);
  if (alphabet) {
    pushField(fields, "Алфавит", alphabet);
  }
  if (trimValue(personal.photo_file_id)) {
    pushField(fields, "Фотография", "Загружена");
  }

  return {
    stepId: "personal",
    title: "Персональные данные",
    testId: "intake-review-section-personal",
    editTestId: "intake-review-edit-personal",
    empty: fields.length === 0,
    fields,
    records: [],
    subsections: [],
  };
}

export function buildIntakeContactsReviewSection(payload: IntakeDraftPayload): IntakeReviewSectionContent {
  const contacts = payload.contacts;
  const fields: IntakeReviewField[] = [];
  pushField(fields, "Мобильный телефон", contacts.mobile_phone);
  pushField(fields, "Email", contacts.email);
  pushField(fields, "Адрес регистрации", contacts.registration_address);
  pushField(fields, "Адрес проживания", contacts.residence_address);

  return {
    stepId: "contacts",
    title: "Контакты",
    testId: "intake-review-section-contacts",
    editTestId: "intake-review-edit-contacts",
    empty: fields.length === 0,
    fields,
    records: [],
    subsections: [],
  };
}

export function buildIntakeEducationReviewSection(payload: IntakeDraftPayload): IntakeReviewSectionContent {
  const records = payload.education.map((raw, index) => {
    const item = normalizeIntakeEducationEntry(raw);
    const title = trimValue(item.institution) ?? `Запись ${index + 1}`;
    return buildRecordCard(title, [
      ["Вид образования", getIntakeEducationTypeLabel(item.education_type)],
      ["Учебное заведение", item.institution],
      ["Период", formatIntakePeriodRange(item.year_from, item.year_to)],
      ["Специальность", item.specialty],
      ["Квалификация", item.qualification],
      ["Документ", getIntakeEducationDocumentTypeLabel(item.document_type)],
      ["№ документа", item.diploma_number],
    ]);
  });

  return {
    stepId: "education",
    title: "Образование",
    testId: "intake-review-section-education",
    editTestId: "intake-review-edit-education",
    empty: !records.some((record) => record.lines.length > 0),
    fields: [],
    records,
    subsections: [],
  };
}

export function buildIntakeTrainingReviewSection(payload: IntakeDraftPayload): IntakeReviewSectionContent {
  const records = payload.training.map((raw, index) => {
    const item = normalizeIntakeTrainingEntry(raw);
    const title = trimValue(item.course_name) ?? trimValue(item.institution) ?? `Запись ${index + 1}`;
    return buildRecordCard(title, [
      ["Курс", item.course_name],
      ["Организация", item.institution],
      ["Период", formatIntakePeriodRange(item.year_from, resolveIntakeTrainingYearTo(item))],
      ["Документ", getIntakeTrainingDocumentTypeLabel(item.document_type)],
      ["№ документа", item.document_number],
      ["Часы", item.hours],
    ]);
  });

  return {
    stepId: "training",
    title: "Обучение",
    testId: "intake-review-section-training",
    editTestId: "intake-review-edit-training",
    empty: !records.some((record) => record.lines.length > 0),
    fields: [],
    records,
    subsections: [],
  };
}

export function buildIntakeRelativesReviewSection(payload: IntakeDraftPayload): IntakeReviewSectionContent {
  const records = payload.relatives.map((item, index) => {
    const title = trimValue(item.full_name) ?? `Запись ${index + 1}`;
    return buildRecordCard(title, [
      ["Степень родства", item.relationship],
      ["ФИО", item.full_name],
      ["Дата рождения", formatIntakeDateForDisplay(item.birth_year, "period")],
      ["Место работы", item.work_place],
    ]);
  });

  return {
    stepId: "relatives",
    title: "Родственники",
    testId: "intake-review-section-relatives",
    editTestId: "intake-review-edit-relatives",
    empty: !records.some((record) => record.lines.length > 0),
    fields: [],
    records,
    subsections: [],
  };
}

export function buildIntakeEmploymentReviewSection(payload: IntakeDraftPayload): IntakeReviewSectionContent {
  const records = payload.employment_biography.map((item, index) => {
    const title = trimValue(item.organization) ?? `Запись ${index + 1}`;
    const from = formatIntakePeriodForDisplay(item.year_from);
    const period = isIntakeEmploymentCurrent(item)
      ? from
        ? `${from} — по настоящее время`
        : "По настоящее время"
      : formatIntakePeriodRange(item.year_from, item.year_to);
    return buildRecordCard(title, [
      ["Организация", item.organization],
      ["Должность", item.position],
      ["Период", period === "—" ? null : period],
      ["Причина увольнения", item.reason_for_leaving],
    ]);
  });

  return {
    stepId: "employment_biography",
    title: "Трудовая биография",
    testId: "intake-review-section-employment",
    editTestId: "intake-review-edit-employment",
    empty: !records.some((record) => record.lines.length > 0),
    fields: [],
    records,
    subsections: [],
  };
}

export function buildIntakeMilitaryReviewSection(payload: IntakeDraftPayload): IntakeReviewSectionContent {
  const military = payload.military;
  const fields: IntakeReviewField[] = [];
  pushField(fields, "Состав", intakeMilitaryCompositionLabel(military.composition));
  pushField(fields, "Воинское звание", military.rank);
  pushField(fields, "Статус", military.status);
  pushField(fields, "Категория", military.category);
  pushField(fields, "Номер ВУС", military.specialty_code);
  pushField(fields, "Категория годности", military.fitness_category);
  pushField(fields, "Военкомат", military.commissariat);
  pushField(fields, "Группа учёта", military.registration_group);
  pushField(fields, "Категория учёта", military.registration_category);

  return {
    stepId: "military",
    title: "Воинский учёт",
    testId: "intake-review-section-military",
    editTestId: "intake-review-edit-military",
    empty: fields.length === 0,
    fields,
    records: [],
    subsections: [],
  };
}

function buildAdditionalSubsectionRecords<T>(
  items: T[],
  declaredEmpty: boolean,
  title: string,
  testId: string,
  buildTitle: (item: T, index: number) => string,
  buildLines: (item: T) => Array<[string, string | null | undefined]>,
): IntakeReviewSectionContent["subsections"][number] {
  if (declaredEmpty) {
    return { title, testId, empty: true, records: [] };
  }
  const records = items.map((item, index) => buildRecordCard(buildTitle(item, index), buildLines(item)));
  return {
    title,
    testId,
    empty: records.every((record) => record.lines.length === 0),
    records,
  };
}

export function buildIntakeAdditionalReviewSection(payload: IntakeDraftPayload): IntakeReviewSectionContent {
  const additional = payload.additional;
  const subsections = [
    buildAdditionalSubsectionRecords(
      additional.foreign_languages,
      additional.foreign_languages_none,
      "Иностранные языки",
      "intake-review-additional-languages",
      (item, index) =>
        resolveIntakeForeignLanguageDisplay(normalizeIntakeForeignLanguageEntry(item).language) !== "—"
          ? resolveIntakeForeignLanguageDisplay(normalizeIntakeForeignLanguageEntry(item).language)
          : `Запись ${index + 1}`,
      (item) => {
        const normalized = normalizeIntakeForeignLanguageEntry(item);
        return [
          ["Язык", resolveIntakeForeignLanguageDisplay(normalized.language)],
          ["Уровень владения", normalized.proficiency],
        ];
      },
    ),
    buildAdditionalSubsectionRecords(
      additional.awards,
      additional.awards_none,
      "Награды",
      "intake-review-additional-awards",
      (item, index) => {
        const normalized = normalizeIntakeAwardEntry(item);
        const name = resolveIntakeAwardNameDisplay(normalized);
        if (name !== "—") return name;
        const category = resolveIntakeAwardCategoryDisplay(normalized);
        return category !== "—" ? category : `Запись ${index + 1}`;
      },
      (item) => {
        const normalized = normalizeIntakeAwardEntry(item);
        return [
          ["Категория", resolveIntakeAwardCategoryDisplay(normalized)],
          ["Название", resolveIntakeAwardNameDisplay(normalized)],
          ["Кем выдано", normalized.issued_by],
          ["Дата награждения", formatIntakeDateForDisplay(normalized.awarded_at, "period")],
          ["№ документа", normalized.document_number],
        ];
      },
    ),
    buildAdditionalSubsectionRecords(
      additional.academic_degrees,
      additional.academic_degrees_none,
      "Учёные степени",
      "intake-review-additional-degrees",
      (item, index) => {
        const summary = resolveIntakeAcademicDegreeDisplay(normalizeIntakeAcademicDegreeEntry(item));
        return summary !== "—" ? summary : `Запись ${index + 1}`;
      },
      (item) => {
        const normalized = normalizeIntakeAcademicDegreeEntry(item);
        return [
          ["Степень", resolveIntakeAcademicDegreeDisplay(normalized)],
          ["Дата присуждения", formatIntakeDateForDisplay(normalized.completed_at, "period")],
          ["№ документа", normalized.document_number],
        ];
      },
    ),
    buildAdditionalSubsectionRecords(
      additional.academic_titles,
      additional.academic_titles_none,
      "Учёные звания",
      "intake-review-additional-titles",
      (item, index) => {
        const summary = resolveIntakeAcademicTitleDisplay(normalizeIntakeAcademicTitleEntry(item));
        return summary !== "—" ? summary : `Запись ${index + 1}`;
      },
      (item) => {
        const normalized = normalizeIntakeAcademicTitleEntry(item);
        return [
          ["Звание", resolveIntakeAcademicTitleDisplay(normalized)],
          ["Дата присвоения", formatIntakeDateForDisplay(normalized.completed_at, "period")],
          ["№ документа", normalized.document_number],
        ];
      },
    ),
  ];

  const empty = subsections.every((section) => section.empty);

  return {
    stepId: "additional",
    title: "Дополнительные сведения",
    testId: "intake-review-section-additional",
    editTestId: "intake-review-edit-additional",
    empty,
    fields: [],
    records: [],
    subsections,
  };
}

export function buildIntakeReviewSections(
  payload: IntakeDraftPayload,
  showPersonnelNumber: boolean,
): IntakeReviewSectionContent[] {
  return [
    buildIntakePersonalReviewSection(payload, showPersonnelNumber),
    buildIntakeContactsReviewSection(payload),
    buildIntakeEducationReviewSection(payload),
    buildIntakeTrainingReviewSection(payload),
    buildIntakeRelativesReviewSection(payload),
    buildIntakeEmploymentReviewSection(payload),
    buildIntakeMilitaryReviewSection(payload),
    buildIntakeAdditionalReviewSection(payload),
  ];
}
