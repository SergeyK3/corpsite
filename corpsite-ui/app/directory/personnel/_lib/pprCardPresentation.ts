import type { APIError } from "@/lib/types";

export type PprCardErrorKind =
  | "access_denied"
  | "not_found"
  | "identity_conflict"
  | "network"
  | "unknown";

export type PprCardErrorView = {
  kind: PprCardErrorKind;
  message: string;
  retryable: boolean;
};

const ACCESS_DENIED =
  "У вас нет доступа к личной карточке этого сотрудника.";
const NOT_FOUND = "Сотрудник или личная карточка не найдены.";
const IDENTITY_CONFLICT =
  "Не удалось определить кадровую запись сотрудника. Обратитесь к администратору или кадровой службе.";
const NETWORK = "Не удалось загрузить личную карточку. Проверьте соединение и повторите попытку.";
const UNKNOWN = "Не удалось загрузить личную карточку.";

export function mapPprCardError(error: unknown): PprCardErrorView {
  if (error instanceof TypeError) {
    return { kind: "network", message: NETWORK, retryable: true };
  }

  const api = error as Partial<APIError>;
  const status = typeof api.status === "number" ? api.status : undefined;

  if (status === 403) {
    return { kind: "access_denied", message: ACCESS_DENIED, retryable: false };
  }
  if (status === 404) {
    return { kind: "not_found", message: NOT_FOUND, retryable: false };
  }
  if (status === 409) {
    return { kind: "identity_conflict", message: IDENTITY_CONFLICT, retryable: false };
  }
  if (status === 401) {
    return { kind: "access_denied", message: ACCESS_DENIED, retryable: false };
  }

  return { kind: "unknown", message: UNKNOWN, retryable: true };
}

export function pprEventTypeLabel(eventType: string): string {
  const map: Record<string, string> = {
    PPR_CREATED: "Личная карточка сформирована",
    PPR_LIFECYCLE_CHANGED: "Изменён статус личной карточки",
    PPR_ENVELOPE_UPDATED: "Обновлены служебные сведения личной карточки",
    PPR_SECTION_ADDED: "Добавлена запись",
    PPR_SECTION_UPDATED: "Изменена запись",
    PPR_SECTION_VOIDED: "Запись аннулирована",
    PPR_SECTION_SUPERSEDED: "Запись заменена",
    EDUCATION_MIGRATED: "Добавлена запись об образовании",
    EDUCATION_VOIDED: "Запись об образовании аннулирована",
    EDUCATION_SUPERSEDED: "Запись об образовании заменена",
  };
  return map[eventType] || eventType;
}

export function hrRelationshipLabel(value: string | null | undefined): string {
  const map: Record<string, string> = {
    EMPLOYED: "Работает",
    FORMER_EMPLOYEE: "Бывший сотрудник",
    CANDIDATE: "Заявитель",
    UNKNOWN: "Не определено",
  };
  if (!value) return "—";
  return map[value] || value;
}

export function lifecycleStatusLabel(materialized: boolean, lifecycleState: string): string {
  if (!materialized || lifecycleState === "NOT_MATERIALIZED") {
    return "Не сформирована полностью";
  }
  const map: Record<string, string> = {
    CREATED: "Сформирована",
    COLLECTING: "Сбор сведений",
    READY: "Готова к активации",
    ACTIVE: "Активна",
    ARCHIVED: "В архиве",
    MERGED: "Объединена",
  };
  return map[lifecycleState] || lifecycleState;
}

export function formatPprDate(value: string | null | undefined): string {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleDateString("ru-RU");
}

export function formatPprDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString("ru-RU");
}

const RELATIONSHIP_TYPE_LABELS: Record<string, string> = {
  father: "Отец",
  mother: "Мать",
  brother: "Брат",
  sister: "Сестра",
  son: "Сын",
  daughter: "Дочь",
  spouse: "Супруг(а)",
  other_close: "Иной близкий родственник",
};

export function relationshipTypeLabel(value: string | null | undefined): string {
  if (!value) return "—";
  return RELATIONSHIP_TYPE_LABELS[value] || value;
}
