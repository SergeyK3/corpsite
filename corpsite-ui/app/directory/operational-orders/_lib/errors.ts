import { formatThrownError } from "@/lib/i18n";

const OO_ERROR_MESSAGES: Record<string, string> = {
  OO_WORKSPACE_FROZEN: "Рабочее пространство уже заморожено",
  OO_DOCUMENT_VERSION_CONFLICT: "Документ изменился. Обновите страницу",
  OO_WORKSPACE_VERSION_CONFLICT: "Рабочее пространство изменилось. Обновите страницу",
  OO_PROMOTION_VERSION_CONFLICT: "Рабочее пространство изменилось. Обновите страницу",
  OO_DOCUMENT_NOT_READY_FOR_SIGNATURE: "Документ не прошёл проверку готовности",
  OO_REVISION_REQUIRED: "Требуется создание новой редакции",
  OO_SIGNING_AUTHORITY_INVALID: "Некорректно назначен подписант",
  OO_DOCUMENT_SCOPE_FORBIDDEN: "Нет доступа к документу",
  OO_FORBIDDEN: "Недостаточно прав",
  OO_WORKSPACE_NOT_FOUND: "Рабочее пространство не найдено",
  OO_DOCUMENT_NOT_FOUND: "Документ не найден",
  OO_VALIDATION_BLOCKED: "Операция заблокирована проверкой",
  OO_CONFIRMATION_PARTY_MISMATCH: "Подтверждающая сторона не соответствует роли",
};

type ApiErrorBody = {
  code?: string;
  message?: string;
  detail?: unknown;
};

function extractCode(body: unknown): string | undefined {
  if (!body || typeof body !== "object") return undefined;
  const obj = body as ApiErrorBody;
  if (typeof obj.code === "string") return obj.code;
  if (obj.detail && typeof obj.detail === "object") {
    const detail = obj.detail as ApiErrorBody;
    if (typeof detail.code === "string") return detail.code;
  }
  return undefined;
}

export function mapOperationalOrdersApiError(err: unknown, fallback: string): string {
  const e = err as { status?: number; details?: unknown; body?: unknown; detail?: unknown };
  const status = Number(e.status ?? 0);
  const body = e.details ?? e.body ?? e.detail;
  const code = extractCode(body);

  if (code && OO_ERROR_MESSAGES[code]) {
    return OO_ERROR_MESSAGES[code];
  }

  if (status === 401) return "Требуется повторная авторизация";
  if (status === 403) return "Недостаточно прав";
  if (status === 404) return "Объект не найден";
  if (status === 409) return "Конфликт версии или состояния. Обновите страницу";
  if (status >= 500) return "Техническая ошибка";

  return formatThrownError(err, { fallback });
}

export function isVersionConflictError(err: unknown): boolean {
  const e = err as { status?: number; details?: unknown; body?: unknown; detail?: unknown };
  const body = e.details ?? e.body ?? e.detail;
  const code = extractCode(body);
  return (
    e.status === 409 &&
    (code === "OO_DOCUMENT_VERSION_CONFLICT" ||
      code === "OO_WORKSPACE_VERSION_CONFLICT" ||
      code === "OO_PROMOTION_VERSION_CONFLICT")
  );
}

export function extractDiagnosticDetail(err: unknown): string | null {
  const e = err as { details?: unknown; body?: unknown; detail?: unknown };
  const body = e.details ?? e.body ?? e.detail;
  if (!body) return null;
  try {
    return typeof body === "string" ? body : JSON.stringify(body, null, 2);
  } catch {
    return String(body);
  }
}
