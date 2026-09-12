/** PPR Query API client — read-only, canonical `/api/ppr/*` path. */

import { buildHeaders, handleAuthFailureIfNeeded, readJsonSafe, toApiError } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";
import type {
  PprCompositeReadResponse,
  PprCompositeSummaryResponse,
} from "./pprQueryTypes";

function getDevUserId(): string | null {
  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
  if (appEnv === "prod" || appEnv === "production") return null;
  const v = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  return v ? v : null;
}

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const devUserId = getDevUserId();
  if (devUserId) headers["X-User-Id"] = devUserId;
  return buildHeaders(headers) as Record<string, string>;
}

async function pprGetJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(resolveApiUrl(path), {
    method: "GET",
    headers: authHeaders(),
    cache: "no-store",
    signal,
  });
  const body = await readJsonSafe(res);
  if (!res.ok) {
    const clearedLockedSession = handleAuthFailureIfNeeded(res.status, body);
    if (clearedLockedSession && typeof window !== "undefined") {
      const returnTo = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      window.location.assign(`/login?return_to=${encodeURIComponent(returnTo)}`);
    }
    throw toApiError(res.status, body, { method: "GET", url: path });
  }
  return body as T;
}

export async function getPprByEmployeeId(
  employeeId: string | number,
  opts?: { signal?: AbortSignal },
): Promise<PprCompositeReadResponse> {
  return pprGetJson<PprCompositeReadResponse>(
    `/api/ppr/employees/${encodeURIComponent(String(employeeId))}`,
    opts?.signal,
  );
}

export async function getPprByPersonId(
  personId: string | number,
  opts?: { signal?: AbortSignal },
): Promise<PprCompositeReadResponse> {
  return pprGetJson<PprCompositeReadResponse>(
    `/api/ppr/persons/${encodeURIComponent(String(personId))}`,
    opts?.signal,
  );
}

export async function getPprPersonPhoto(
  personId: string | number,
  opts?: { signal?: AbortSignal },
): Promise<Blob> {
  const path = `/api/ppr/persons/${encodeURIComponent(String(personId))}/photo`;
  const res = await fetch(resolveApiUrl(path), {
    method: "GET",
    headers: { ...authHeaders(), Accept: "image/jpeg" },
    cache: "no-store",
    signal: opts?.signal,
  });
  if (!res.ok) {
    const body = await readJsonSafe(res);
    throw toApiError(res.status, body, { method: "GET", url: path });
  }
  return res.blob();
}

export type PprPersonPhotoUploadResponse = {
  person_id: number;
  person_photo_id: number;
  status: string;
};

export async function uploadPprPersonPhoto(
  personId: string | number,
  file: File,
): Promise<PprPersonPhotoUploadResponse> {
  const path = `/api/ppr/persons/${encodeURIComponent(String(personId))}/photo`;
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(resolveApiUrl(path), {
    method: "POST",
    // Do not set Content-Type: the browser supplies the multipart boundary.
    headers: authHeaders(),
    body: formData,
    cache: "no-store",
  });
  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, { method: "POST", url: path });
  }
  return body as PprPersonPhotoUploadResponse;
}

export async function getPprSummaryByPersonId(
  personId: string | number,
  opts?: { signal?: AbortSignal },
): Promise<PprCompositeSummaryResponse> {
  return pprGetJson<PprCompositeSummaryResponse>(
    `/api/ppr/persons/${encodeURIComponent(String(personId))}/summary`,
    opts?.signal,
  );
}

export type PprIntendedEmploymentUpdateBody = {
  org_group_id?: number | null;
  org_unit_id?: number | null;
  position_id?: number | null;
  employment_rate?: number | null;
};

export async function patchPprIntendedEmployment(
  personId: string | number,
  body: PprIntendedEmploymentUpdateBody,
): Promise<import("./pprQueryTypes").PprIntendedEmploymentResponse> {
  const res = await fetch(
    resolveApiUrl(`/api/ppr/persons/${encodeURIComponent(String(personId))}/intended-employment`),
    {
      method: "PATCH",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    },
  );
  const payload = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, payload, {
      method: "PATCH",
      url: `/api/ppr/persons/${personId}/intended-employment`,
    });
  }
  return payload as import("./pprQueryTypes").PprIntendedEmploymentResponse;
}

export async function getPprHireDefaultsByPersonId(
  personId: string | number,
  opts?: { signal?: AbortSignal },
): Promise<import("./pprQueryTypes").PprHireDefaultsResponse> {
  return pprGetJson<import("./pprQueryTypes").PprHireDefaultsResponse>(
    `/api/ppr/persons/${encodeURIComponent(String(personId))}/hire-defaults`,
    opts?.signal,
  );
}
