/** TypeScript types matching R7 PPR Query API response schemas. */

export type PprIdentityResponse = {
  requested_person_id: number | null;
  requested_employee_id: number | null;
  resolved_person_id: number;
  merge_redirected: boolean;
  merge_chain: number[];
  employee_context_id: number | null;
  person_status: string;
  match_key: string;
  iin: string | null;
};

export type PprMaterializationResponse = {
  materialized: boolean;
  lifecycle_state: string;
  hr_relationship_context: string | null;
  envelope_version: number | null;
  created_at: string | null;
  updated_at: string | null;
};

export type PprGeneralResponse = {
  full_name: string;
  last_name: string | null;
  first_name: string | null;
  middle_name: string | null;
  birth_date: string | null;
  iin: string | null;
  created_at: string;
  updated_at: string;
};

export type PprEducationRecordResponse = {
  record_id: number | null;
  education_kind: string;
  institution_type: string | null;
  institution_name: string | null;
  specialty: string | null;
  qualification: string | null;
  started_at: string | null;
  completed_at: string | null;
  diploma_number: string | null;
  document_date: string | null;
  verification_status: string;
  lifecycle_status: string;
};

export type PprTrainingRecordResponse = {
  record_id: number | null;
  training_kind: string;
  title: string | null;
  organization_name: string | null;
  hours: string | number | null;
  started_at: string | null;
  completed_at: string | null;
  certificate_number: string | null;
  document_date: string | null;
  verification_status: string;
  lifecycle_status: string;
};

export type PprRelativeRecordResponse = {
  record_id: number | null;
  relationship_type: string;
  relationship_label: string | null;
  full_name: string;
  birth_date: string | null;
  birth_place: string | null;
  organization_name: string | null;
  residence_address: string | null;
  notes: string | null;
  verification_status: string;
  lifecycle_status: string;
};

export type PprExternalEmploymentRecordResponse = {
  record_id: number | null;
  record_kind: string;
  employer_name: string | null;
  department_name: string | null;
  position_title: string | null;
  employment_type: string | null;
  started_at: string | null;
  ended_at: string | null;
  termination_reason: string | null;
  document_reference: string | null;
  source_system: string;
  source_id: string | null;
  provenance: Record<string, unknown> | null;
  notes: string | null;
  employee_context_id: number | null;
  verification_status: string;
  lifecycle_status: string;
  created_at: string | null;
  updated_at: string | null;
};

export type PprMilitaryRecordResponse = {
  record_id: number | null;
  record_kind: string;
  obligation_status: string | null;
  registration_category: string | null;
  military_rank: string | null;
  military_specialty_code: string | null;
  personnel_composition: string | null;
  fitness_category: string | null;
  registration_status: string | null;
  commissariat_name: string | null;
  registered_at: string | null;
  deregistered_at: string | null;
  notes: string | null;
  source_type: string;
  provenance: Record<string, unknown> | null;
  metadata: Record<string, unknown> | null;
  employee_context_id: number | null;
  verification_status: string;
  lifecycle_status: string;
  created_at: string | null;
  updated_at: string | null;
};

export type PprMilitaryRecordDetailsResponse = PprMilitaryRecordResponse & {
  military_id_book_series?: string | null;
  military_id_book_number?: string | null;
  registration_certificate_series?: string | null;
  registration_certificate_number?: string | null;
};

export type PprSectionRecordResponse =
  | PprEducationRecordResponse
  | PprTrainingRecordResponse
  | PprRelativeRecordResponse
  | PprExternalEmploymentRecordResponse
  | PprMilitaryRecordResponse
  | PprMilitaryRecordDetailsResponse;

export type PprSectionResponse = {
  section_code: string;
  active: PprSectionRecordResponse[];
  superseded: PprSectionRecordResponse[];
  voided: PprSectionRecordResponse[];
};

export type PprEventSummaryItemResponse = {
  event_id: number;
  event_type: string;
  category: string;
  record_table_name: string;
  record_id: number;
  occurred_at: string;
  section_code: string | null;
  domain_code: string | null;
};

export type PprEventSummaryResponse = {
  recent: PprEventSummaryItemResponse[];
  returned_count: number;
  limit: number;
};

export type PprReadMetadataResponse = {
  read_mode: string;
  source: string;
  generated_at: string;
  warnings: string[];
  transitional: boolean;
  merge_redirected: boolean;
  source_person_id: number;
  requested_input_kind: string | null;
  requested_input_id: number | null;
};

export type PprIntendedEmploymentResponse = {
  org_group_id: number | null;
  org_unit_id: number | null;
  position_id: number | null;
  employment_rate: number | null;
  org_group_name: string | null;
  org_unit_name: string | null;
  position_name: string | null;
};

export type PprHireDefaultsResponse = PprIntendedEmploymentResponse & {
  person_id: number;
};

export type PprCompositeReadResponse = {
  identity: PprIdentityResponse;
  materialization: PprMaterializationResponse;
  general: PprGeneralResponse;
  sections: Record<string, PprSectionResponse>;
  events: PprEventSummaryResponse | null;
  intended_employment: PprIntendedEmploymentResponse | null;
  metadata: PprReadMetadataResponse;
};

export type PprCompositeSummaryResponse = {
  identity: PprIdentityResponse;
  materialization: PprMaterializationResponse;
  full_name: string;
  education_active_count: number;
  training_active_count: number;
  family_active_count: number;
  external_employment_active_count: number;
  recent_event_count: number;
  metadata: PprReadMetadataResponse;
};

export const PPR_HR_RELATIONSHIP_CANDIDATE = "CANDIDATE";
export const PPR_HR_RELATIONSHIP_EMPLOYED = "EMPLOYED";
export const PPR_SECTION_CODE_EDUCATION = "PPR-EDUCATION";
export const PPR_SECTION_CODE_TRAINING = "PPR-TRAINING";
export const PPR_SECTION_CODE_FAMILY = "PPR-FAMILY";
export const PPR_SECTION_CODE_EMPLOYMENT_BIOGRAPHY = "PPR-EMPLOYMENT-BIOGRAPHY";
export const PPR_SECTION_CODE_MILITARY = "PPR-MILITARY";

export const PPR_MILITARY_RECORD_KIND_REGISTRATION = "registration";
export const PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE = "not_applicable";

export const PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_EPISODE = "episode";
export const PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_NARRATIVE_SUMMARY = "narrative_summary";
export const PPR_EXTERNAL_EMPLOYMENT_RECORD_KIND_ATTESTATION_NONE = "attestation_none";

export const PPR_LIFECYCLE_NOT_MATERIALIZED = "NOT_MATERIALIZED";
