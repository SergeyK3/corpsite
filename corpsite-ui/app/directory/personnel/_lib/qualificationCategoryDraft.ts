/** Sample-data contract for the saved QUALIFICATION_CATEGORY draft preview. */
import type { MedicalSpecialtySnapshot } from "../_components/PersonnelOrderMedicalSpecialtyPicker";
import { formatPersonnelOrderActionStartDate } from "./personnelOrderPrintFormat";

export const CATEGORY_LEVELS = {
  highest: { ru: "высшая", render_ru: "высшей", kk: "жоғары" },
  first: { ru: "первая", render_ru: "первой", kk: "бірінші" },
  second: { ru: "вторая", render_ru: "второй", kk: "екінші" },
} as const;
export type CategoryLevel = keyof typeof CATEGORY_LEVELS;
export const LOCAL_CATEGORY_DRAFT_KEY = "corpsite:local:qualification-category-draft:v2";

export type QualificationCategoryDraft = {
  contract?: "medical-qualification-category-v2";
  effective_date?: string;
  employee_id: number | null;
  source_employee_name: string;
  document_forms_ru: { employee_full_name_genitive_ru: string; position_document_genitive_ru: string };
  document_forms_kk: { employee_full_name_genitive_kk: string; position_document_possessive_kk: string };
  document_org_unit: { unit_id: number | null; name: string; name_kk: string; document_genitive_ru: string; document_genitive_kk: string };
  medical_specialty: MedicalSpecialtySnapshot | null;
  /** New namespace; category and assigned_at reuse PPR field semantics. */
  qualification_category: {
    code?: number | null;
    name_ru?: string;
    name_kk?: string;
    category: CategoryLevel | "";
    assigned_at: string;
    category_code_ru: string;
    category_code_kk: string;
    category_code_source: string;
  };
};

/** Active order form; old snapshots remain readable without rewriting orders. */
export function emptyCategoryOrderDraft(): QualificationCategoryDraft {
  return { ...emptyCategoryDraft(), contract: "medical-qualification-category-v2", effective_date: "" };
}

export function categoryOrderPayload(draft: QualificationCategoryDraft) {
  const c = draft.qualification_category;
  return { ...draft, contract: "medical-qualification-category-v2", qualification_category: {
    code: c.code ?? null, name_ru: c.name_ru || "", name_kk: c.name_kk || "", assigned_at: c.assigned_at,
  } };
}

export function categoryOrderDraftFromRecord(source: Partial<QualificationCategoryDraft>, effectiveDate = ""): QualificationCategoryDraft {
  const empty = emptyCategoryOrderDraft();
  const c = { ...empty.qualification_category, ...source.qualification_category };
  const code = c.code ?? ({ second: 2, first: 3, highest: 4 } as Record<string, number>)[c.category] ?? null;
  return { ...empty, ...source, contract: "medical-qualification-category-v2",
    effective_date: source.effective_date || effectiveDate,
    qualification_category: { ...c, code } };
}

export const CATEGORY_DRAFT_TEXTS = {
  "title_ru": "Об изменении квалификационной категории",
  "title_kk": "Біліктілік санатын өзгерту туралы",
  "body_template_ru": "С {{effective_date.ru}} категория {{position.document_genitive_ru}} («{{medical_specialty.name_ru}}») {{org_unit.document_genitive_ru}} {{employee.full_name_genitive_ru}} будет считаться {{qualification_category.category_code_ru}} „{{qualification_category.level_ru}}“ до {{qualification_category.valid_until_ru}}.",
  "body_template_kk": "{{effective_date.kk}} бастап {{org_unit.document_genitive_kk}} {{position.document_possessive_kk}} («{{medical_specialty.name_kk}}») {{employee.full_name_genitive_kk}} санаты {{qualification_category.category_code_kk}} „{{qualification_category.level_kk}}“ {{qualification_category.valid_until_kk}} дейін болып есептелсін."
} as const;

export function emptyCategoryDraft(): QualificationCategoryDraft {
  return { employee_id: null, source_employee_name: "", document_forms_ru: { employee_full_name_genitive_ru: "", position_document_genitive_ru: "" },
    document_forms_kk: { employee_full_name_genitive_kk: "", position_document_possessive_kk: "" },
    document_org_unit: { unit_id: null, name: "", name_kk: "", document_genitive_ru: "", document_genitive_kk: "" }, medical_specialty: null,
    qualification_category: { category: "", assigned_at: "", category_code_ru: "", category_code_kk: "", category_code_source: "" } };
}

function isoDate(value: string): Date {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error("Укажите полную дату присвоения.");
  const result = new Date(value + "T00:00:00Z");
  if (!Number.isFinite(result.getTime()) || result.toISOString().slice(0, 10) !== value || result.getUTCFullYear() < 1900 || result.getUTCFullYear() > 9994)
    throw new Error("Некорректная дата присвоения.");
  return result;
}

/** Calendar addition clamps 29 February to 28 February, then subtracts a day. */
export function categoryValidUntil(assignedAt: string): string {
  const source = isoDate(assignedAt), year = source.getUTCFullYear() + 5, month = source.getUTCMonth();
  const lastDay = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const end = new Date(Date.UTC(year, month, Math.min(source.getUTCDate(), lastDay)));
  end.setUTCDate(end.getUTCDate() - 1);
  return end.toISOString().slice(0, 10);
}
const KK_MONTHS = ["қаңтарға", "ақпанға", "наурызға", "сәуірге", "мамырға", "маусымға", "шілдеге", "тамызға", "қыркүйекке", "қазанға", "қарашаға", "желтоқсанға"];
function numericDate(value: string) { return value.split("-").reverse().join("."); }
function kazakhDate(value: string) {
  const d = isoDate(value), month = d.getUTCMonth();
  return `${d.getUTCFullYear()} жылғы ${d.getUTCDate()} ${KK_MONTHS[month]}`;
}

export function categoryDraftErrors(d: QualificationCategoryDraft): string[] {
  const errors: string[] = [], c = d.qualification_category;
  const classifier = d.contract === "medical-qualification-category-v2";
  for (const [value, label] of [[d.document_forms_ru.employee_full_name_genitive_ru,"ФИО в родительном падеже RU"],
    [d.document_forms_kk.employee_full_name_genitive_kk,"ФИО в ілік септік KK"], [d.document_org_unit.document_genitive_kk,"Подразделение в ілік септік KK"],
    [d.document_forms_ru.position_document_genitive_ru,"Должность в родительном падеже RU"],
    [d.document_forms_kk.position_document_possessive_kk,"Должность в тексте KK"],
    [d.document_org_unit.document_genitive_ru,"Подразделение в родительном падеже RU"],
    ...(!classifier ? [[d.source_employee_name,"ФИО"], [d.document_org_unit.name,"Подразделение RU"], [d.document_org_unit.name_kk,"Подразделение KK"], [c.category_code_ru,"Код категории RU"], [c.category_code_kk,"Код категории KK"], [c.category_code_source,"Источник кода (сертификат)"]] : [])])
    if (!value.trim()) errors.push(`Заполните: ${label}.`);
  if (!Number.isSafeInteger(d.employee_id) || Number(d.employee_id) < 1) errors.push("Выберите сотрудника.");
  if (classifier ? ![2,3,4].includes(c.code ?? 0) || !c.name_ru?.trim() || !c.name_kk?.trim() : !Object.prototype.hasOwnProperty.call(CATEGORY_LEVELS, c.category)) errors.push("Выберите высшую, первую или вторую категорию из справочника.");
  const s = d.medical_specialty;
  if ((!classifier || s != null) && (!s || !Number.isSafeInteger(s.medical_specialty_id) || s.medical_specialty_id < 1 || !s.name_ru.trim() || !s.name_kk.trim()))
    errors.push("Выберите медицинскую специальность с названиями RU и KK из справочника.");
  try { categoryValidUntil(c.assigned_at); } catch (error) { errors.push((error as Error).message); }
  if (classifier) try { isoDate(d.effective_date || ""); } catch { errors.push("Укажите дату начала действия категории."); }
  return errors;
}

export function generateCategoryDraft(d: QualificationCategoryDraft, texts: typeof CATEGORY_DRAFT_TEXTS = CATEGORY_DRAFT_TEXTS) {
  const errors = categoryDraftErrors(d); if (errors.length) throw new Error(errors.join("\n"));
  const c = d.qualification_category, level = CATEGORY_LEVELS[c.category as CategoryLevel], end = categoryValidUntil(c.assigned_at);
  const variables: Record<string, string> = {
    "employee.full_name": d.source_employee_name,
    "employee.full_name_genitive_ru": d.document_forms_ru.employee_full_name_genitive_ru,
    "employee.full_name_genitive_kk": d.document_forms_kk.employee_full_name_genitive_kk,
    "position.document_genitive_ru": d.document_forms_ru.position_document_genitive_ru,
    "position.document_possessive_kk": d.document_forms_kk.position_document_possessive_kk,
    "org_unit.document_genitive_ru": d.document_org_unit.document_genitive_ru,
    "org_unit.title_ru": d.document_org_unit.name, "org_unit.title_kk": d.document_org_unit.name_kk,
    "org_unit.document_genitive_kk": d.document_org_unit.document_genitive_kk,
    "medical_specialty.name_ru": d.medical_specialty!.name_ru, "medical_specialty.name_kk": d.medical_specialty!.name_kk,
    "effective_date.ru": numericDate(c.assigned_at), "effective_date.kk": formatPersonnelOrderActionStartDate(c.assigned_at, "kk"),
    "qualification_category.category": c.category,
    "qualification_category.level_ru": level.render_ru,
    "qualification_category.level_kk": level.kk,
    "qualification_category.category_code_ru": c.category_code_ru, "qualification_category.category_code_kk": c.category_code_kk,
    "qualification_category.valid_until_ru": numericDate(end), "qualification_category.valid_until_kk": kazakhDate(end),
  };
  function render(text: string) {
    return text.replace(/\{\{\s*([\w.]+)\s*\}\}/g, (_, key: string) => {
      if (!(key in variables)) throw new Error(`Неизвестная переменная: ${key}`);
      return variables[key];
    });
  }
  return { variables, valid_until: end, title_ru: texts.title_ru, title_kk: texts.title_kk,
    body_template_ru: render(texts.body_template_ru), body_template_kk: render(texts.body_template_kk) };
}

export function serializeCategoryDraft(draft: QualificationCategoryDraft): string {
  return JSON.stringify({ schema_version: 1, draft, texts: CATEGORY_DRAFT_TEXTS, rendered: generateCategoryDraft(draft) });
}
export function restoreCategoryDraft(raw: string): QualificationCategoryDraft {
  const stored = JSON.parse(raw);
  if (stored.schema_version !== 1 || !stored.draft || !stored.texts) throw new Error("Неизвестный формат локального черновика.");
  // Verify both the saved source texts and computed snapshot; never trust an edited expiry.
  if (JSON.stringify(stored.texts) !== JSON.stringify(CATEGORY_DRAFT_TEXTS) ||
      JSON.stringify(generateCategoryDraft(stored.draft)) !== JSON.stringify(stored.rendered))
    throw new Error("Сохранённые тексты или данные черновика изменены. Требуется проверка.");
  return stored.draft;
}
