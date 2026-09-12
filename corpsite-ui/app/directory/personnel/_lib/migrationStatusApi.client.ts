import { apiFetchJson } from "@/lib/api";

export const MIGRATION_STATUS_PATH = "/directory/personnel/migration-status";
/** Ordered server-side PPR migration-status catalog (WP-PPR-MIG-005G-A/B). */
export type MigrationSection =
  | "general"
  | "education"
  | "training"
  | "relatives"
  | "military"
  | "employment_biography"
  | "employment_history"
  | "foreign_languages"
  | "additional"
  | "awards"
  | "academic_degrees_titles";
export type MigrationUniverse = { universe_id: number; base_cohort_run_id: number; supplemental_cohort_run_ids: number[]; calculated_at: string };
export type MigrationCell = { status_code: string; status_label: string; reason_code: string; reason_label: string; calculated_at: string; stage_run_id?: number | null; stage1_run_id?: number | null; stage_participant_id?: number | null; stage1_participant_id?: number | null; pmf_run_id?: number | null };
export type MigrationGeneralSummary = {
  total_active_employees: number;
  processed: number;
  review_required: number;
  updated_current_run: number;
  skipped_already_filled: number;
};
export type MigrationPresentationSection = { code: string; title: string; order: number };
export type MigrationPresentationStatus = { code: string; title: string; order: number };
export type MigrationStatusSummary = { sections: MigrationPresentationSection[]; statuses: MigrationPresentationStatus[]; counts: Array<{ section_code: string; status_code: string; count: number }> };
export type MigrationMatrix = { universe_id: number; page: number; page_size: number; total: number; items: Array<{ person_id: number; employee_context_id: number; org_group_id?: number | null; org_group_name?: string | null; org_unit_id: number | null; org_unit_name?: string | null; position_id?: number | null; position_name?: string | null; full_name: string; cells: Partial<Record<MigrationSection, MigrationCell>> }>; counts: Array<{ section_code: MigrationSection; status_code: string; status_label: string; count: number }>; general_summary?: MigrationGeneralSummary; status_summary?: MigrationStatusSummary };
export type MigrationMatrixParams = { universe_id: number; page?: number; page_size?: number; section?: MigrationSection; status?: string; reason?: string; org_group_id?: number; org_unit_id?: number; position_id?: number; q?: string };

export function listMigrationStatusUniverses(): Promise<{ items: MigrationUniverse[] }> {
  return apiFetchJson(`${MIGRATION_STATUS_PATH}/universes`);
}

export function getMigrationStatusMatrix(params: MigrationMatrixParams): Promise<MigrationMatrix> {
  return apiFetchJson(MIGRATION_STATUS_PATH, { query: params });
}

export function getPersonMigrationStatus(personId: number, universeId: number): Promise<{ universe_id: number; cells: Partial<Record<MigrationSection, MigrationCell>> }> {
  return apiFetchJson(`${MIGRATION_STATUS_PATH}/persons/${personId}`, { query: { universe_id: universeId } });
}
