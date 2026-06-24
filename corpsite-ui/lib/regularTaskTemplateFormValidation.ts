import { parseScheduleParamsText, validateScheduleParams } from "./regularTaskScheduleParams";

export type TemplateFormValidationValues = {
  title: string;
  owner_unit_id: string;
  schedule_type: string;
  schedule_params: string;
};

function toNullableInt(text: string): number | null {
  const trimmed = String(text ?? "").trim();
  if (!trimmed) return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value)) return null;
  return Math.trunc(value);
}

export function validateTemplateFormValues(values: TemplateFormValidationValues): string | null {
  if (!String(values.title ?? "").trim()) {
    return "Название обязательно.";
  }

  const parsed = parseScheduleParamsText(values.schedule_params);
  if (parsed.error) return parsed.error;

  const ownerUnitId = toNullableInt(values.owner_unit_id);
  if (ownerUnitId == null || ownerUnitId <= 0) {
    return "Укажите отделение (положительный числовой ID).";
  }

  return validateScheduleParams(String(values.schedule_type ?? ""), parsed.value);
}
