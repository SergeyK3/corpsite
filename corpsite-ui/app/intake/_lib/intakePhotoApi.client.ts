import { buildHeaders, readJsonSafe, toApiError } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";
import type { IntakeDraftPayload } from "./intakeApi.client";

export type IntakePhotoMutationResponse = {
  application_id: number;
  photo_file_id: string;
  payload: IntakeDraftPayload;
  saved_at: string;
};

export function buildIntakePhotoPublicUrl(token: string, cacheBust?: string): string {
  const base = resolveApiUrl(`/intake/${encodeURIComponent(token)}/photo`);
  return cacheBust ? `${base}?v=${encodeURIComponent(cacheBust)}` : base;
}

export function buildIntakePhotoOnBehalfUrl(applicationId: number, cacheBust?: string): string {
  const base = resolveApiUrl(`/directory/personnel-applications/${applicationId}/intake/photo`);
  return cacheBust ? `${base}?v=${encodeURIComponent(cacheBust)}` : base;
}

export async function fetchIntakePhotoOnBehalfBlob(applicationId: number): Promise<Blob> {
  const path = `/directory/personnel-applications/${applicationId}/intake/photo`;
  const res = await fetch(resolveApiUrl(path), {
    method: "GET",
    headers: buildHeaders({ Accept: "image/jpeg" }),
    cache: "no-store",
  });
  if (!res.ok) {
    throw toApiError(res.status, await readJsonSafe(res), { method: "GET", url: path });
  }
  return res.blob();
}

export async function uploadIntakePhotoPublic(token: string, blob: Blob): Promise<IntakePhotoMutationResponse> {
  const path = `/intake/${encodeURIComponent(token)}/photo`;
  const form = new FormData();
  form.append("file", blob, "photo.jpg");
  const res = await fetch(resolveApiUrl(path), { method: "PUT", body: form });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "PUT", url: path });
  return body as IntakePhotoMutationResponse;
}

export async function deleteIntakePhotoPublic(token: string): Promise<IntakePhotoMutationResponse> {
  const path = `/intake/${encodeURIComponent(token)}/photo`;
  const res = await fetch(resolveApiUrl(path), { method: "DELETE", headers: buildHeaders() });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "DELETE", url: path });
  return body as IntakePhotoMutationResponse;
}

export async function uploadIntakePhotoOnBehalf(
  applicationId: number,
  blob: Blob,
): Promise<IntakePhotoMutationResponse> {
  const path = `/directory/personnel-applications/${applicationId}/intake/photo`;
  const form = new FormData();
  form.append("file", blob, "photo.jpg");
  const res = await fetch(resolveApiUrl(path), {
    method: "PUT",
    headers: buildHeaders(),
    body: form,
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "PUT", url: path });
  return body as IntakePhotoMutationResponse;
}

export async function deleteIntakePhotoOnBehalf(applicationId: number): Promise<IntakePhotoMutationResponse> {
  const path = `/directory/personnel-applications/${applicationId}/intake/photo`;
  const res = await fetch(resolveApiUrl(path), {
    method: "DELETE",
    headers: buildHeaders(),
  });
  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body, { method: "DELETE", url: path });
  return body as IntakePhotoMutationResponse;
}
