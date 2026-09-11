import type { MeInfo } from "./types";

export function canReadPprMigrationStatus(me: MeInfo | null | undefined): boolean {
  return me?.has_ppr_migration_status_read === true;
}
