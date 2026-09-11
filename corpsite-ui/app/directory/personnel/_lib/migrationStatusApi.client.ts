import { apiFetchJson } from "@/lib/api";

export const MIGRATION_STATUS_PATH = "/directory/personnel/migration-status";
export type MigrationSection = "general" | "education" | "training";
export type MigrationUniverse = { universe_id: number; base_cohort_run_id: number; supplemental_cohort_run_ids: number[]; calculated_at: string };
export type MigrationCell = { status_code: string; status_label: string; reason_code: string; reason_label: string; calculated_at: string; stage_run_id?: number | null; stage1_run_id?: number | null; stage_participant_id?: number | null; stage1_participant_id?: number | null; pmf_run_id?: number | null };
export type MigrationMatrix = { universe_id: number; page: number; page_size: number; total: number; items: Array<{ person_id: number; employee_context_id: number; org_unit_id: number | null; full_name: string; cells: Partial<Record<MigrationSection, MigrationCell>> }>; counts: Array<{ section_code: MigrationSection; status_code: string; status_label: string; count: number }> };
export type MigrationMatrixParams = { universe_id: number; page?: number; page_size?: number; section?: MigrationSection; status?: string; reason?: string; org_unit_id?: number; q?: string };

export function listMigrationStatusUniverses(): Promise<{ items: MigrationUniverse[] }> {
  return apiFetchJson(`${MIGRATION_STATUS_PATH}/universes`);
}

export function getMigrationStatusMatrix(params: MigrationMatrixParams): Promise<MigrationMatrix> {
  return apiFetchJson(MIGRATION_STATUS_PATH, { query: params });
}

export function getPersonMigrationStatus(personId: number, universeId: number): Promise<{ universe_id: number; cells: Partial<Record<MigrationSection, MigrationCell>> }> {
  return apiFetchJson(`${MIGRATION_STATUS_PATH}/persons/${personId}`, { query: { universe_id: universeId } });
}
