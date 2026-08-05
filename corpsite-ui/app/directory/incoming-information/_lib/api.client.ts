import { apiFetchJson } from "@/lib/api";

import type {
  IncomingDocumentDetail,
  IncomingDocumentListQuery,
  IncomingDocumentListResponse,
} from "./types";

export const INCOMING_INFORMATION_API_PREFIX = "/api/incoming-information";

export async function listIncomingDocuments(
  query: IncomingDocumentListQuery,
): Promise<IncomingDocumentListResponse> {
  return apiFetchJson<IncomingDocumentListResponse>(
    `${INCOMING_INFORMATION_API_PREFIX}/incoming-documents`,
    {
      query: {
        limit: query.limit,
        offset: query.offset,
      },
    },
  );
}

export async function getIncomingDocument(documentId: number): Promise<IncomingDocumentDetail> {
  return apiFetchJson<IncomingDocumentDetail>(
    `${INCOMING_INFORMATION_API_PREFIX}/incoming-documents/${documentId}`,
  );
}

export function incomingInformationErrorStatus(error: unknown): number {
  if (!error || typeof error !== "object" || !("status" in error)) return 0;
  const status = Number((error as { status?: unknown }).status);
  return Number.isFinite(status) ? status : 0;
}

export function incomingInformationErrorMessage(error: unknown, fallback: string): string {
  if (!error || typeof error !== "object" || !("message" in error)) return fallback;
  const message = String((error as { message?: unknown }).message ?? "").trim();
  return message || fallback;
}
