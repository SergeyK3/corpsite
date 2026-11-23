"use client";

import { apiFetchJson, buildHeaders, buildUrl, readJsonSafe, toApiError } from "./api";

export type TrainingStep = { key: string; actor: "participant" | "system"; instruction: string; evidence_label?: string };
export type TrainingAssignment = {
  assignment_id: number;
  title: string;
  lesson_code: string;
  lesson_number: number;
  position_label: string;
  duration_minutes: number;
  course_title: string;
  course_code: string;
  course_version: number;
  latest_attempt_id: number | null;
  latest_attempt_number: number | null;
  latest_status: string | null;
  latest_outcome: string | null;
  latest_score: number | null;
  latest_checked_at: string | null;
  latest_application_number: string | null;
  required: boolean;
  instruction_url?: string | null;
};
export type TrainingAttempt = {
  attempt_id: number;
  attempt_number: number;
  status: string;
  outcome: string | null;
  score: number | null;
  fixture: Record<string, unknown>;
  participant_user_id: number;
  lesson_code: string;
  lesson_number: number;
  lesson_title: string;
  course_title: string;
  course_version: number;
  duration_minutes: number;
  last_checked_at: string | null;
  source_data: string | null;
  expected_result: string | null;
  steps: TrainingStep[];
};
export type TrainingEvidence = {
  evidence_id: number;
  step_key: string;
  mime_type: string;
  width: number;
  height: number;
};
export type TrainingDetail = {
  attempt: TrainingAttempt;
  evidence: TrainingEvidence[];
  events: Array<Record<string, unknown>>;
  reviews: TrainingReview[];
};
export type TrainingReview = {
  review_id: number; outcome: string | null; score: number | null;
  explanation: string; created_at: string; reviewer_name: string | null;
};
export type TrainingSummaryAttempt = {
  attempt_id: number; attempt_number: number; status: string; outcome: string | null;
  score: number | null; explanation: string | null; last_checked_at: string | null;
  application_number: string | null; reviewed_at: string | null; reviewer_name: string | null;
};
export type TrainingSummaryItem = {
  assignment_id: number; course_code: string; course_title: string; course_version: number;
  lesson_code: string; lesson_number: number; lesson_title: string; attempts: TrainingSummaryAttempt[];
};
export type TrainingSummary = { full_name: string; position_name: string | null; items: TrainingSummaryItem[] };
export type TrainingNotice = {
  notification_id: number; review_id: number; attempt_id: number; attempt_number: number;
  application_number: string | null; course_title: string; lesson_title: string;
  lesson_number: number; score: number; outcome: string; explanation: string;
  reviewed_at: string; reviewer_name: string | null;
};
export type TrainingTask = {
  assignment_id: number; source_kind: "training_assignment";
  course_title: string; lesson_title: string; lesson_number: number;
  state: "not_started" | "in_progress" | "under_review" | "failed" | "passed";
  href: string; due_at: string | null;
};
export type TrainingReviewRow = {
  attempt_id: number; attempt_number: number; full_name: string;
  lesson_code: string; lesson_number: number; lesson_title: string; course_title: string; course_version: number;
  fixture: Record<string, unknown>;
};

export const trainingApi = {
  catalog: () => apiFetchJson<{ items: Array<Record<string, unknown>> }>("/training/catalog"),
  assignments: () => apiFetchJson<{ items: TrainingAssignment[] }>("/training/assignments"),
  preview: (id: number) => apiFetchJson<{ ready: boolean; reason?: string; fixture?: Record<string, unknown> }>(`/training/assignments/${id}/preview`, { method: "POST" }),
  start: (id: number, key: string) => apiFetchJson<{ attempt_id: number; attempt_number: number }>(`/training/assignments/${id}/attempts`, { method: "POST", headers: { "Idempotency-Key": key } }),
  detail: (id: number) => apiFetchJson<TrainingDetail>(`/training/attempts/${id}`),
  check: (id: number) => apiFetchJson<{ status: string; message: string; missing_steps?: string[] }>(`/training/attempts/${id}/check`, { method: "POST" }),
  hireRecord: (id: number) => apiFetchJson<Record<string, unknown>>(`/training/attempts/${id}/record`),
  hireConsent: (id: number) => apiFetchJson<Record<string, unknown>>(`/training/attempts/${id}/record/consent`, { method: "POST" }),
  mySummary: () => apiFetchJson<TrainingSummary>("/training/me/summary"),
  myNotifications: () => apiFetchJson<{ items: TrainingNotice[] }>("/training/me/notifications"),
  myTasks: () => apiFetchJson<{ items: TrainingTask[] }>("/training/me/tasks"),
  review: (id: number, decision: { evidence_valid: boolean; established_substitution: boolean; hint_or_action_correction: boolean; explanation: string }) =>
    apiFetchJson<{ status: string; outcome: string; score: number }>(`/training/attempts/${id}/review`, { method: "POST", body: decision }),
  attempts: (query?: Record<string, string | number>) => apiFetchJson<{ items: TrainingReviewRow[]; total: number; page: number; page_size: number }>("/training/results/attempts", { query }),
  courses: (query?: Record<string, string | number>) => apiFetchJson<{ items: Array<Record<string, unknown>>; total: number; page: number; page_size: number }>("/training/results/courses", { query }),
};

export async function uploadTrainingEvidence(attemptId: number, stepKey: string, file: File): Promise<TrainingEvidence> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(buildUrl(`/training/attempts/${attemptId}/steps/${stepKey}/evidence`), {
    method: "POST", headers: buildHeaders(), body, cache: "no-store",
  });
  const payload = await readJsonSafe(response);
  if (!response.ok) throw toApiError(response.status, payload);
  return payload as TrainingEvidence;
}

export async function trainingEvidenceUrl(id: number): Promise<string> {
  const response = await fetch(buildUrl(`/training/evidence/${id}`), {
    headers: buildHeaders(), cache: "no-store",
  });
  if (!response.ok) throw toApiError(response.status, await readJsonSafe(response));
  return URL.createObjectURL(await response.blob());
}

export async function removeTrainingEvidence(id: number): Promise<void> {
  await apiFetchJson(`/training/evidence/${id}`, { method: "DELETE" });
}
