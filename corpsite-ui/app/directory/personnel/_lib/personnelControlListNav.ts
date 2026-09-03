export type PersonnelControlListSection =
  | "upload"
  | "analytics"
  | "review"
  | "changes"
  | "migration"
  | "medical"
  | "export";

const PERSONNEL_ROOT = "/directory/personnel";
const IMPORT_ROOT = `${PERSONNEL_ROOT}/import`;

export function isPersonnelControlListPath(pathname: string): boolean {
  return (
    pathname === IMPORT_ROOT ||
    pathname.startsWith(`${IMPORT_ROOT}/`) ||
    pathname === `${PERSONNEL_ROOT}/baselines` ||
    pathname.startsWith(`${PERSONNEL_ROOT}/baselines/`) ||
    pathname === `${PERSONNEL_ROOT}/monthly-references` ||
    pathname.startsWith(`${PERSONNEL_ROOT}/monthly-references/`) ||
    pathname === `${PERSONNEL_ROOT}/hr-change-events` ||
    pathname.startsWith(`${PERSONNEL_ROOT}/hr-change-events/`) ||
    pathname === `${PERSONNEL_ROOT}/migration` ||
    pathname.startsWith(`${PERSONNEL_ROOT}/migration/`) ||
    pathname === `${PERSONNEL_ROOT}/control-list/export`
  );
}

export function parsePersonnelImportBatchId(pathname: string): number | null {
  const match = pathname.match(/^\/directory\/personnel\/import\/(\d+)(?:\/|$)/);
  if (!match) return null;
  const batchId = Number(match[1]);
  return Number.isSafeInteger(batchId) && batchId > 0 ? batchId : null;
}

export function resolvePersonnelControlListSection(pathname: string): PersonnelControlListSection | null {
  if (!isPersonnelControlListPath(pathname)) return null;
  if (pathname === `${PERSONNEL_ROOT}/control-list/export`) return "export";
  if (
    pathname === `${PERSONNEL_ROOT}/hr-change-events` ||
    pathname.startsWith(`${PERSONNEL_ROOT}/hr-change-events/`)
  ) {
    return "changes";
  }
  if (pathname === `${PERSONNEL_ROOT}/migration` || pathname.startsWith(`${PERSONNEL_ROOT}/migration/`)) {
    return "migration";
  }
  if (pathname === `${IMPORT_ROOT}/review` || pathname.startsWith(`${IMPORT_ROOT}/review/`)) {
    return "review";
  }

  const batchId = parsePersonnelImportBatchId(pathname);
  if (batchId != null) {
    const batchRoot = `${IMPORT_ROOT}/${batchId}`;
    if (pathname === `${batchRoot}/review` || pathname.startsWith(`${batchRoot}/review/`)) {
      return "medical";
    }
    return "analytics";
  }
  return "upload";
}
