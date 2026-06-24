export function resolveTaskStatusCode(src: unknown): string {
  if (!src || typeof src !== "object") return "";

  const task = src as Record<string, unknown>;
  const code = String(task.status_code ?? "").trim().toUpperCase();
  if (code) return code;

  const legacy = String(task.status ?? "").trim().toUpperCase();
  if (legacy) return legacy;

  const nameRu = String(task.status_name_ru ?? "").trim().toLowerCase();
  if (nameRu === "ожидает согласование") return "WAITING_APPROVAL";

  return "";
}

export type TaskEditOptions = {
  isSystemAdmin?: boolean;
};

export function canEditTask(src: unknown, options?: TaskEditOptions): boolean {
  if (!src || typeof src !== "object") return false;

  const task = src as Record<string, unknown>;
  const taskKind = String(task.task_kind ?? "").trim().toLowerCase();
  const statusCode = resolveTaskStatusCode(src);
  const isSystemAdmin = Boolean(options?.isSystemAdmin);

  if (statusCode === "ARCHIVED") return false;
  if (statusCode === "WAITING_APPROVAL") return false;

  if (taskKind === "regular") {
    if (isSystemAdmin) return true;
    if (statusCode === "WAITING_REPORT") return false;
    return true;
  }

  return taskKind === "adhoc";
}

export function isTaskRowEditable(
  src: unknown,
  options: { readOnlyTeamMode: boolean; isSystemAdmin?: boolean },
): boolean {
  return (
    canEditTask(src, { isSystemAdmin: options.isSystemAdmin }) && !options.readOnlyTeamMode
  );
}

export function editButtonTitle(src: unknown): string {
  if (!src || typeof src !== "object") return "Сначала выберите задачу";

  const task = src as Record<string, unknown>;
  const taskKind = String(task.task_kind ?? "").trim().toLowerCase();
  const statusCode = resolveTaskStatusCode(src);

  if (statusCode === "ARCHIVED") return "Архивная задача не редактируется";
  if (statusCode === "WAITING_APPROVAL") return "Задача на согласовании — редактирование недоступно";
  if (taskKind === "adhoc" || taskKind === "regular") return "Редактировать выбранную задачу";
  return "Этот тип задачи не поддерживает редактирование";
}
