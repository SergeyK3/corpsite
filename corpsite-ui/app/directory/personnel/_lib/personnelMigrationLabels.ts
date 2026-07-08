// PMF-4B — display labels for Personnel Migration Wizard shell.

import type { MigrationDomainRow } from "./personnelMigrationApi.client";

export type MigrationDomainReadiness = "disabled" | "pilot_ready" | "active";

export function migrationDomainEnabledLabel(isEnabled: boolean): string {
  return isEnabled ? "Включён" : "Отключён";
}

export function migrationDomainReadiness(domain: MigrationDomainRow): MigrationDomainReadiness {
  if (!domain.is_enabled) return "disabled";
  if (domain.domain_code === "education") return "pilot_ready";
  return "active";
}

export function migrationDomainReadinessLabel(readiness: MigrationDomainReadiness): string {
  switch (readiness) {
    case "disabled":
      return "Не готов";
    case "pilot_ready":
      return "Pilot (PMF-4G)";
    case "active":
      return "Активен";
    default:
      return "—";
  }
}

export function migrationDomainReadinessHint(readiness: MigrationDomainReadiness): string {
  switch (readiness) {
    case "disabled":
      return "Домен отключён в реестре PMF. Включение — через runbook pilot.";
    case "pilot_ready":
      return "Первый домен для pilot-миграции. UI сессии — PMF-4C.";
    case "active":
      return "Домен включён. Полный wizard — в следующих WP.";
    default:
      return "";
  }
}

export function migrationTargetTableCount(domain: MigrationDomainRow): number {
  return domain.target_table_names?.length ?? 0;
}

export function migrationDomainDescription(domain: MigrationDomainRow): string {
  if (domain.description?.trim()) return domain.description.trim();
  return "Описание домена не задано.";
}
