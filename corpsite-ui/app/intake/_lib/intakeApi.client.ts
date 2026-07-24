import { readJsonSafe, toApiError } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";
import { resolveApiUrl } from "@/lib/apiBase";

export type IntakeEducationType = "basic" | "internship" | "residency" | "masters" | "phd";

export type IntakeEducationDocumentType = "diploma" | "certificate";

export type IntakeEducation = {
  education_type: IntakeEducationType;
  institution: string;
  year_from: string;
  year_to: string;
  specialty: string;
  qualification: string;
  document_type: IntakeEducationDocumentType;
  diploma_number: string;
};

export const INTAKE_EDUCATION_DOCUMENT_TYPE_OPTIONS: ReadonlyArray<{
  value: IntakeEducationDocumentType;
  label: string;
}> = [
  { value: "diploma", label: "Диплом" },
  { value: "certificate", label: "Сертификат" },
];

export type IntakeTrainingDocumentType = "certificate" | "witness";

export type IntakeTraining = {
  institution: string;
  course_name: string;
  year_from: string;
  year_to: string;
  document_type: IntakeTrainingDocumentType;
  document_number: string;
  hours: string;
  hours_is_manual: boolean;
  /** Legacy single end-date field kept for backward-compatible reads. */
  year?: string;
};

export const INTAKE_TRAINING_DOCUMENT_TYPE_OPTIONS: ReadonlyArray<{
  value: IntakeTrainingDocumentType;
  label: string;
}> = [
  { value: "certificate", label: "Сертификат" },
  { value: "witness", label: "Свидетельство" },
];

/** Import profile contract exposes degrees.records — safe to collect in intake additional step. */
export const INTAKE_SUPPORTS_ACADEMIC_DEGREES = true;

/** No driver_license field exists in import/PPR contracts yet. */
export const INTAKE_SUPPORTS_DRIVER_LICENSE = false;

export type IntakeForeignLanguage = {
  language: string;
  proficiency: string;
};

/** Aligns with import profile award_records core fields plus issued_by/document_number. */
export type IntakeAward = {
  category: string;
  name: string;
  issued_by: string;
  awarded_at: string;
  document_number: string;
  /** Legacy merged value — migrated to category/name on read. */
  title?: string;
};

/** Degree-only academic record. */
export type IntakeAcademicDegree = {
  degree: string;
  degree_other: string;
  field_of_science: string;
  completed_at: string;
  document_number: string;
  /** Legacy combined label — migrated on read. */
  label?: string;
  /** Legacy free-form type — migrated to field_of_science when structured fields empty. */
  degree_type?: string;
};

/** Title-only academic record. */
export type IntakeAcademicTitle = {
  academic_title: string;
  academic_title_other: string;
  field_of_science: string;
  completed_at: string;
  document_number: string;
  label?: string;
  degree_type?: string;
};

export type IntakeAdditionalPayload = {
  foreign_languages: IntakeForeignLanguage[];
  foreign_languages_none: boolean;
  awards: IntakeAward[];
  awards_none: boolean;
  academic_degrees: IntakeAcademicDegree[];
  academic_degrees_none: boolean;
  academic_titles: IntakeAcademicTitle[];
  academic_titles_none: boolean;
};

export const INTAKE_EDUCATION_TYPE_OPTIONS: ReadonlyArray<{
  value: IntakeEducationType;
  label: string;
}> = [
  { value: "basic", label: "Базовое образование" },
  { value: "internship", label: "Интернатура" },
  { value: "residency", label: "Резидентура" },
  { value: "masters", label: "Магистратура" },
  { value: "phd", label: "Докторантура" },
];

export type IntakeDraftPayload = {
  personal: {
    last_name: string;
    first_name: string;
    middle_name: string;
    birth_date: string;
    birth_place: string;
    gender: string;
    citizenship: string;
    nationality: string;
    /** Assigned by HR; hidden in public intake until set. */
    personnel_number: string;
    /** Server-side photo file id; empty when no photo uploaded. */
    photo_file_id: string;
  };
  contacts: {
    mobile_phone: string;
    email: string;
    registration_address: string;
    residence_address: string;
  };
  education: IntakeEducation[];
  training: IntakeTraining[];
  relatives: Array<{
    relationship: string;
    full_name: string;
    birth_year: string;
    work_place: string;
  }>;
  employment_biography: Array<{
    organization: string;
    position: string;
    year_from: string;
    year_to: string;
    reason_for_leaving: string;
  }>;
  military: {
    status: string;
    rank: string;
    category: string;
    composition: string;
    specialty_code: string;
    specialty_name: string;
    fitness_category: string;
    commissariat: string;
    registration_group: string;
    registration_category: string;
  };
  additional: IntakeAdditionalPayload;
  current_step: string;
};

export type IntakeSessionResponse = {
  application_id: number;
  draft_id: number;
  link_id: number;
  status: string;
  payload: IntakeDraftPayload;
  read_only: boolean;
  link_status: string;
  opened_at?: string | null;
  submitted_at?: string | null;
  expires_at?: string | null;
};

export type IntakeAutosaveResponse = {
  draft_id: number;
  status: string;
  payload: IntakeDraftPayload;
  saved_at: string;
};

export type IntakeSubmitResponse = {
  application_id: number;
  draft_id: number;
  status: string;
  submitted_at: string;
};

export type IntakeLinkIssueResponse = {
  application_id: number;
  link_id: number;
  intake_url_path: string;
  expires_at: string;
  status: string;
  reissued: boolean;
};

export type IntakeSummaryResponse = {
  application_id: number;
  link_status: string | null;
  draft_status: string | null;
  link_id: number | null;
  issued_at: string | null;
  expires_at: string | null;
  opened_at: string | null;
  submitted_at: string | null;
  revoked_at: string | null;
  intake_url_path: string | null;
};

export const INTAKE_STEPS = [
  { id: "personal", title: "Персональные данные" },
  { id: "contacts", title: "Контакты" },
  { id: "education", title: "Образование" },
  { id: "training", title: "Обучение" },
  { id: "relatives", title: "Родственники" },
  { id: "employment_biography", title: "Трудовая биография" },
  { id: "military", title: "Воинский учёт" },
  { id: "additional", title: "Дополнительные сведения" },
  { id: "review", title: "Проверка" },
] as const;

export const INTAKE_ON_BEHALF_INITIAL_STEP_ID = "employment_biography";

export function formatIntakeStepHeaderTitle(stepIndex: number): string {
  const safeIndex = Math.min(Math.max(stepIndex, 0), INTAKE_STEPS.length - 1);
  const step = INTAKE_STEPS[safeIndex];
  return `Анкета претендента · шаг ${safeIndex + 1} из ${INTAKE_STEPS.length} — ${step.title}`;
}

/** HR on-behalf edit opens on employment biography, not the applicant's saved step. */
export function resolveIntakeOnBehalfInitialStepIndex(): number {
  const preferredIndex = INTAKE_STEPS.findIndex((step) => step.id === INTAKE_ON_BEHALF_INITIAL_STEP_ID);
  if (preferredIndex >= 0) return preferredIndex;
  const firstEditableIndex = INTAKE_STEPS.findIndex((step) => step.id !== "review");
  return firstEditableIndex >= 0 ? firstEditableIndex : 0;
}

export function emptyIntakeDraftPayload(): IntakeDraftPayload {
  return {
    personal: {
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
    contacts: {
      mobile_phone: "",
      email: "",
      registration_address: "",
      residence_address: "",
    },
    education: [],
    training: [],
    relatives: [],
    employment_biography: [],
    military: {
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
    additional: {
      foreign_languages: [],
      foreign_languages_none: false,
      awards: [],
      awards_none: false,
      academic_degrees: [],
      academic_degrees_none: false,
      academic_titles: [],
      academic_titles_none: false,
    },
    current_step: "personal",
  };
}

export function mapIntakeApiError(error: unknown, fallback: string): string {
  return formatThrownError(error, { fallback });
}

function publicHeaders(json = false): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

export async function openIntakeSession(token: string): Promise<IntakeSessionResponse> {
  const path = `/intake/${encodeURIComponent(token)}`;
  const res = await fetch(resolveApiUrl(path), {
    method: "GET",
    headers: publicHeaders(),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "GET", url: path });
  return body as IntakeSessionResponse;
}

export async function autosaveIntakeDraft(
  token: string,
  payload: IntakeDraftPayload,
): Promise<IntakeAutosaveResponse> {
  const path = `/intake/${encodeURIComponent(token)}`;
  const res = await fetch(resolveApiUrl(path), {
    method: "PATCH",
    headers: publicHeaders(true),
    body: JSON.stringify({ payload }),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "PATCH", url: path });
  return body as IntakeAutosaveResponse;
}

export async function submitIntakeDraft(
  token: string,
  payload?: IntakeDraftPayload,
): Promise<IntakeSubmitResponse> {
  const path = `/intake/${encodeURIComponent(token)}/submit`;
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: publicHeaders(true),
    body: JSON.stringify({ payload: payload ?? null }),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: path });
  return body as IntakeSubmitResponse;
}
