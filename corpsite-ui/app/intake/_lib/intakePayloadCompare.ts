import type {
  IntakeAdditionalPayload,
  IntakeDraftPayload,
  IntakeEducation,
  IntakeTraining,
} from "./intakeApi.client";

type StringRecord<T> = { [K in keyof T]: string };

export type CanonicalIntakeDraftPayload = {
  personal: StringRecord<IntakeDraftPayload["personal"]>;
  contacts: StringRecord<IntakeDraftPayload["contacts"]>;
  education: StringRecord<IntakeEducation>[];
  training: StringRecord<
    Omit<IntakeTraining, "hours_is_manual" | "year"> & { hours_is_manual: string }
  >[];
  relatives: StringRecord<IntakeDraftPayload["relatives"][number]>[];
  employment_biography: StringRecord<IntakeDraftPayload["employment_biography"][number]>[];
  military: StringRecord<IntakeDraftPayload["military"]>;
  additional: {
    foreign_languages: StringRecord<IntakeAdditionalPayload["foreign_languages"][number]>[];
    foreign_languages_none: string;
    awards: StringRecord<IntakeAdditionalPayload["awards"][number]>[];
    awards_none: string;
    academic_degrees: StringRecord<IntakeAdditionalPayload["academic_degrees"][number]>[];
    academic_degrees_none: string;
    academic_titles: StringRecord<IntakeAdditionalPayload["academic_titles"][number]>[];
    academic_titles_none: string;
  };
  current_step: string;
};

function normalizeScalar(value: string | null | undefined): string {
  if (value == null) return "";
  return String(value);
}

function normalizeDict<T extends Record<string, string>>(
  template: T,
  overlay: Partial<T> | undefined,
): StringRecord<T> {
  const source: Partial<T> = overlay ?? {};
  const result: StringRecord<T> = { ...template };
  for (const key in template) {
    if (!Object.prototype.hasOwnProperty.call(template, key)) continue;
    result[key] = normalizeScalar(source[key] ?? template[key] ?? "");
  }
  return result;
}

function normalizeTrainingItems(
  items: IntakeTraining[] | undefined,
): CanonicalIntakeDraftPayload["training"] {
  if (!Array.isArray(items)) return [];
  return items.map((item) => ({
    institution: normalizeScalar(item.institution),
    course_name: normalizeScalar(item.course_name),
    year_from: normalizeScalar(item.year_from),
    year_to: normalizeScalar(item.year_to ?? item.year),
    document_type: normalizeScalar(item.document_type),
    document_number: normalizeScalar(item.document_number),
    hours: normalizeScalar(item.hours),
    hours_is_manual: item.hours_is_manual ? "true" : "false",
  }));
}

function normalizeAdditionalBlock(
  block: IntakeAdditionalPayload | undefined,
): CanonicalIntakeDraftPayload["additional"] {
  const source = block ?? emptyIntakeAdditionalDefaults();
  return {
    foreign_languages: normalizeListItems(source.foreign_languages),
    foreign_languages_none: source.foreign_languages_none ? "true" : "false",
    awards: normalizeListItems(source.awards),
    awards_none: source.awards_none ? "true" : "false",
    academic_degrees: normalizeListItems(source.academic_degrees),
    academic_degrees_none: source.academic_degrees_none ? "true" : "false",
    academic_titles: normalizeListItems(source.academic_titles),
    academic_titles_none: source.academic_titles_none ? "true" : "false",
  };
}

function emptyIntakeAdditionalDefaults(): IntakeAdditionalPayload {
  return {
    foreign_languages: [],
    foreign_languages_none: false,
    awards: [],
    awards_none: false,
    academic_degrees: [],
    academic_degrees_none: false,
    academic_titles: [],
    academic_titles_none: false,
  };
}

function normalizeListItems<T extends Record<string, string>>(
  items: T[] | undefined,
): Array<StringRecord<T>> {
  if (!Array.isArray(items)) return [];
  return items
    .filter((item): item is T => typeof item === "object" && item != null)
    .map((item) => {
      const normalized: StringRecord<T> = { ...item };
      for (const key in item) {
        if (!Object.prototype.hasOwnProperty.call(item, key)) continue;
        normalized[key] = normalizeScalar(item[key] ?? "");
      }
      return normalized;
    });
}

export function canonicalizeIntakePayloadForCompare(
  payload: IntakeDraftPayload,
): CanonicalIntakeDraftPayload {
  return {
    personal: normalizeDict(
      {
        last_name: "",
        first_name: "",
        middle_name: "",
        birth_date: "",
        birth_place: "",
        gender: "",
        citizenship: "",
        nationality: "",
        personnel_number: "",
        photo_file_id: "",
      },
      payload.personal,
    ),
    contacts: normalizeDict(
      {
        mobile_phone: "",
        email: "",
        registration_address: "",
        residence_address: "",
      },
      payload.contacts,
    ),
    education: normalizeListItems(payload.education),
    training: normalizeTrainingItems(payload.training),
    relatives: normalizeListItems(payload.relatives),
    employment_biography: normalizeListItems(payload.employment_biography),
    military: normalizeDict(
      {
        status: "",
        rank: "",
        category: "",
        composition: "",
        specialty_code: "",
        specialty_name: "",
        fitness_category: "",
        commissariat: "",
        registration_group: "",
        registration_category: "",
      },
      payload.military,
    ),
    additional: normalizeAdditionalBlock(payload.additional),
    current_step: payload.current_step,
  };
}

export function intakePayloadsEqual(left: IntakeDraftPayload, right: IntakeDraftPayload): boolean {
  const normalizedLeft = canonicalizeIntakePayloadForCompare(left);
  const normalizedRight = canonicalizeIntakePayloadForCompare(right);
  const { current_step: _leftStep, ...leftBody } = normalizedLeft;
  const { current_step: _rightStep, ...rightBody } = normalizedRight;
  return JSON.stringify(leftBody) === JSON.stringify(rightBody);
}
