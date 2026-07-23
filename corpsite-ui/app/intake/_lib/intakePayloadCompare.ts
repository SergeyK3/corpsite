import type { IntakeDraftPayload } from "./intakeApi.client";

function normalizeScalar(value: unknown): string {
  if (value == null) return "";
  return String(value);
}

function normalizeDict(
  template: Record<string, string>,
  overlay: Record<string, string> | undefined,
): Record<string, string> {
  const source = overlay ?? {};
  return Object.fromEntries(
    Object.keys(template).map((key) => [key, normalizeScalar(source[key] ?? template[key] ?? "")]),
  );
}

function normalizeListItems(items: unknown): Array<Record<string, string>> {
  if (!Array.isArray(items)) return [];
  return items
    .filter((item): item is Record<string, string> => typeof item === "object" && item != null)
    .map((item) =>
      Object.fromEntries(Object.entries(item).map(([key, value]) => [key, normalizeScalar(value)])),
    );
}

export function canonicalizeIntakePayloadForCompare(payload: IntakeDraftPayload): IntakeDraftPayload {
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
    education: normalizeListItems(payload.education) as IntakeDraftPayload["education"],
    training: normalizeListItems(payload.training) as IntakeDraftPayload["training"],
    relatives: normalizeListItems(payload.relatives) as IntakeDraftPayload["relatives"],
    employment_biography: normalizeListItems(
      payload.employment_biography,
    ) as IntakeDraftPayload["employment_biography"],
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
