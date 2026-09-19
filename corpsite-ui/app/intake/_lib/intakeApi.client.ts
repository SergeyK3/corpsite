import { readJsonSafe, toApiError } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";
import { resolveApiUrl } from "@/lib/apiBase";
import { normalizeIntakeRecordId } from "./intakeRecordId";

export type IntakeEducationType = "basic" | "internship" | "residency" | "masters" | "phd";

export type IntakeEducationDocumentType = "diploma" | "certificate";

export type IntakeEducation = {
  record_id: string;
  /** Canonical v2 names retained alongside controlled-form legacy aliases. */
  start_date: string;
  end_date: string;
  institution_original: string;
  specialty_original: string;
  qualification_original: string;
  document_number: string;
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
  record_id: string;
  start_date: string;
  end_date: string;
  institution_original: string;
  course_name_original: string;
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

export type IntakeRelative = {
  record_id: string;
  relationship: string;
  relationship_other: string;
  full_name: string;
  birth_date: string;
  workplace: string;
  /** Legacy controlled-form aliases. */
  birth_year: string;
  work_place: string;
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
  relatives: IntakeRelative[];
  employment_biography: Array<{
    record_id: string;
    start_date: string | null;
    end_date: string | null;
    organization_original: string;
    organization_normalized: string;
    city: string | null;
    position_original: string;
    position_normalized: string;
    reason_for_leaving: string | null;
    note: string | null;
    verification_status: "unverified" | "requires_review" | "verified" | "rejected";
    evidence_document_ids: string[];
    /** Read-only compatibility aliases. They are removed by the next save. */
    organization?: string;
    position?: string;
    year_from?: string;
    year_to?: string;
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

export const INTAKE_ON_BEHALF_INITIAL_STEP_ID = "personal";

export function formatIntakeStepHeaderTitle(stepIndex: number): string {
  const safeIndex = Math.min(Math.max(stepIndex, 0), INTAKE_STEPS.length - 1);
  const step = INTAKE_STEPS[safeIndex];
  return `Анкета претендента · шаг ${safeIndex + 1} из ${INTAKE_STEPS.length} — ${step.title}`;
}

/** HR on-behalf edit opens on the first intake step, not the applicant's saved step. */
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
  const apiError = error as {
    code?: unknown;
    details?: { detail?: { code?: unknown } };
  };
  const code = String(apiError?.code ?? apiError?.details?.detail?.code ?? "").trim();
  const intakeMessages: Record<string, string> = {
    TOKEN_MISSING: "Ссылка недействительна. Проверьте, что она скопирована полностью.",
    TOKEN_INVALID: "Ссылка недействительна. Проверьте, что она скопирована полностью.",
    TOKEN_EXPIRED: "Срок действия ссылки истёк. Попросите отдел кадров отправить новую ссылку.",
    TOKEN_REVOKED: "Ссылка больше недоступна. Обратитесь в отдел кадров.",
    TOKEN_NOT_ACCESSIBLE: "Ссылка недоступна. Обратитесь в отдел кадров.",
  };
  if (intakeMessages[code]) return intakeMessages[code];
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
  return normalizeIntakeResponsePayload(body as IntakeSessionResponse);
}

export async function autosaveIntakeDraft(
  token: string,
  payload: IntakeDraftPayload,
): Promise<IntakeAutosaveResponse> {
  const path = `/intake/${encodeURIComponent(token)}`;
  const res = await fetch(resolveApiUrl(path), {
    method: "PATCH",
    headers: publicHeaders(true),
    body: JSON.stringify({ payload: toCanonicalIntakeV2(payload) }),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "PATCH", url: path });
  return normalizeIntakeResponsePayload(body as IntakeAutosaveResponse);
}

function normalizeIntakeResponsePayload<T extends { payload: IntakeDraftPayload }>(response: T): T {
  const source = response.payload as unknown as Record<string, unknown>;
  const sourcePersonal = source.personal && typeof source.personal === "object" ? source.personal as Record<string, unknown> : {};
  const sourceContacts = source.contacts && typeof source.contacts === "object" ? source.contacts as Record<string, unknown> : {};
  const sourceMilitary = source.military && typeof source.military === "object" ? source.military as Record<string, unknown> : {};
  // This is the single boundary between persisted canonical JSON and controlled
  // form inputs.  Only nullish textual values become ""; numbers, booleans
  // and arrays retain their types and therefore cannot become the text "null".
  const formText = (value: unknown): unknown => value == null ? "" : value;
  const toFormValue = (value: unknown): unknown => {
    if (value == null) return "";
    if (Array.isArray(value)) return value.map(toFormValue);
    if (typeof value === "object") {
      return Object.fromEntries(Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, toFormValue(item)]));
    }
    return value;
  };
  const formTextFields = (value: Record<string, unknown>, keys: readonly string[]) => Object.fromEntries(
    keys.map((key) => [key, formText(value[key])]),
  );
  const raw: unknown = response.payload?.employment_biography;
  const employment_biography = Array.isArray(raw)
    ? raw.filter((item): item is Record<string, unknown> => !!item && typeof item === "object").map((item, index) => ({
      record_id: String(item.record_id || `legacy-${index}`),
      start_date: nullable(item.start_date ?? item.year_from),
      end_date: nullable(item.end_date ?? item.year_to),
      organization_original: String(item.organization_original ?? item.organization ?? ""),
      organization_normalized: String(item.organization_normalized ?? item.organization_original ?? item.organization ?? ""),
      city: nullable(item.city),
      position_original: String(item.position_original ?? item.position ?? ""),
      position_normalized: String(item.position_normalized ?? item.position_original ?? item.position ?? ""),
      reason_for_leaving: nullable(item.reason_for_leaving),
      note: nullable(item.note),
      verification_status: item.verification_status === "verified" || item.verification_status === "rejected" || item.verification_status === "requires_review" ? item.verification_status : "unverified",
      evidence_document_ids: Array.isArray(item.evidence_document_ids) ? item.evidence_document_ids.map(String) : [],
    }))
    : [];
  const legacyRows = (key: string) => Array.isArray(source[key]) ? source[key] as Record<string, unknown>[] : [];
  const education = legacyRows("education").map((item) => ({ ...item,
    record_id: normalizeIntakeRecordId(item.record_id), start_date: formText(item.start_date ?? item.year_from), end_date: formText(item.end_date ?? item.year_to),
    institution_original: formText(item.institution_original ?? item.institution), specialty_original: formText(item.specialty_original ?? item.specialty), qualification_original: formText(item.qualification_original ?? item.qualification), document_number: formText(item.document_number ?? item.diploma_number),
    institution: item.institution ?? item.institution_original ?? "", specialty: item.specialty ?? item.specialty_original ?? "",
    qualification: item.qualification ?? item.qualification_original ?? "", year_from: item.year_from ?? item.start_date ?? "",
    year_to: item.year_to ?? item.end_date ?? "", diploma_number: item.diploma_number ?? item.document_number ?? "",
  }));
  const training = legacyRows("training").map((item) => ({ ...item,
    record_id: normalizeIntakeRecordId(item.record_id), start_date: formText(item.start_date ?? item.year_from), end_date: formText(item.end_date ?? item.year_to ?? item.year),
    institution_original: formText(item.institution_original ?? item.institution), course_name_original: formText(item.course_name_original ?? item.course_name),
    institution: item.institution ?? item.institution_original ?? "", course_name: item.course_name ?? item.course_name_original ?? "",
    year_from: item.year_from ?? item.start_date ?? "", year_to: item.year_to || item.end_date || item.year || "",
  }));
  const relatives = legacyRows("relatives").map((item) => ({ ...item,
    record_id: normalizeIntakeRecordId(item.record_id), relationship_other: formText(item.relationship_other),
    birth_date: formText(item.birth_date ?? item.birth_year), workplace: formText(item.workplace ?? item.work_place),
    birth_year: formText(item.birth_year ?? item.birth_date), work_place: formText(item.work_place ?? item.workplace),
  }));
  const personal = {
    ...sourcePersonal,
    ...formTextFields(sourcePersonal, ["last_name", "first_name", "middle_name", "birth_date", "birth_place", "gender", "citizenship", "nationality", "photo_file_id"]),
  };
  const contacts = {
    ...sourceContacts,
    ...formTextFields(sourceContacts, ["mobile_phone", "email", "registration_address", "residence_address"]),
  };
  const military = {
    ...sourceMilitary,
    ...formTextFields(sourceMilitary, ["status", "rank", "category", "composition", "commissariat", "specialty_code", "specialty_name", "fitness_category", "registration_group", "registration_category"]),
  };
  return { ...response, payload: toFormValue({ ...response.payload, personal, contacts, military, education, training, relatives, employment_biography }) } as T;
}

/** Convert legacy or persisted v2 payload into safe controlled-input values. */
export function toIntakeFormPayload(payload: IntakeDraftPayload): IntakeDraftPayload {
  return normalizeIntakeResponsePayload({ payload }).payload;
}

function nullable(value: unknown): string | null {
  const text = String(value ?? "").trim();
  return text || null;
}

export async function submitIntakeDraft(
  token: string,
  payload?: IntakeDraftPayload,
): Promise<IntakeSubmitResponse> {
  const path = `/intake/${encodeURIComponent(token)}/submit`;
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    headers: publicHeaders(true),
    body: JSON.stringify({ payload: payload ? toCanonicalIntakeV2(payload) : null }),
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "POST", url: path });
  return body as IntakeSubmitResponse;
}

/** Convert the UI's legacy-compatible view model to the persisted v2 contract. */
export function toCanonicalIntakeV2(payload: IntakeDraftPayload): Record<string, unknown> {
  const additional = payload.additional;
  for (const key of ["foreign_languages", "awards", "academic_degrees", "academic_titles"] as const) {
    if (additional[`${key}_none`] && additional[key].length) {
      throw new Error(`Нельзя указать «нет сведений», пока заполнен раздел ${key}`);
    }
  }
  return {
    ...payload, schema_version: 2,
    personal: { ...payload.personal, personnel_number: undefined, photo_file_id: nullable(payload.personal.photo_file_id) },
    contacts: { email: nullable(payload.contacts.email), mobile_phone: nullable(payload.contacts.mobile_phone), residence_address: nullable(payload.contacts.residence_address), registration_address: nullable(payload.contacts.registration_address) },
    education: payload.education.map((item) => ({ record_id: item.record_id, start_date: nullable(item.start_date || item.year_from), end_date: nullable(item.end_date || item.year_to), institution_original: nullable(item.institution_original || item.institution), education_type: item.education_type, document_type: item.document_type, document_number: nullable(item.document_number || item.diploma_number), specialty_original: nullable(item.specialty_original || item.specialty), qualification_original: nullable(item.qualification_original || item.qualification) })),
    training: payload.training.map((item) => ({ record_id: item.record_id, start_date: nullable(item.start_date || item.year_from), end_date: nullable(item.end_date || item.year_to || item.year), course_name_original: nullable(item.course_name_original || item.course_name), institution_original: nullable(item.institution_original || item.institution), document_type: item.document_type, document_number: nullable(item.document_number), hours: item.hours === "" ? null : Number(item.hours), hours_is_manual: item.hours_is_manual })),
    relatives: payload.relatives.map((item) => ({ record_id: item.record_id, relationship: item.relationship, relationship_other: nullable(item.relationship_other), full_name: nullable(item.full_name), birth_date: nullable(item.birth_date || item.birth_year), workplace: nullable(item.workplace || item.work_place) })),
  };
}
