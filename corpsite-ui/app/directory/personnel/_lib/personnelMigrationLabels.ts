// PMF-4B.1 — technical labels (Technical Information block only).

import type { MigrationDomainRow } from "./personnelMigrationApi.client";

export function migrationTechnicalDomainCode(domain: MigrationDomainRow): string {
  return domain.domain_code;
}

export function migrationTechnicalTargetTables(domain: MigrationDomainRow): string[] {
  return domain.target_table_names ?? [];
}

export function migrationTechnicalControlListColumns(domain: MigrationDomainRow): string[] {
  return domain.control_list_columns ?? [];
}

export function migrationTechnicalRegistryEnabled(domain: MigrationDomainRow): boolean {
  return domain.is_enabled;
}

export function migrationTechnicalDescription(domain: MigrationDomainRow): string | null {
  return domain.description?.trim() || null;
}

export function migrationTechnicalRunStatus(status: string): string {
  return status.trim() || "—";
}
