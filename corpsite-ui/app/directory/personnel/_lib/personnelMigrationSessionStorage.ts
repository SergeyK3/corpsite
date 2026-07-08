// PMF-4C — client-side draft run resume cache (until PMF-3C list runs API).

const STORAGE_PREFIX = "pmf:migration:draft-run:";

function storageKey(domainCode: string, employeeId: number): string {
  return `${STORAGE_PREFIX}${domainCode}:${employeeId}`;
}

export function readStoredDraftRunId(domainCode: string, employeeId: number): number | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(storageKey(domainCode, employeeId));
    if (!raw) return null;
    const id = Number(raw);
    return Number.isFinite(id) && id > 0 ? id : null;
  } catch {
    return null;
  }
}

export function writeStoredDraftRunId(domainCode: string, employeeId: number, runId: number): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(storageKey(domainCode, employeeId), String(runId));
  } catch {
    // ignore quota / private mode
  }
}

export function clearStoredDraftRunId(domainCode: string, employeeId: number): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(storageKey(domainCode, employeeId));
  } catch {
    // ignore
  }
}
