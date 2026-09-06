import { apiFetchJson } from "@/lib/api";

export type SystemIdentityObjectType = "USER" | "ROLE";
export type SystemIdentitySearchField = "full_name" | "login" | "name" | "code";

export type SystemIdentityTarget = {
  object_type: SystemIdentityObjectType;
  object_id: number;
};

export type SystemIdentitySearchItem = SystemIdentityTarget & {
  label: string;
  secondary_label: string | null;
};

export type SystemIdentityRelationship = {
  relation_code: string;
  table: string;
  columns: string[];
  classification: "BLOCKING" | "PRESERVE" | "REBIND_HISTORICAL_AUTHORSHIP" | "DELETE_ALLOWLIST";
  count: number;
  state_digest: string;
  on_delete: string | null;
};

export type SystemIdentityPreviewItem = SystemIdentitySearchItem & {
  has_test_provenance: boolean;
  ready_for_deletion: boolean;
  blocking_codes: string[];
  relationships: SystemIdentityRelationship[];
  relationship_fingerprint: string;
};

export type SystemIdentitySearchResponse = {
  items: SystemIdentitySearchItem[];
  count: number;
  typed_ids: SystemIdentityTarget[];
  target_list_hash: string;
  normalized_mask: string | null;
};

export type SystemIdentityPreviewResponse = {
  items: SystemIdentityPreviewItem[];
  count: number;
  ready_count: number;
  typed_ids: SystemIdentityTarget[];
  target_list_hash: string;
  relationship_fingerprint: string;
  fingerprint_version: string;
  policy_version: string;
};

export function searchSystemIdentities(params: {
  objectType: SystemIdentityObjectType;
  field: SystemIdentitySearchField;
  selector: string;
}): Promise<SystemIdentitySearchResponse> {
  const selector = params.selector.trim();
  const exactId = /^\d+$/.test(selector) ? Number(selector) : null;
  return apiFetchJson<SystemIdentitySearchResponse>("/directory/test-system-identity-deletion/search", {
    method: "POST",
    body: {
      object_type: params.objectType,
      field: params.field,
      ...(exactId !== null ? { object_ids: [exactId] } : { mask: selector }),
    },
  });
}

export function previewSystemIdentities(
  targets: SystemIdentityTarget[],
): Promise<SystemIdentityPreviewResponse> {
  return apiFetchJson<SystemIdentityPreviewResponse>("/directory/test-system-identity-deletion/preview", {
    method: "POST",
    body: { targets },
  });
}

/** Read-only authorization probe for older /auth/me projections. */
export function probeSystemIdentityDeletionAccess(): Promise<SystemIdentitySearchResponse> {
  return apiFetchJson<SystemIdentitySearchResponse>("/directory/test-system-identity-deletion/search", {
    method: "POST",
    body: {
      object_type: "USER",
      field: "full_name",
      object_ids: [2147483647],
    },
  });
}
