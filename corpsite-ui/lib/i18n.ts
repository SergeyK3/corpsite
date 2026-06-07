// FILE: corpsite-ui/lib/i18n.ts

export const TASK_STATUS_LABELS: Readonly<Record<string, string>> = {
  in_progress: "В работе",
  waiting_report: "Ожидает отчёт",
  waiting_approval: "Ожидает согласование",
  done: "Выполнено",
  rejected: "Отклонено",
  archived: "В архиве",
  active: "В работе",
};

export const TASK_ACTION_LABELS: Readonly<Record<string, string>> = {
  report: "Отправить отчёт",
  approve: "Согласовать",
  reject: "Отклонить",
  archive: "В архив",
};

export const TASK_SOURCE_LABELS: Readonly<Record<string, string>> = {
  manual: "Вручную",
  regular_task: "Регулярный шаблон",
  bot: "Telegram-бот",
  import: "Импорт",
};

export const SCHEDULE_TYPE_LABELS: Readonly<Record<string, string>> = {
  daily: "Ежедневно",
  weekly: "Еженедельно",
  monthly: "Ежемесячно",
  yearly: "Ежегодно",
};

export const RUN_STATUS_LABELS: Readonly<Record<string, string>> = {
  ok: "Успешно",
  partial: "Частично",
  error: "Ошибка",
  skip: "Пропущено",
};

const API_MESSAGE_LABELS: Readonly<Record<string, string>> = {
  "request failed": "Не удалось выполнить запрос",
  "backend did not return access_token": "Сервер не вернул токен доступа",

  "task not found": "Задача не найдена",
  "user not found": "Пользователь не найден",
  "employee not found.": "Сотрудник не найден",
  "access denied": "Доступ запрещён",

  "missing authorization: bearer token": "Требуется авторизация",
  "invalid or expired token": "Недействительный или просроченный токен",
  "invalid token subject": "Некорректный токен",

  "title is required": "Укажите название",
  "title cannot be empty": "Название не может быть пустым",
  "period_id is required": "Укажите отчётный период",
  "executor_role_id is required": "Укажите роль исполнителя",
  "report_link is required": "Укажите ссылку на отчёт",

  "only admin can run regular tasks": "Запуск доступен только администратору",
  "only admin can modify regular tasks": "Изменение доступно только администратору",
  "only admin can hard-delete tasks": "Удаление доступно только администратору",

  "this task cannot be edited": "Эту задачу нельзя редактировать",
  "only adhoc tasks can be edited": "Редактировать можно только разовые задачи",

  "failed to create manual task": "Не удалось создать задачу",
  "failed to create task": "Не удалось создать задачу",

  "unsupported schedule_type: yearly": "Тип расписания yearly не поддерживается",
};

const HTTP_STATUS_FALLBACKS: Readonly<Record<number, string>> = {
  400: "Некорректный запрос",
  401: "Требуется авторизация",
  403: "Недостаточно прав",
  404: "Объект не найден",
  409: "Конфликт данных",
  422: "Некорректные данные",
  500: "Ошибка сервера",
};

function isRecord(v: unknown): v is Record<string, unknown> {
  return !!v && typeof v === "object" && !Array.isArray(v);
}

function normalizeLookupKey(code: string): string {
  return String(code ?? "").trim().toLowerCase();
}

function lookupLabel(
  map: Readonly<Record<string, string>>,
  code: string | null | undefined,
  fallback?: string,
): string {
  const raw = String(code ?? "").trim();
  if (!raw) return fallback ?? "—";

  const key = normalizeLookupKey(raw);
  const hit = map[key] ?? map[raw.toUpperCase()] ?? map[raw];
  if (hit) return hit;

  return fallback ?? raw;
}

function translateKnownMessage(message: string): string {
  const raw = String(message ?? "").trim();
  if (!raw) return "";

  const key = normalizeLookupKey(raw);
  return API_MESSAGE_LABELS[key] ?? raw;
}

export function taskStatusLabel(
  code: string | null | undefined,
  options?: { fallback?: string },
): string {
  return lookupLabel(TASK_STATUS_LABELS, code, options?.fallback);
}

export function taskActionLabel(
  code: string | null | undefined,
  options?: { fallback?: string },
): string {
  return lookupLabel(TASK_ACTION_LABELS, code, options?.fallback);
}

export function taskSourceLabel(
  code: string | null | undefined,
  options?: { fallback?: string },
): string {
  return lookupLabel(TASK_SOURCE_LABELS, code, options?.fallback);
}

export function scheduleTypeLabel(
  code: string | null | undefined,
  options?: { fallback?: string },
): string {
  return lookupLabel(SCHEDULE_TYPE_LABELS, code, options?.fallback);
}

export function runStatusLabel(
  code: string | null | undefined,
  options?: { fallback?: string },
): string {
  return lookupLabel(RUN_STATUS_LABELS, code, options?.fallback);
}

export function taskActionsLabel(
  actions: readonly string[] | null | undefined,
  separator = " / ",
): string {
  if (!actions || actions.length === 0) return "—";
  return actions.map((a) => taskActionLabel(a)).join(separator);
}

export type FormatApiErrorOptions = {
  fallback?: string;
};

/**
 * body.message → словарь известных EN detail/error → HTTP fallback
 */
export function formatApiError(
  status: number,
  body: unknown,
  options?: FormatApiErrorOptions,
): string {
  const fallback =
    options?.fallback ??
    HTTP_STATUS_FALLBACKS[status] ??
    "Не удалось выполнить запрос";

  if (body == null) return fallback;

  if (typeof body === "string") {
    const translated = translateKnownMessage(body);
    return translated || fallback;
  }

  if (!isRecord(body)) return fallback;

  const structured = String(body.message ?? "").trim();
  if (structured) return structured;

  const detail = body.detail ?? body.error;

  if (typeof detail === "string") {
    const translated = translateKnownMessage(detail);
    return translated || fallback;
  }

  if (isRecord(detail)) {
    const nested = String(detail.message ?? detail.detail ?? "").trim();
    if (nested) return translateKnownMessage(nested) || fallback;
  }

  const loose = String(body.error ?? "").trim();
  if (loose) {
    const translated = translateKnownMessage(loose);
    return translated || fallback;
  }

  return fallback;
}
