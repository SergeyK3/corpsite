export type PartyReference = {
  reference_type: "PERSON" | "POSITION_ROLE" | "ORG_UNIT";
  reference: string;
  display_name?: string | null;
};

export type ValidationIssue = {
  code: string;
  severity: string;
  message: string;
  field_path?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type ValidationResult = {
  is_valid: boolean;
  has_errors: boolean;
  has_warnings: boolean;
  issues: ValidationIssue[];
};

export type WorkspaceSummary = {
  workspace_id: number;
  organization_id: number;
  drafting_path: string;
  stage: string;
  submitting_org_unit_id: number;
  record_creator_user_id: number;
  content_author_reference: string;
  content_author_type: string;
  proposed_title: string | null;
  submitted_at: string;
  accepted_at: string | null;
  created_at: string;
  updated_at: string;
  version: number;
  ru_present?: boolean | null;
  kk_present?: boolean | null;
  document_id?: number | null;
  open_clarification_count?: number | null;
  has_active_translation?: boolean | null;
};

export type DraftBlock = {
  block_id: number;
  workspace_id: number;
  locale: string;
  block_type: string;
  submitted_text: string;
  workspace_effective_text: string | null;
  sequence: number;
  source_type: string;
  review_state: string;
  version: number;
  created_at: string;
  updated_at: string;
};

export type Clarification = {
  clarification_id: number;
  workspace_id: number;
  code: string;
  severity: string;
  category: string;
  message: string;
  field_path: string | null;
  status: string;
  requested_by: number | null;
  resolved_by: number | null;
  resolution_note: string | null;
  created_at: string;
  resolved_at: string | null;
};

export type AuditSummary = {
  audit_id: number;
  action: string;
  actor_user_id: number | null;
  created_at: string;
};

export type ProvenanceSummary = {
  provenance_id: number;
  draft_block_id: number;
  locale: string;
  source_type: string;
  action: string;
  content_fingerprint: string | null;
  created_at: string;
};

export type TranslationAssignment = {
  id: number;
  workspace_id: number;
  source_locale: string;
  target_locale: string;
  assigned_to_type: string;
  assigned_to_reference: string;
  assigned_to_display_name: string | null;
  assigned_by_user_id: number;
  status: string;
  requested_at: string;
  accepted_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  due_at: string | null;
  source_block_version: number;
  target_block_version: number | null;
  source_content_fingerprint: string;
  produced_content_fingerprint: string | null;
  notes: string | null;
  version: number;
  created_at: string;
  updated_at: string;
};

export type ContentConfirmation = {
  id: number;
  workspace_id: number;
  locale: string;
  block_id: number;
  block_version: number;
  content_fingerprint: string;
  confirmer_party_type: string;
  confirmer_party_reference: string;
  confirmer_display_name: string | null;
  confirmer_user_id: number | null;
  confirmation_role: string;
  status: string;
  confirmed_at: string | null;
  revoked_at: string | null;
  revocation_reason: string | null;
  version: number;
  created_at: string;
};

export type BilingualReconciliation = {
  id: number;
  workspace_id: number;
  ru_block_id: number;
  kk_block_id: number;
  ru_block_version: number;
  kk_block_version: number;
  ru_content_fingerprint: string;
  kk_content_fingerprint: string;
  status: string;
  reconciled_by_user_id: number | null;
  reconciled_at: string | null;
  invalidation_reason: string | null;
  invalidated_at: string | null;
  version: number;
  notes: string | null;
  created_at: string;
};

export type WorkspaceDetail = {
  workspace: WorkspaceSummary;
  blocks: DraftBlock[];
  provenance: ProvenanceSummary[];
  clarifications: Clarification[];
  audit: AuditSummary[];
  validation: ValidationResult;
  locale_completeness: { ru_present: boolean; kk_present: boolean; locales_present: string[] };
  readiness_for_editorial: boolean;
  readiness_for_editorial_package: boolean;
  translation_assignments: TranslationAssignment[];
  content_confirmations: ContentConfirmation[];
  bilingual_reconciliations: BilingualReconciliation[];
};

export type WorkspaceListResponse = {
  items: WorkspaceSummary[];
  total: number;
  limit: number;
  offset: number;
};

export type DocumentSummary = {
  document_id: number;
  workspace_id: number;
  document_kind: string;
  status: string;
  created_from_workspace_version: number;
  created_from_workspace_fingerprint: string;
  promotion_id: number;
  created_at: string;
  created_by_user_id: number;
  version: number;
  submitting_org_unit_id: number | null;
  ready_for_signature_at: string | null;
  ready_for_signature_by_user_id: number | null;
};

export type DocumentVersion = {
  id: number;
  document_id: number;
  version_number: number;
  workspace_version: number;
  promotion_snapshot_version: number;
  snapshot_fingerprint: string;
  is_current: boolean;
  created_at: string;
  created_by_user_id: number;
};

export type SigningAuthority = {
  id: number;
  document_id: number;
  document_version_id: number;
  authority_party_type: string;
  authority_party_reference: string;
  authority_display_name: string | null;
  authority_position_id: number | null;
  authority_org_unit_id: number | null;
  authority_basis: string | null;
  assigned_by_user_id: number;
  status: string;
  assigned_at: string;
  superseded_at: string | null;
  version: number;
};

export type LifecycleAudit = {
  id: number;
  document_id: number;
  document_version_id: number | null;
  transition_from: string | null;
  transition_to: string | null;
  action: string;
  actor_user_id: number | null;
  reason: string | null;
  created_at: string;
  document_version_before: number | null;
  document_version_after: number | null;
};

export type DocumentLocalization = {
  id: number;
  document_version_id: number;
  locale: string;
  block_type: string;
  sequence: number;
  official_text: string;
  content_fingerprint: string;
  source_workspace_block_version: number;
  source_confirmation_ids: number[];
  source_reconciliation_id: number | null;
  created_at: string;
};

export type PromotionSummary = {
  id: number;
  workspace_id: number;
  document_id: number | null;
  status: string;
  workspace_version: number;
  workspace_fingerprint: string;
  snapshot_fingerprint: string | null;
  snapshot_version: number;
  promoted_by_user_id: number;
  promoted_at: string | null;
  created_at: string;
};

export type DocumentDetail = {
  document: DocumentSummary;
  current_version: DocumentVersion | null;
  promotion: PromotionSummary | null;
  signing_authority: SigningAuthority | null;
  readiness_validation: ValidationResult | null;
  latest_lifecycle_transition: LifecycleAudit | null;
  org_scope_source: { submitting_org_unit_id?: number | null; workspace_id: number } | null;
  workspace_drift_detected: boolean;
  revision_recommended: boolean;
};

export type DocumentListResponse = {
  items: DocumentSummary[];
  total: number;
  limit: number;
  offset: number;
};

export type PromotionResult = {
  workspace_id: number;
  document: DocumentDetail;
  validation: ValidationResult;
  idempotent_replay: boolean;
  workspace_frozen: boolean;
  workspace_drift_detected: boolean;
  revision_recommended: boolean;
  document_id: number | null;
  promotion_id: number | null;
};

export type EditorialPackageValidation = {
  workspace_id: number;
  validation: ValidationResult;
};

export type SignatureReadiness = {
  document_id: number;
  status: string;
  aggregate_version: number;
  signing_authority: SigningAuthority | null;
  readiness_validation: ValidationResult;
  workspace_drift_detected: boolean;
  revision_recommended: boolean;
};

export type ReadyForSignatureResult = {
  document: DocumentDetail;
  validation: ValidationResult;
  idempotent_replay: boolean;
};

export type ReturnToCreatedResult = {
  document: DocumentDetail;
  idempotent_replay: boolean;
};

export type SigningAuthorityResult = {
  document_id: number;
  signing_authority: SigningAuthority | null;
  document: DocumentSummary | null;
  idempotent_replay: boolean;
};

export type OperationalOrdersPermissions = {
  intake_create?: boolean;
  intake_read?: boolean;
  intake_operate?: boolean;
  translation_assign?: boolean;
  translation_work?: boolean;
  content_confirm?: boolean;
  reconcile?: boolean;
  editorial_ready?: boolean;
  promote?: boolean;
  signature_readiness_read?: boolean;
  assign_signing_authority?: boolean;
  mark_ready_for_signature?: boolean;
  return_from_signature?: boolean;
};
