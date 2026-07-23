import type { IntakeDraftPayload, IntakeEducation } from "./intakeApi.client";

type StringRecord<T> = { [K in keyof T]: string };

export type CanonicalIntakeDraftPayload = {
  personal: StringRecord<IntakeDraftPayload["personal"]>;
  contacts: StringRecord<IntakeDraftPayload["contacts"]>;
  education: StringRecord<IntakeEducation>[];
  training: StringRecord<IntakeDraftPayload["training"][number]>[];
  relatives: StringRecord<IntakeDraftPayload["relatives"][number]>[];
  employment_biography: StringRecord<IntakeDraftPayload["employment_biography"][number]>[];
  military: StringRecord<IntakeDraftPayload["military"]>;
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
    training: normalizeListItems(payload.training),
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
