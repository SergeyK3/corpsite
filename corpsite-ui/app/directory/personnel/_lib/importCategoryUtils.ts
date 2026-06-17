const MEDICAL_CATEGORY_LABELS: Record<string, string> = {
  highest: "высшая",
  first: "первая",
  second: "вторая",
};

export function formatMedicalCategoryLabel(categoryKey: string | null | undefined): string {
  const key = String(categoryKey ?? "").trim().toLowerCase();
  if (!key || key === "none") return "";
  if (MEDICAL_CATEGORY_LABELS[key]) return MEDICAL_CATEGORY_LABELS[key];

  const text = key;
  if (text.includes("высш")) return "высшая";
  if (text.includes("перва")) return "первая";
  if (text.includes("втор")) return "вторая";
  return "";
}

export const MEDICAL_CATEGORY_FILTER_OPTIONS = [
  { value: "", label: "Все категории" },
  { value: "highest", label: "Высшая" },
  { value: "first", label: "Первая" },
  { value: "second", label: "Вторая" },
  { value: "none", label: "Без категории" },
] as const;
