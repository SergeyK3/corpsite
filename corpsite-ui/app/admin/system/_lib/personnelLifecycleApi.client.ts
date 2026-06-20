// FILE: corpsite-ui/app/admin/system/_lib/personnelLifecycleApi.client.ts
import { apiFetchJson } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";

import type { Paginated } from "./adminSystemApi.client";

/* ---------- Lifecycle runs ---------- */

export type LifecycleRunSummary = {
  run_id: number;
  previous_snapshot_id: number;
  snapshot_id: number;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  actor_user_id?: number | null;
  dry_run: boolean;
  refresh_cache: boolean;
  enqueue: boolean;
  sync_persons: boolean;
  effective_entries_processed?: number;
  events_created: number;
  events_existing?: number;
  enrollment_created?: number;
  enrollment_existing?: number;
  persons_created: number;
  persons_updated?: number;
  assignments_created: number;
  assignments_updated?: number;
  assignments_closed?: number;
  warnings_count: number;
  errors_count: number;
};

export type LifecycleRunDetail = LifecycleRunSummary & {
  summary: Record<string, unknown>;
};

export type LifecycleRunRequest = {
  previous_snapshot_id: number;
  snapshot_id: number;
  refresh_cache?: boolean;
  enqueue?: boolean;
  sync_persons?: boolean;
};

export type LifecycleRunReport = {
  run_id?: number | null;
  previous_snapshot_id: number;
  snapshot_id: number;
  dry_run: boolean;
  refresh_cache: boolean;
  enqueue: boolean;
  sync_persons: boolean;
  run_status: string;
  duration_ms: number;
  effective_cache: Record<string, unknown>;
  monthly_diff: Record<string, unknown>;
  personnel_events: Record<string, unknown>;
  enrollment: Record<string, unknown>;
  person_sync: Record<string, unknown>;
  validation: Record<string, unknown>;
  warnings: string[];
  errors: Record<string, unknown>[];
};

/* ---------- Personnel events ---------- */

export type PersonnelEventSummary = {
  personnel_event_id: number;
  previous_snapshot_id: number;
  snapshot_id: number;
  person_key: string;
  assignment_key?: string | null;
  event_type: string;
  status: string;
  field_path?: string | null;
  person_id?: number | null;
  assignment_id?: number | null;
  detected_at?: string | null;
  resolved_at?: string | null;
};

export type PersonnelEventDetail = PersonnelEventSummary & {
  source_event_id?: number | null;
  old_value?: unknown;
  new_value?: unknown;
  effective_old_value?: unknown;
  effective_new_value?: unknown;
  resolved_by_user_id?: number | null;
  metadata: Record<string, unknown>;
};

/* ---------- Overrides ---------- */

export type OverrideSummary = {
  override_id: number;
  scope_type: string;
  scope_key: string;
  field_path: string;
  status: string;
  tier: number;
  owner_domain: string;
  person_key?: string | null;
  assignment_key?: string | null;
  stale_flag: boolean;
  created_at?: string | null;
  updated_at?: string | null;
};

export type OverrideDetail = OverrideSummary & {
  person_id?: number | null;
  assignment_id?: number | null;
  canonical_value?: unknown;
  override_value?: unknown;
  justification?: string | null;
  evidence_url?: string | null;
  created_by_user_id?: number | null;
  approved_by_user_id?: number | null;
  approved_at?: string | null;
  supersedes_override_id?: number | null;
  superseded_by_override_id?: number | null;
  metadata: Record<string, unknown>;
};

export type OverrideActionRequest = {
  comment?: string;
  reason?: string;
};

/* ---------- Effective person ---------- */

export type EffectivePersonResponse = {
  snapshot_id: number;
  entry_id: number;
  person_key: string;
  assignment_key?: string | null;
  scope_type: string;
  record_kind: string;
  entity_scope?: string | null;
  canonical_payload: Record<string, unknown>;
  effective_payload: Record<string, unknown>;
  applied_override_ids: number[];
};

/* ---------- Validation ---------- */

export type ValidationCheck = {
  code: string;
  severity: string;
  count: number;
  samples?: Record<string, unknown>[];
  snapshots?: Record<string, unknown>[];
};

export type ValidationResponse = {
  previous_snapshot_id: number;
  snapshot_id: number;
  checks: ValidationCheck[];
  warnings_count: number;
  errors_count: number;
  warnings: string[];
  errors: string[];
  validated_at?: string | null;
};

export function mapPersonnelLifecycleApiError(err: unknown, fallback: string): string {
  return formatThrownError(err, { fallback });
}

export async function fetchLifecycleRuns(params?: {
  previous_snapshot_id?: number;
  snapshot_id?: number;
  status?: string;
  limit?: number;
  offset?: number;
  sort_by?: string;
  sort_dir?: string;
}): Promise<Paginated<LifecycleRunSummary>> {
  return apiFetchJson<Paginated<LifecycleRunSummary>>("/admin/personnel/lifecycle/runs", {
    query: params,
  });
}

export async function fetchLifecycleRun(runId: number): Promise<LifecycleRunDetail> {
  return apiFetchJson<LifecycleRunDetail>(`/admin/personnel/lifecycle/runs/${runId}`);
}

export async function previewLifecycleRun(body: LifecycleRunRequest): Promise<LifecycleRunReport> {
  return apiFetchJson<LifecycleRunReport>("/admin/personnel/lifecycle/run-preview", {
    method: "POST",
    body,
  });
}

export async function executeLifecycleRun(body: LifecycleRunRequest): Promise<LifecycleRunReport> {
  return apiFetchJson<LifecycleRunReport>("/admin/personnel/lifecycle/run", {
    method: "POST",
    body,
  });
}

export async function fetchLifecycleValidation(params: {
  previous_snapshot_id: number;
  snapshot_id: number;
}): Promise<ValidationResponse> {
  return apiFetchJson<ValidationResponse>("/admin/personnel/lifecycle/validation", {
    query: params,
  });
}

export async function fetchPersonnelEvents(params?: {
  snapshot_id?: number;
  event_type?: string;
  status?: string;
  person_key?: string;
  assignment_key?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
  sort_by?: string;
  sort_dir?: string;
}): Promise<Paginated<PersonnelEventSummary>> {
  return apiFetchJson<Paginated<PersonnelEventSummary>>("/admin/personnel/events", {
    query: params,
  });
}

export async function fetchPersonnelEvent(eventId: number): Promise<PersonnelEventDetail> {
  return apiFetchJson<PersonnelEventDetail>(`/admin/personnel/events/${eventId}`);
}

export async function fetchOverrides(params?: {
  status?: string;
  scope_type?: string;
  person_key?: string;
  assignment_key?: string;
  field_path?: string;
  limit?: number;
  offset?: number;
  sort_by?: string;
  sort_dir?: string;
}): Promise<Paginated<OverrideSummary>> {
  return apiFetchJson<Paginated<OverrideSummary>>("/admin/personnel/overrides", { query: params });
}

export async function fetchOverride(overrideId: number): Promise<OverrideDetail> {
  return apiFetchJson<OverrideDetail>(`/admin/personnel/overrides/${overrideId}`);
}

export async function approveOverride(
  overrideId: number,
  body?: OverrideActionRequest,
): Promise<OverrideSummary> {
  return apiFetchJson<OverrideSummary>(`/admin/personnel/overrides/${overrideId}/approve`, {
    method: "POST",
    body: body ?? {},
  });
}

export async function rejectOverride(
  overrideId: number,
  body: OverrideActionRequest,
): Promise<OverrideSummary> {
  return apiFetchJson<OverrideSummary>(`/admin/personnel/overrides/${overrideId}/reject`, {
    method: "POST",
    body,
  });
}

export async function revokeOverride(
  overrideId: number,
  body: OverrideActionRequest,
): Promise<OverrideSummary> {
  return apiFetchJson<OverrideSummary>(`/admin/personnel/overrides/${overrideId}/revoke`, {
    method: "POST",
    body,
  });
}

export async function reconfirmOverride(
  overrideId: number,
  body?: OverrideActionRequest,
): Promise<OverrideSummary> {
  return apiFetchJson<OverrideSummary>(`/admin/personnel/overrides/${overrideId}/reconfirm`, {
    method: "POST",
    body: body ?? {},
  });
}

export async function fetchEffectivePerson(params: {
  person_key: string;
  assignment_key?: string;
  snapshot_id?: number;
}): Promise<EffectivePersonResponse> {
  return apiFetchJson<EffectivePersonResponse>("/admin/personnel/effective-person", {
    query: params,
  });
}
