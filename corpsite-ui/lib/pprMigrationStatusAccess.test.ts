import { describe, expect, it } from "vitest";
import { canReadPprMigrationStatus } from "./pprMigrationStatusAccess";

describe("canReadPprMigrationStatus", () => {
  it("shows the LK link only for the exact read grant projection", () => {
    expect(canReadPprMigrationStatus({ has_ppr_migration_status_read: true })).toBe(true);
    expect(canReadPprMigrationStatus({ is_privileged: true })).toBe(false);
    expect(canReadPprMigrationStatus(null)).toBe(false);
  });
});
