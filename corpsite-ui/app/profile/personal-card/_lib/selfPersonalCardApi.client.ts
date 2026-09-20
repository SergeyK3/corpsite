"use client";

import { buildHeaders, handleAuthFailureIfNeeded, readJsonSafe, toApiError } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";
import type {
  PprAdditionalProfileResponse,
  PprGeneralResponse,
  PprMaterializationResponse,
  PprSectionResponse,
} from "@/app/directory/personnel/_lib/pprQueryTypes";

export type SelfPersonalCard = {
  materialization: PprMaterializationResponse;
  general: PprGeneralResponse;
  sections: Record<string, PprSectionResponse>;
  additional: PprAdditionalProfileResponse;
};

export type SelfPersonalCardResponse =
  | { status: "READY"; card: SelfPersonalCard }
  | { status: "NO_EMPLOYEE_LINK" | "PERSON_NOT_LINKED" | "IDENTITY_AMBIGUOUS"; card: null };

export type SelfOperationalAssignment = {
  department_group_name: string | null;
  org_unit_name: string | null;
  position_name: string | null;
  operational_status: string | null;
  employment_rate: number | null;
  /** Full IIN is allowed only in this employee's self-service projection. */
  iin: string | null;
};

export type SelfOperationalAssignmentResponse =
  | { status: "READY"; operational_assignment: SelfOperationalAssignment }
  | { status: "NO_EMPLOYEE_LINK" | "PERSON_NOT_LINKED" | "IDENTITY_AMBIGUOUS"; operational_assignment: null };

/**
 * The self-service API deliberately accepts no Employee or Person identifier.
 * Subject resolution happens exclusively on the server from the session user.
 */
export async function getMyPersonalCard(
  opts?: { signal?: AbortSignal },
): Promise<SelfPersonalCardResponse> {
  const path = "/api/ppr/me";
  const response = await fetch(resolveApiUrl(path), {
    method: "GET",
    headers: buildHeaders({ Accept: "application/json" }),
    cache: "no-store",
    signal: opts?.signal,
  });
  const body = await readJsonSafe(response);
  if (!response.ok) {
    const clearedLockedSession = handleAuthFailureIfNeeded(response.status, body);
    if (clearedLockedSession && typeof window !== "undefined") {
      const returnTo = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      window.location.assign(`/login?return_to=${encodeURIComponent(returnTo)}`);
    }
    throw toApiError(response.status, body, { method: "GET", url: path });
  }
  return body as SelfPersonalCardResponse;
}

/** ID-free operational Employee projection for the authenticated caller only. */
export async function getMyOperationalAssignment(
  opts?: { signal?: AbortSignal },
): Promise<SelfOperationalAssignmentResponse> {
  const path = "/api/ppr/me/operational-assignment";
  const response = await fetch(resolveApiUrl(path), {
    method: "GET",
    headers: buildHeaders({ Accept: "application/json" }),
    cache: "no-store",
    signal: opts?.signal,
  });
  const body = await readJsonSafe(response);
  if (!response.ok) {
    const clearedLockedSession = handleAuthFailureIfNeeded(response.status, body);
    if (clearedLockedSession && typeof window !== "undefined") {
      const returnTo = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      window.location.assign(`/login?return_to=${encodeURIComponent(returnTo)}`);
    }
    throw toApiError(response.status, body, { method: "GET", url: path });
  }
  return body as SelfOperationalAssignmentResponse;
}

async function selfCommand<T>(path: string, method: "POST" | "PUT", body: object): Promise<T> {
  const response = await fetch(resolveApiUrl(path), { method, headers: buildHeaders({ Accept: "application/json", "Content-Type": "application/json" }), body: JSON.stringify(body), cache: "no-store" });
  const payload = await readJsonSafe(response);
  if (!response.ok) throw toApiError(response.status, payload, { method, url: path });
  return payload as T;
}

const commandId = () => globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
export const saveMyContacts = (body: object) => selfCommand("/api/ppr/me/contacts", "PUT", { command_id: commandId(), ...body });
export const saveMyForeignLanguages = (body: object) => selfCommand("/api/ppr/me/foreign-languages", "PUT", { command_id: commandId(), ...body });
export const addMyEducation = (record: object) => selfCommand("/api/ppr/me/education/records", "POST", { command_id: commandId(), record });
export const addMyExternalEmployment = (record: object, idempotencyCommandId = commandId()) => selfCommand("/api/ppr/me/employment-biography/records", "POST", { command_id: idempotencyCommandId, record });
export const supersedeMyExternalEmployment = (recordId: number, body: { expected_updated_at: string; replacement: object }, idempotencyCommandId = commandId()) => selfCommand(`/api/ppr/me/employment-biography/records/${recordId}/supersede`, "POST", { command_id: idempotencyCommandId, ...body });

export const getMyContacts = (opts?: { signal?: AbortSignal }) => selfGet<{ canonical: (Record<string, unknown> & { version?: number }) | null; fallback: Record<string, unknown> | null }>("/api/ppr/me/contacts", opts);
export const getMyForeignLanguages = (opts?: { signal?: AbortSignal }) => selfGet<{ foreign_languages: { language: string; proficiency: string }[]; updated_at: string | null }>("/api/ppr/me/foreign-languages", opts);

async function selfGet<T>(path: string, opts?: { signal?: AbortSignal }): Promise<T> {
  const response = await fetch(resolveApiUrl(path), { method: "GET", headers: buildHeaders({ Accept: "application/json" }), cache: "no-store", signal: opts?.signal });
  const body = await readJsonSafe(response);
  if (!response.ok) throw toApiError(response.status, body, { method: "GET", url: path });
  return body as T;
}
