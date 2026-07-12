import { buildHeaders } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";

import { mapOperationalOrdersApiError } from "./errors";
import type {
  ContentConfirmation,
  DocumentDetail,
  DocumentListResponse,
  DocumentLocalization,
  EditorialPackageValidation,
  PartyReference,
  PromotionResult,
  ReadyForSignatureResult,
  ReturnToCreatedResult,
  SignatureReadiness,
  SigningAuthorityResult,
  TranslationAssignment,
  WorkspaceDetail,
  WorkspaceListResponse,
} from "./types";

export { mapOperationalOrdersApiError } from "./errors";

export const OO_BASE_PATH = "/directory/operational-orders";
export const OO_API_PREFIX = "/api/operational-orders";

type RequestOptions = {
  method?: string;
  body?: unknown;
};

async function requestJson<T>(path: string, opts?: RequestOptions): Promise<T> {
  const headers = buildHeaders(
    opts?.body !== undefined ? { "Content-Type": "application/json" } : undefined,
  ) as Record<string, string>;
  const res = await fetch(resolveApiUrl(path), {
    method: opts?.method ?? (opts?.body !== undefined ? "POST" : "GET"),
    headers,
    body: opts?.body !== undefined ? JSON.stringify(opts.body) : undefined,
    cache: "no-store",
  });

  const text = await res.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!res.ok) {
    const err = new Error("Request failed") as Error & {
      status: number;
      details: unknown;
    };
    err.status = res.status;
    err.details = parsed;
    throw err;
  }

  return parsed as T;
}

export type WorkspaceListParams = {
  stage?: string;
  submitting_org_unit_id?: number;
  record_creator_user_id?: number;
  drafting_path?: string;
  promoted?: boolean;
  limit?: number;
  offset?: number;
};

export type DocumentListParams = {
  status?: string;
  workspace_id?: number;
  submitting_org_unit_id?: number;
  limit?: number;
  offset?: number;
};

function buildQuery(params: Record<string, string | number | boolean | undefined>): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === "") continue;
    qs.set(key, String(value));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

export async function listWorkspaces(params: WorkspaceListParams = {}): Promise<WorkspaceListResponse> {
  return requestJson(`${OO_API_PREFIX}/draft-workspaces${buildQuery(params)}`);
}

export async function getWorkspace(workspaceId: number): Promise<WorkspaceDetail> {
  return requestJson(`${OO_API_PREFIX}/draft-workspaces/${workspaceId}`);
}

export async function listDocuments(params: DocumentListParams = {}): Promise<DocumentListResponse> {
  return requestJson(`${OO_API_PREFIX}/documents${buildQuery(params)}`);
}

export async function getDocument(documentId: number): Promise<DocumentDetail> {
  return requestJson(`${OO_API_PREFIX}/documents/${documentId}`);
}

export async function getDocumentLocalizations(
  documentId: number,
  versionNumber?: number,
): Promise<{ document_id: number; version_number: number; items: DocumentLocalization[] }> {
  return requestJson(
    `${OO_API_PREFIX}/documents/${documentId}/localizations${buildQuery({ version_number: versionNumber })}`,
  );
}

export async function patchBlockEffectiveText(
  workspaceId: number,
  blockId: number,
  workspaceEffectiveText: string,
  expectedVersion: number,
): Promise<WorkspaceDetail> {
  return requestJson(`${OO_API_PREFIX}/draft-workspaces/${workspaceId}/blocks/${blockId}`, {
    method: "PATCH",
    body: { workspace_effective_text: workspaceEffectiveText, expected_version: expectedVersion },
  });
}

export async function validateWorkspace(
  workspaceId: number,
  expectedVersion?: number,
): Promise<WorkspaceDetail> {
  return requestJson(`${OO_API_PREFIX}/draft-workspaces/${workspaceId}/validate`, {
    body: { expected_version: expectedVersion },
  });
}

export async function resolveClarification(
  workspaceId: number,
  clarificationId: number,
  resolutionNote: string | undefined,
  expectedVersion: number,
): Promise<WorkspaceDetail> {
  return requestJson(
    `${OO_API_PREFIX}/draft-workspaces/${workspaceId}/clarifications/${clarificationId}/resolve`,
    { body: { resolution_note: resolutionNote, expected_version: expectedVersion } },
  );
}

export async function validateEditorialPackage(
  workspaceId: number,
  expectedVersion?: number,
): Promise<EditorialPackageValidation> {
  return requestJson(`${OO_API_PREFIX}/draft-workspaces/${workspaceId}/validate-editorial-package`, {
    body: { expected_version: expectedVersion },
  });
}

export async function markEditorialPackageReady(
  workspaceId: number,
  expectedVersion: number,
): Promise<WorkspaceDetail> {
  return requestJson(`${OO_API_PREFIX}/draft-workspaces/${workspaceId}/editorial-package-ready`, {
    body: { expected_version: expectedVersion },
  });
}

export async function promoteWorkspace(
  workspaceId: number,
  expectedWorkspaceVersion: number,
): Promise<PromotionResult> {
  return requestJson(`${OO_API_PREFIX}/workspaces/${workspaceId}/promote`, {
    body: { expected_workspace_version: expectedWorkspaceVersion },
  });
}

export async function createTranslationAssignment(
  workspaceId: number,
  payload: {
    target_locale: "ru" | "kk";
    assigned_to: PartyReference;
    due_at?: string;
    notes?: string;
    expected_version: number;
  },
): Promise<WorkspaceDetail> {
  return requestJson(`${OO_API_PREFIX}/draft-workspaces/${workspaceId}/translation-assignments`, {
    body: payload,
  });
}

export async function translationAssignmentAction(
  workspaceId: number,
  assignmentId: number,
  action: "accept" | "start" | "cancel" | "complete",
  payload: Record<string, unknown>,
): Promise<WorkspaceDetail> {
  const suffix = action === "complete" ? "complete" : action;
  return requestJson(
    `${OO_API_PREFIX}/draft-workspaces/${workspaceId}/translation-assignments/${assignmentId}/${suffix}`,
    { body: payload },
  );
}

export async function createConfirmation(
  workspaceId: number,
  payload: {
    block_id: number;
    confirmation_role: string;
    confirmer: PartyReference;
    block_expected_version?: number;
    expected_version?: number;
    operator_recorded?: boolean;
  },
): Promise<WorkspaceDetail> {
  return requestJson(`${OO_API_PREFIX}/draft-workspaces/${workspaceId}/confirmations`, {
    body: payload,
  });
}

export async function revokeConfirmation(
  workspaceId: number,
  confirmationId: number,
  payload: { revocation_reason?: string; expected_version?: number; confirmation_expected_version?: number },
): Promise<WorkspaceDetail> {
  return requestJson(
    `${OO_API_PREFIX}/draft-workspaces/${workspaceId}/confirmations/${confirmationId}/revoke`,
    { body: payload },
  );
}

export async function createReconciliation(
  workspaceId: number,
  payload: {
    ru_block_id: number;
    kk_block_id: number;
    notes?: string;
    ru_block_expected_version?: number;
    kk_block_expected_version?: number;
    expected_version?: number;
  },
): Promise<WorkspaceDetail> {
  return requestJson(`${OO_API_PREFIX}/draft-workspaces/${workspaceId}/reconciliations`, {
    body: payload,
  });
}

export async function invalidateReconciliation(
  workspaceId: number,
  reconciliationId: number,
  payload: {
    invalidation_reason?: string;
    expected_version?: number;
    reconciliation_expected_version?: number;
  },
): Promise<WorkspaceDetail> {
  return requestJson(
    `${OO_API_PREFIX}/draft-workspaces/${workspaceId}/reconciliations/${reconciliationId}/invalidate`,
    { body: payload },
  );
}

export async function assignSigningAuthority(
  documentId: number,
  payload: {
    authority: PartyReference;
    authority_position_id?: number | null;
    authority_org_unit_id?: number | null;
    authority_basis?: string | null;
    expected_document_version: number;
  },
): Promise<SigningAuthorityResult> {
  return requestJson(`${OO_API_PREFIX}/documents/${documentId}/signing-authority`, { body: payload });
}

export async function validateReadyForSignature(
  documentId: number,
  expectedDocumentVersion?: number,
): Promise<SignatureReadiness> {
  return requestJson(`${OO_API_PREFIX}/documents/${documentId}/validate-ready-for-signature`, {
    body: { expected_document_version: expectedDocumentVersion },
  });
}

export async function markReadyForSignature(
  documentId: number,
  expectedDocumentVersion: number,
): Promise<ReadyForSignatureResult> {
  return requestJson(`${OO_API_PREFIX}/documents/${documentId}/ready-for-signature`, {
    body: { expected_document_version: expectedDocumentVersion },
  });
}

export async function returnToCreated(
  documentId: number,
  reason: string,
  expectedDocumentVersion: number,
): Promise<ReturnToCreatedResult> {
  return requestJson(`${OO_API_PREFIX}/documents/${documentId}/return-to-created`, {
    body: { reason, expected_document_version: expectedDocumentVersion },
  });
}

export function mapOoApiError(err: unknown, fallback: string): string {
  return mapOperationalOrdersApiError(err, fallback);
}

export function parseTranslationAssignments(detail: WorkspaceDetail): TranslationAssignment[] {
  return (detail.translation_assignments ?? []) as TranslationAssignment[];
}

export function parseContentConfirmations(detail: WorkspaceDetail): ContentConfirmation[] {
  return (detail.content_confirmations ?? []) as ContentConfirmation[];
}
