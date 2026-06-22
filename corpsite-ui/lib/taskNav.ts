// FILE: corpsite-ui/lib/taskNav.ts

export const TASK_PAGE_PATH = "/tasks";
export const TASK_ID_QUERY_PARAM = "task_id";

export function buildTaskPageHref(taskId: number): string | null {
  const id = Math.trunc(Number(taskId));
  if (!Number.isFinite(id) || id <= 0) return null;
  return `${TASK_PAGE_PATH}?${TASK_ID_QUERY_PARAM}=${id}`;
}

export function parseTaskIdFromSearchParams(
  sp: Pick<URLSearchParams, "get">,
): number | null {
  const raw = String(sp.get(TASK_ID_QUERY_PARAM) ?? "").trim();
  const id = Number(raw);
  if (!Number.isFinite(id) || id <= 0) return null;
  return Math.trunc(id);
}
