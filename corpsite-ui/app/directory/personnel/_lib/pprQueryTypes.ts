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

export type PprSectionResponse = {
  section_code: string;
  active: Array<PprEducationRecordResponse | PprTrainingRecordResponse>;
  superseded: Array<PprEducationRecordResponse | PprTrainingRecordResponse>;
  voided: Array<PprEducationRecordResponse | PprTrainingRecordResponse>;
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
  recent_event_count: number;
  metadata: PprReadMetadataResponse;
};

export const PPR_HR_RELATIONSHIP_CANDIDATE = "CANDIDATE";
export const PPR_HR_RELATIONSHIP_EMPLOYED = "EMPLOYED";
export const PPR_SECTION_CODE_EDUCATION = "PPR-EDUCATION";
export const PPR_SECTION_CODE_TRAINING = "PPR-TRAINING";

export const PPR_LIFECYCLE_NOT_MATERIALIZED = "NOT_MATERIALIZED";
