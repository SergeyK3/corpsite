# WP-PPR-MIG-005D — Matrix navigation UI

| Status | **Completed — Ready for WP-PPR-MIG-005E** |
|---|---|
| Route | `/directory/personnel/migration-status` |
| Read access | `PPR_MIGRATION_STATUS_READ`, projected by `/auth/me` as `has_ppr_migration_status_read` |

The route consumes only the WP-005C `GET` endpoints. Its refresh control repeats those reads and shows the selected universe `calculated_at`; it does not rebuild projection or call any mutation.

The matrix keeps `universe_id`, filters and page in the URL. A single available universe is selected automatically; several require explicit selection. The server remains authoritative for BASE/supplemental membership, pagination, filtering and status/reason labels. Each returned person has text-first `general`, `education` and `training` cells, with accessible link labels and titles.

Card links use `buildPprMigrationCardHref`, which permits only PPR section identifiers and uses the existing relative-only `normalizeReturnTo` guard. The encoded `return_to` preserves the report URL state. WP-005E card badges, rebuild actions and manual correction events are intentionally excluded.

## Verification

Targeted TypeScript verification used a temporary, untracked `tsconfig` outside the repository. It extended the frontend configuration and listed the WP-005D production files; it passed with no errors. Targeted frontend tests passed (14), and the `/auth/me` exact-capability contract passed (2). ESLint for changed frontend files and `git diff --check` passed. The production build compiled successfully.

The repository-wide `npx tsc --noEmit --pretty false` still reports 129 pre-existing errors. None refer to `MigrationStatusMatrixPageClient`, `migrationStatusApi.client`, the `migration-status` page, `employeeCardNav`, `PersonnelLk`, the new capability projection, or WP-005D tests. The unrelated technical debt is concentrated in admin org units; employees; operational orders; personnel import, orders and PPR migration tests; intake; regular tasks; and legacy `lib` tests. It was recorded but deliberately not changed in this WP.
