// FILE: corpsite-ui/lib/taskNav.ts

export const TASK_PAGE_PATH = "/tasks";
export const TASK_ID_QUERY_PARAM = "task_id";
export const RETURN_TO_QUERY_PARAM = "return_to";

export type BuildTaskPageHrefOptions = {
  returnTo?: string | null;
};

export function buildTaskPageHref(
  taskId: number,
  options?: BuildTaskPageHrefOptions,
): string | null {
  const id = Math.trunc(Number(taskId));
  if (!Number.isFinite(id) || id <= 0) return null;

  const params = new URLSearchParams();
  params.set(TASK_ID_QUERY_PARAM, String(id));

  const returnTo = normalizeReturnTo(options?.returnTo);
  if (returnTo) {
    params.set(RETURN_TO_QUERY_PARAM, returnTo);
  }

  return `${TASK_PAGE_PATH}?${params.toString()}`;
}

export function parseTaskIdFromSearchParams(
  sp: Pick<URLSearchParams, "get">,
): number | null {
  const raw = String(sp.get(TASK_ID_QUERY_PARAM) ?? "").trim();
  const id = Number(raw);
  if (!Number.isFinite(id) || id <= 0) return null;
  return Math.trunc(id);
}

export function normalizeReturnTo(value: string | null | undefined): string | null {
  const raw = String(value ?? "").trim();
  if (!raw) return null;
  if (!raw.startsWith("/") || raw.startsWith("//")) return null;
  return raw;
}

export function parseReturnToFromSearchParams(
  sp: Pick<URLSearchParams, "get">,
): string | null {
  return normalizeReturnTo(sp.get(RETURN_TO_QUERY_PARAM));
}

export function removeTaskIdFromSearchParams(
  sp: Pick<URLSearchParams, "toString">,
): string {
  const params = new URLSearchParams(sp.toString());
  params.delete(TASK_ID_QUERY_PARAM);
  params.delete(RETURN_TO_QUERY_PARAM);
  const qs = params.toString();
  return qs ? `${TASK_PAGE_PATH}?${qs}` : TASK_PAGE_PATH;
}

export function resolveTaskDrawerCloseTarget(
  sp: Pick<URLSearchParams, "get" | "toString">,
): string {
  const returnTo = parseReturnToFromSearchParams(sp);
  if (returnTo) return returnTo;
  return removeTaskIdFromSearchParams(sp);
}
