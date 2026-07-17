import { readJsonSafe, toApiError } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";
import { resolveApiUrl } from "@/lib/apiBase";

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
  };
  contacts: {
    mobile_phone: string;
    email: string;
    registration_address: string;
    residence_address: string;
  };
  education: Array<{
    institution: string;
    year_from: string;
    year_to: string;
    specialty: string;
    qualification: string;
    diploma_number: string;
  }>;
  training: Array<{
    institution: string;
    year: string;
    course_name: string;
    hours: number | null;
  }>;
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
    fitness_category: string;
    commissariat: string;
    registration_group: string;
    registration_category: string;
  };
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
  { id: "review", title: "Проверка" },
] as const;

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
      fitness_category: "",
      commissariat: "",
      registration_group: "",
      registration_category: "",
    },
    current_step: "personal",
  };
}

export function mapIntakeApiError(error: unknown, fallback: string): string {
  return formatThrownError(error, fallback);
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
