import type {
  CertificatePortfolioRecord,
  DegreePortfolioRecord,
  EducationPortfolioRecord,
  ImportProfile,
  TrainingPortfolioRecord,
} from "./importApi.client";

export const CATEGORY_OPTIONS = [
  "Высшая",
  "Первая",
  "Вторая",
  "Сертификат специалиста",
  "Без категории",
  "Другое",
] as const;

const YEAR_RE = /^\d{4}$/;
const DATE_RE = /^(\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})$/i;
const YEAR_IN_TEXT_RE = /\b(19|20)\d{2}\b/;
const YEAR_ONLY_DATE_RE = /^01\.01\.\d{4}$/;

export function yearToDefaultDate(year: string): string {
  return `01.01.${year}`;
}

/** True when the date is the default 01.01.YYYY placeholder (exact day/month unknown). */
export function isYearOnlyDate(value: string): boolean {
  return YEAR_ONLY_DATE_RE.test((value || "").trim());
}

export function normalizeDateInput(value: string): string {
  const text = (value || "").trim();
  if (!text) return "";
  if (text.toLowerCase() === "постоянно") return text;
  if (YEAR_RE.test(text)) return yearToDefaultDate(text);
  if (DATE_RE.test(text)) return text;
  const match = text.match(YEAR_IN_TEXT_RE);
  return match ? yearToDefaultDate(match[0]) : text;
}

export function getDegreeRecords(degrees: ImportProfile["degrees"]): DegreePortfolioRecord[] {
  const records = degrees?.records ?? [];
  if (records.length > 0) {
    return records.map((row) => ({
      ...row,
      label: String(row.label ?? row.source_text ?? ""),
      completed_at: String(row.completed_at ?? ""),
    }));
  }
  const raw = (degrees?.raw_text ?? "").trim();
  if (!raw) return [];
  return [
    {
      label: raw,
      completed_at: "",
      degree_type: /кандидат\s+мед/i.test(raw)
        ? "candidate_medical_sciences"
        : /доктор\s+мед/i.test(raw)
          ? "doctor_medical_sciences"
          : undefined,
      source_field: "degree_raw",
      source_text: raw,
      confidence: 1,
      parse_method: "regex_v1",
      document_id: null,
    },
  ];
}

export function buildDegreesState(records: DegreePortfolioRecord[]): ImportProfile["degrees"] {
  const labels = records.map((row) => (row.label || "").trim()).filter(Boolean);
  const raw_text = labels.join("; ");
  return {
    candidate_medical_sciences: records.some((row) => /кандидат\s+мед/i.test(row.label || "")),
    doctor_medical_sciences: records.some((row) => /доктор\s+мед/i.test(row.label || "")),
    raw_text,
    records,
  };
}

export function normalizeEditableProfile(profile: ImportProfile): ImportProfile {
  const education = { ...(profile.education ?? {}) };
  let educationRecords = Array.isArray(profile.education_records) ? [...profile.education_records] : [];
  if (!educationRecords.length && Array.isArray(education.basic)) {
    educationRecords = [...education.basic];
  }
  educationRecords = educationRecords.map((row) => ({
    ...row,
    completed_at: normalizeDateInput(String(row.completed_at ?? "")),
  }));
  if (Array.isArray(education.basic)) {
    education.basic = education.basic.map((row) => ({
      ...row,
      completed_at: normalizeDateInput(String(row.completed_at ?? "")),
    }));
  }
  return {
    ...profile,
    education,
    education_records: educationRecords,
    training_records: (profile.training_records ?? []).map((row) => ({
      ...row,
      completed_at: normalizeDateInput(String(row.completed_at ?? "")),
    })),
    category_records: (profile.category_records ?? []).map((row) => ({
      ...row,
      issued_at: normalizeDateInput(String(row.issued_at ?? "")),
    })),
    certificate_records: (profile.certificate_records ?? []).map((row) => ({
      ...row,
      issued_at: normalizeDateInput(String(row.issued_at ?? "")),
    })),
    award_records: (profile.award_records ?? []).map((row) => ({
      ...row,
      date: normalizeDateInput(String(row.date ?? "")),
    })),
    degrees: buildDegreesState(
      getDegreeRecords(profile.degrees ?? {
        candidate_medical_sciences: false,
        doctor_medical_sciences: false,
        raw_text: "",
        records: [],
      }).map((row) => ({
        ...row,
        completed_at: normalizeDateInput(String(row.completed_at ?? "")),
      }))
    ),
  };
}

export function extractYearFromText(text: string): string | null {
  const match = (text || "").match(YEAR_IN_TEXT_RE);
  return match ? match[0] : null;
}

export function stripYearFromText(text: string): string {
  return (text || "")
    .replace(YEAR_IN_TEXT_RE, "")
    .replace(/\s*[,;.-]\s*$/, "")
    .replace(/^\s*[,;.-]\s*/, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

export function extractEditableSectionsOverride(profile: ImportProfile): Record<string, unknown> {
  const educationRecords = getProfessionalEducationRecords(profile);
  return {
    education: educationRecords.map((row) => ({
      institution: row.institution || "",
      specialty: row.specialty || "",
      date: normalizeDateInput(String(row.completed_at ?? "")),
      record_type: row.record_type || "basic",
    })),
    training: (profile.training_records ?? []).map((row) => ({
      title: row.title || "",
      organization: row.organization || "",
      date: normalizeDateInput(String(row.completed_at ?? "")),
      hours: row.hours ?? null,
    })),
    categories: (profile.category_records ?? []).map((row) => ({
      category: categoryDisplayLabel(String(row.category ?? "")),
      date: normalizeDateInput(String(row.issued_at ?? "")),
      specialty: row.specialty || "",
    })),
    certificates: (profile.certificate_records ?? []).map((row) => ({
      kind: row.kind || "",
      topic: row.topic || row.specialty || "",
      date: normalizeDateInput(String(row.issued_at ?? "")),
      hours: row.hours ?? null,
      link: row.link || "",
    })),
    degree: getDegreeRecords(profile.degrees ?? {
      candidate_medical_sciences: false,
      doctor_medical_sciences: false,
      raw_text: "",
      records: [],
    }).map((row) => ({
      label: row.label || "",
      date: normalizeDateInput(String(row.completed_at ?? "")),
    })),
    awards: (profile.award_records ?? []).map((row) => ({
      title: row.title || "",
      date: normalizeDateInput(String(row.date ?? "")),
    })),
    notes: profile.notes_raw || "",
  };
}

const CATEGORY_CODE_LABELS: Record<string, string> = {
  highest: "Высшая",
  first: "Первая",
  second: "Вторая",
  specialist_certificate: "Сертификат специалиста",
  certificate: "Сертификат специалиста",
  none: "Без категории",
  other: "Другое",
};

export function categoryDisplayLabel(value: string): string {
  const text = (value || "").trim();
  if (!text) return "";
  const lowered = text.toLowerCase();
  return CATEGORY_CODE_LABELS[lowered] ?? text;
}

export function validateDate(value: string): string | null {
  const text = value.trim();
  if (!text) return null;
  if (text.toLowerCase() === "постоянно") return null;
  if (DATE_RE.test(text) || isYearOnlyDate(text)) return null;
  return "Дата: YYYY-MM-DD, DD.MM.YYYY или «постоянно»";
}

export function validateHours(value: string): string | null {
  const text = value.trim();
  if (!text) return null;
  return Number.isFinite(Number(text)) ? null : "Часы: число или пусто";
}

export function validateUrl(value: string): string | null {
  const text = value.trim();
  if (!text) return null;
  try {
    const url = new URL(text);
    return url.protocol === "http:" || url.protocol === "https:" ? null : "Ссылка: URL или пусто";
  } catch {
    return "Ссылка: URL или пусто";
  }
}

export function validateEditableProfile(profile: ImportProfile): string[] {
  const errors: string[] = [];
  const educationRecords = getProfessionalEducationRecords(profile);
  for (const [idx, row] of educationRecords.entries()) {
    const dateErr = validateDate(String(row.completed_at ?? ""));
    if (dateErr) errors.push(`Учебное заведение, строка ${idx + 1}: ${dateErr}`);
  }
  for (const [idx, row] of (profile.training_records ?? []).entries()) {
    const dateErr = validateDate(String(row.completed_at ?? ""));
    if (dateErr) errors.push(`Повышение квалификации, строка ${idx + 1}: ${dateErr}`);
    const hoursErr = validateHours(row.hours != null ? String(row.hours) : "");
    if (hoursErr) errors.push(`Повышение квалификации, строка ${idx + 1}: ${hoursErr}`);
  }
  for (const [idx, row] of (profile.category_records ?? []).entries()) {
    const dateErr = validateDate(String(row.issued_at ?? ""));
    if (dateErr) errors.push(`Категория, строка ${idx + 1}: ${dateErr}`);
  }
  for (const [idx, row] of (profile.certificate_records ?? []).entries()) {
    const dateErr = validateDate(String(row.issued_at ?? ""));
    if (dateErr) errors.push(`Сертификат, строка ${idx + 1}: ${dateErr}`);
    const hoursErr = validateHours(row.hours != null ? String(row.hours) : "");
    if (hoursErr) errors.push(`Сертификат, строка ${idx + 1}: ${hoursErr}`);
    const urlErr = validateUrl(String(row.link ?? ""));
    if (urlErr) errors.push(`Сертификат, строка ${idx + 1}: ${urlErr}`);
  }
  for (const [idx, row] of getDegreeRecords(profile.degrees ?? {
    candidate_medical_sciences: false,
    doctor_medical_sciences: false,
    raw_text: "",
    records: [],
  }).entries()) {
    const dateErr = validateDate(String(row.completed_at ?? ""));
    if (dateErr) errors.push(`Степень, строка ${idx + 1}: ${dateErr}`);
  }
  for (const [idx, row] of (profile.award_records ?? []).entries()) {
    const dateErr = validateDate(String(row.date ?? ""));
    if (dateErr) errors.push(`Награда, строка ${idx + 1}: ${dateErr}`);
  }
  return errors;
}

export function splitEducationRow(rows: EducationPortfolioRecord[], index: number): EducationPortfolioRecord[] {
  const source = rows[index];
  if (!source) return rows;
  const copy: EducationPortfolioRecord = {
    ...source,
    institution: "",
    specialty: "",
    completed_at: "",
    source_text: source.source_text || "",
  };
  const next = [...rows];
  next.splice(index + 1, 0, copy);
  return next;
}

export function splitCertificateRow(rows: CertificatePortfolioRecord[], index: number): CertificatePortfolioRecord[] {
  const source = rows[index];
  if (!source) return rows;
  const copy: CertificatePortfolioRecord = {
    ...source,
    kind: "",
    topic: "",
    specialty: "",
    issued_at: "",
    hours: null,
    link: "",
    source_text: source.source_text || "",
  };
  const next = [...rows];
  next.splice(index + 1, 0, copy);
  return next;
}

export function splitTrainingRow(rows: TrainingPortfolioRecord[], index: number): TrainingPortfolioRecord[] {
  const source = rows[index];
  if (!source) return rows;
  const copy: TrainingPortfolioRecord = {
    ...source,
    title: "",
    completed_at: "",
    hours: null,
    source_text: source.source_text || "",
  };
  const next = [...rows];
  next.splice(index + 1, 0, copy);
  return next;
}

export function emptyEducationRow(): EducationPortfolioRecord {
  return {
    record_type: "basic",
    institution: "",
    specialty: "",
    completed_at: "",
    source_field: "profile_override",
    source_text: "",
    confidence: 1,
    parse_method: "manual_override",
    document_id: null,
  };
}

export function emptyTrainingRow(): TrainingPortfolioRecord {
  return {
    title: "",
    organization: "",
    hours: null,
    started_at: "",
    completed_at: "",
    source_field: "profile_override",
    source_text: "",
    confidence: 1,
    parse_method: "manual_override",
    document_id: null,
  };
}

export function emptyCategoryRow() {
  return {
    category: "",
    specialty: "",
    issued_at: "",
    source_field: "profile_override",
    source_text: "",
    confidence: 1,
    parse_method: "manual_override",
    document_id: null,
  };
}

export function emptyCertificateRow() {
  return {
    kind: "",
    topic: "",
    specialty: "",
    issued_at: "",
    valid_until: "",
    hours: null,
    link: "",
    certificate_number: "",
    source_field: "profile_override",
    source_text: "",
    confidence: 1,
    parse_method: "manual_override",
    document_id: null,
  };
}

export function splitDegreeRow(rows: DegreePortfolioRecord[], index: number): DegreePortfolioRecord[] {
  const source = rows[index];
  if (!source) return rows;
  const copy: DegreePortfolioRecord = {
    ...source,
    label: "",
    completed_at: "",
    degree_type: undefined,
    source_text: source.source_text || "",
  };
  const next = [...rows];
  next.splice(index + 1, 0, copy);
  return next;
}

export function emptyDegreeRow(): DegreePortfolioRecord {
  return {
    label: "",
    completed_at: "",
    source_field: "profile_override",
    source_text: "",
    confidence: 1,
    parse_method: "manual_override",
    document_id: null,
  };
}

export function emptyAwardRow() {
  return {
    title: "",
    date: "",
    source_field: "profile_override",
    source_text: "",
    confidence: 1,
    parse_method: "manual_override",
    document_id: null,
  };
}

export const EXPERIENCE_CALC_NOTE =
  "Стаж рассчитывается приблизительно по дате окончания первого профессионального учебного заведения на текущую дату";

function parseProfileDate(value: string): Date | null {
  const text = normalizeDateInput(value);
  if (!text || text.toLowerCase() === "постоянно") return null;
  const isoMatch = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (isoMatch) {
    const date = new Date(Number(isoMatch[1]), Number(isoMatch[2]) - 1, Number(isoMatch[3]));
    return Number.isNaN(date.getTime()) ? null : date;
  }
  const dmyMatch = text.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (dmyMatch) {
    const date = new Date(Number(dmyMatch[3]), Number(dmyMatch[2]) - 1, Number(dmyMatch[1]));
    return Number.isNaN(date.getTime()) ? null : date;
  }
  return null;
}

export function getProfessionalEducationRecords(
  profile: Pick<ImportProfile, "education" | "education_records">,
): EducationPortfolioRecord[] {
  const basicFromEducation = profile.education?.basic ?? [];
  if (basicFromEducation.length) {
    return basicFromEducation;
  }
  const records = profile.education_records ?? [];
  return records.filter((row) => (row.record_type || "basic") === "basic");
}

export function calcExperienceYears(from: Date, to: Date = new Date()): number {
  const ms = to.getTime() - from.getTime();
  if (ms < 0) return 0;
  const days = ms / (1000 * 60 * 60 * 24);
  return Math.round((days / 365.25) * 10) / 10;
}

export function formatExperienceYears(years: number): string {
  const normalized = Math.max(0, years);
  const intPart = Math.floor(normalized);
  const decPart = Math.round((normalized - intPart) * 10);
  return `${String(intPart).padStart(2, "0")},${decPart} лет`;
}

export function formatValidityYearsDecimal(years: number): string {
  const normalized = Math.max(0, years);
  const intPart = Math.floor(normalized);
  const decPart = Math.round((normalized - intPart) * 10);
  return `${intPart},${decPart}`;
}

export const RECORD_VALIDITY_TERM_YEARS = 5;

export const RECORD_VALIDITY_EXPIRED_NOTE = "утратила силу";

/** @deprecated use RECORD_VALIDITY_TERM_YEARS */
export const CATEGORY_VALIDITY_TERM_YEARS = RECORD_VALIDITY_TERM_YEARS;

/** @deprecated use RECORD_VALIDITY_EXPIRED_NOTE */
export const CATEGORY_VALIDITY_EXPIRED_NOTE = RECORD_VALIDITY_EXPIRED_NOTE;

export function calcRecordValidityNote(issuedAt: string, to: Date = new Date()): string | null {
  const from = parseProfileDate(normalizeDateInput(issuedAt));
  if (!from) return null;
  const elapsed = calcExperienceYears(from, to);
  if (elapsed > RECORD_VALIDITY_TERM_YEARS) {
    return RECORD_VALIDITY_EXPIRED_NOTE;
  }
  const remaining = Math.max(0, RECORD_VALIDITY_TERM_YEARS - elapsed);
  return `осталось ${formatValidityYearsDecimal(remaining)} лет`;
}

/** @deprecated use calcRecordValidityNote */
export const calcCategoryValidityNote = calcRecordValidityNote;

export function calcExperienceFromEducation(
  profile: Pick<ImportProfile, "education" | "education_records">,
  to: Date = new Date(),
): string | null {
  const dates = getProfessionalEducationRecords(profile)
    .map((row) => parseProfileDate(String(row.completed_at ?? "")))
    .filter((date): date is Date => date !== null);
  if (!dates.length) return null;
  const earliest = dates.reduce((min, date) => (date.getTime() < min.getTime() ? date : min));
  return formatExperienceYears(calcExperienceYears(earliest, to));
}
