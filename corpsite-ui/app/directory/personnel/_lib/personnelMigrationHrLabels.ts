// PMF-4B.1 — HR-facing copy for Migration Wizard (no technical terms).

import type { MigrationDomainRow } from "./personnelMigrationApi.client";

export const MIGRATION_HERO_TITLE = "Перенос проверенных данных в кадровую карточку";

export const MIGRATION_HERO_DESCRIPTION =
  "Используйте этот раздел после проверки импортированных записей. Здесь вы переносите одобренные данные из импорта в постоянную кадровую карточку сотрудника.";

export const MIGRATION_REVIEW_LINK_HREF = "/directory/personnel/import/review";

export const MIGRATION_REVIEW_LINK_LABEL = "Проверка записей";

export type MigrationProcessStepId = "import" | "review" | "transfer" | "personal_file";

export type MigrationProcessStep = {
  id: MigrationProcessStepId;
  title: string;
  href: string | null;
};

export const MIGRATION_PROCESS_STEPS: MigrationProcessStep[] = [
  { id: "import", title: "Импорт", href: "/directory/personnel/import" },
  { id: "review", title: "Проверка записей", href: MIGRATION_REVIEW_LINK_HREF },
  { id: "transfer", title: "Перенос в кадровую карточку", href: null },
  { id: "personal_file", title: "Личная карточка сотрудника", href: "/directory/staff" },
];

export const MIGRATION_CURRENT_STEP_ID: MigrationProcessStepId = "transfer";

export type MigrationNextStep = {
  number: number;
  title: string;
  description: string;
  available: boolean;
};

export const MIGRATION_NEXT_STEPS: MigrationNextStep[] = [
  {
    number: 1,
    title: "Выберите тип кадровых данных",
    description: "Укажите, какие сведения нужно перенести — например, образование.",
    available: true,
  },
  {
    number: 2,
    title: "Выберите сотрудника",
    description: "Будет доступно на следующем этапе.",
    available: false,
  },
  {
    number: 3,
    title: "Подтвердите перенос",
    description: "Проверьте данные и зафиксируйте их в кадровой карточке.",
    available: false,
  },
];

export type MigrationRoadmapItem = {
  label: string;
  status: "available" | "current" | "planned";
};

export const MIGRATION_ROADMAP_ITEMS: MigrationRoadmapItem[] = [
  { label: "Образование", status: "current" },
  { label: "Послужной список", status: "planned" },
  { label: "Сертификаты", status: "planned" },
  { label: "Категории", status: "planned" },
  { label: "Научные степени", status: "planned" },
  { label: "Награды", status: "planned" },
  { label: "Владение языками", status: "planned" },
  { label: "Повышение квалификации", status: "planned" },
];

/** HR-facing transfer scope per data type (domain_code). */
export function migrationHrTransferItems(domain: MigrationDomainRow): string[] {
  switch (domain.domain_code) {
    case "education":
      return ["дипломы", "специальности", "курсы повышения квалификации", "обучение"];
    default:
      if (domain.description?.trim()) {
        return [domain.description.trim()];
      }
      return ["кадровые сведения этого типа"];
  }
}

export type MigrationHrDomainStatus = "awaiting_enablement" | "available" | "coming_soon";

export function migrationHrDomainStatus(domain: MigrationDomainRow): MigrationHrDomainStatus {
  if (!domain.is_enabled) return "awaiting_enablement";
  if (domain.domain_code === "education") return "available";
  return "coming_soon";
}

export function migrationHrDomainStatusLabel(status: MigrationHrDomainStatus): string {
  switch (status) {
    case "awaiting_enablement":
      return "Ожидает включения";
    case "available":
      return "Доступен";
    case "coming_soon":
      return "Скоро";
    default:
      return "—";
  }
}

export function migrationHrDomainStatusHint(status: MigrationHrDomainStatus): string {
  switch (status) {
    case "awaiting_enablement":
      return "Раздел пока недоступен. Администратор включит его для pilot-запуска.";
    case "available":
      return "Можно начать перенос после выбора сотрудника (следующий этап).";
    case "coming_soon":
      return "Перенос этого типа данных будет добавлен позже.";
    default:
      return "";
  }
}

export function migrationHrDomainStatusBadgeClass(status: MigrationHrDomainStatus): string {
  switch (status) {
    case "available":
      return "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-200";
    case "coming_soon":
      return "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-200";
    default:
      return "border-zinc-200 bg-zinc-100 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400";
  }
}

export function migrationHrLoadError(message: string): string {
  const normalized = message.trim().toLowerCase();
  if (normalized === "not found" || normalized.includes("404")) {
    return "Сервис переноса временно недоступен. Обратитесь к системному администратору.";
  }
  if (normalized.includes("failed to fetch") || normalized.includes("network")) {
    return "Не удалось связаться с сервером. Проверьте подключение и повторите попытку.";
  }
  return message;
}

export function migrationHrEmptyStateTitle(): string {
  return "Типы кадровых данных не настроены";
}

export function migrationHrEmptyStateDescription(): string {
  return "Обратитесь к системному администратору для настройки переноса данных.";
}
