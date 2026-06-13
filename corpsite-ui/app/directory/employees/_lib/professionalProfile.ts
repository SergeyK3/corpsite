// FILE: corpsite-ui/app/directory/employees/_lib/professionalProfile.ts
import type { ProfessionalDocumentRow } from "../../personnel/_lib/demoApi.client";

export type ProfessionalRiskLevel =
  | "OK"
  | "ATTENTION"
  | "URGENT"
  | "CRITICAL"
  | "INCOMPLETE";

export type ProfessionalProfileSummary = {
  mainSpecialty: string;
  category: string;
  riskLevel: ProfessionalRiskLevel;
  riskLabel: string;
  nearestExpiration: string | null;
  documents: ProfessionalDocumentRow[];
  available: boolean;
};

/** Demo: основные медицинские специальности (независимы от должности). */
export const DEMO_MAIN_SPECIALTIES = [
  "Врач-онколог",
  "Врач-хирург",
  "Врач-терапевт",
  "Медицинская сестра",
] as const;

export type DemoMainSpecialty = (typeof DEMO_MAIN_SPECIALTIES)[number];

/** Квалификационные категории врача (не типы документов). */
export const QUALIFICATION_CATEGORIES = [
  "Высшая категория",
  "Первая категория",
  "Вторая категория",
  "Без категории",
] as const;

export type QualificationCategory = (typeof QUALIFICATION_CATEGORIES)[number];

const RISK_ORDER: Record<string, number> = {
  EXPIRED: 0,
  EXPIRING_30: 1,
  EXPIRING_60: 2,
  MISSING: 3,
  VALID: 4,
};

export const RISK_META: Record<
  ProfessionalRiskLevel,
  { label: string; className: string }
> = {
  OK: {
    label: "Допуск в норме",
    className: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-200",
  },
  ATTENTION: {
    label: "Требует внимания",
    className: "bg-yellow-100 text-yellow-900 dark:bg-yellow-950/40 dark:text-yellow-200",
  },
  URGENT: {
    label: "Срочное продление",
    className: "bg-orange-100 text-orange-900 dark:bg-orange-950/40 dark:text-orange-200",
  },
  CRITICAL: {
    label: "Документ истёк",
    className: "bg-red-100 text-red-900 dark:bg-red-950/50 dark:text-red-200",
  },
  INCOMPLETE: {
    label: "Данные неполные",
    className: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  },
};

export const DOCUMENT_STATUS_META: Record<string, { label: string; className: string }> = {
  VALID: {
    label: "Действует",
    className: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-200",
  },
  EXPIRING_60: {
    label: "≤ 60 дней",
    className: "bg-yellow-100 text-yellow-900 dark:bg-yellow-950/40 dark:text-yellow-200",
  },
  EXPIRING_30: {
    label: "≤ 30 дней",
    className: "bg-orange-100 text-orange-900 dark:bg-orange-950/40 dark:text-orange-200",
  },
  EXPIRED: {
    label: "Истёк",
    className: "bg-red-100 text-red-900 dark:bg-red-950/50 dark:text-red-200",
  },
  MISSING: {
    label: "Нет данных",
    className: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  },
};

/** Summary card order for the documents register. */
export const DOCUMENT_STATUS_SUMMARY_ORDER = [
  "EXPIRED",
  "EXPIRING_30",
  "EXPIRING_60",
  "VALID",
  "MISSING",
] as const;

export function countDocumentsByStatus(
  items: ProfessionalDocumentRow[]
): Record<string, number> {
  const counts: Record<string, number> = {
    EXPIRED: 0,
    EXPIRING_30: 0,
    EXPIRING_60: 0,
    VALID: 0,
    MISSING: 0,
  };
  for (const row of items) {
    const key = String(row.status || "").toUpperCase();
    if (key in counts) counts[key] += 1;
  }
  return counts;
}

function worstDocumentStatus(documents: ProfessionalDocumentRow[]): string {
  if (!documents.length) return "MISSING";
  return documents.reduce((worst, row) => {
    const status = String(row.status || "").toUpperCase();
    const currentRank = RISK_ORDER[status] ?? 99;
    const worstRank = RISK_ORDER[worst] ?? 99;
    return currentRank < worstRank ? status : worst;
  }, "VALID");
}

function mapDocumentStatusToRisk(status: string): ProfessionalRiskLevel {
  switch (status) {
    case "EXPIRED":
      return "CRITICAL";
    case "EXPIRING_30":
      return "URGENT";
    case "EXPIRING_60":
      return "ATTENTION";
    case "MISSING":
      return "INCOMPLETE";
    default:
      return "OK";
  }
}

function nearestExpirationIso(documents: ProfessionalDocumentRow[]): string | null {
  const dates = documents
    .map((d) => d.expires_at)
    .filter((v): v is string => Boolean(v))
    .sort((a, b) => new Date(a).getTime() - new Date(b).getTime());
  return dates[0] ?? null;
}

function hasRegisteredDocuments(documents: ProfessionalDocumentRow[]): boolean {
  return documents.some((d) => d.certificate_id != null);
}

/** Demo: основная специальность — независима от должности (заведующий может быть врачом-онкологом). */
function inferMainSpecialty(employeeId: number): DemoMainSpecialty {
  const demoByEmployee: Record<number, DemoMainSpecialty> = {
    1: "Врач-онколог",
    2: "Врач-хирург",
    3: "Врач-терапевт",
    4: "Медицинская сестра",
  };

  if (demoByEmployee[employeeId]) {
    return demoByEmployee[employeeId];
  }

  return DEMO_MAIN_SPECIALTIES[Math.abs(employeeId) % DEMO_MAIN_SPECIALTIES.length];
}

/** Demo: квалификационная категория врача — отдельно от типов документов и должности. */
function inferQualificationCategory(
  employeeId: number,
  documents: ProfessionalDocumentRow[],
  mainSpecialty: DemoMainSpecialty
): QualificationCategory {
  if (mainSpecialty === "Медицинская сестра") {
    return "Без категории";
  }

  if (!hasRegisteredDocuments(documents)) {
    return "Без категории";
  }

  const demoByEmployee: Record<number, QualificationCategory> = {
    1: "Высшая категория",
    2: "Первая категория",
    3: "Вторая категория",
    4: "Без категории",
  };

  if (demoByEmployee[employeeId]) {
    return demoByEmployee[employeeId];
  }

  const tiers: QualificationCategory[] = [
    "Высшая категория",
    "Первая категория",
    "Вторая категория",
  ];
  return tiers[Math.abs(employeeId) % tiers.length];
}

export function buildProfessionalProfileSummary(args: {
  employeeId: number;
  documents: ProfessionalDocumentRow[];
  available: boolean;
}): ProfessionalProfileSummary {
  const employeeDocuments = args.documents.filter((d) => d.employee_id === args.employeeId);
  const worst = worstDocumentStatus(employeeDocuments);
  const riskLevel = mapDocumentStatusToRisk(worst);
  const mainSpecialty = inferMainSpecialty(args.employeeId);

  return {
    mainSpecialty,
    category: inferQualificationCategory(args.employeeId, employeeDocuments, mainSpecialty),
    riskLevel,
    riskLabel: RISK_META[riskLevel].label,
    nearestExpiration: nearestExpirationIso(employeeDocuments),
    documents: employeeDocuments,
    available: args.available,
  };
}

/** Register row enrichment — same source as EmployeeDrawer professional profile. */
export function getEmployeeProfessionalContext(
  employeeId: number,
  allDocuments: ProfessionalDocumentRow[]
): Pick<ProfessionalProfileSummary, "mainSpecialty" | "category"> {
  const profile = buildProfessionalProfileSummary({
    employeeId,
    documents: allDocuments,
    available: true,
  });
  return {
    mainSpecialty: profile.mainSpecialty,
    category: profile.category,
  };
}

/** Statuses that need management attention (demo register quick filter). */
export const PROBLEMATIC_DOCUMENT_STATUSES = new Set([
  "EXPIRED",
  "EXPIRING_30",
  "EXPIRING_60",
  "MISSING",
]);

export type DocumentQuickFilter =
  | ""
  | "ALL"
  | "PROBLEMATIC"
  | "EXPIRED"
  | "EXPIRING_30"
  | "EXPIRING_60"
  | "MISSING";

export const DOCUMENT_QUICK_FILTERS: { value: DocumentQuickFilter; label: string }[] = [
  { value: "ALL", label: "Все" },
  { value: "PROBLEMATIC", label: "Проблемные" },
  { value: "EXPIRED", label: "Истёк" },
  { value: "EXPIRING_30", label: "≤ 30 дней" },
  { value: "EXPIRING_60", label: "≤ 60 дней" },
  { value: "MISSING", label: "Нет данных" },
];

export function matchesDocumentQuickFilter(
  status: string,
  quickFilter: DocumentQuickFilter
): boolean {
  if (!quickFilter || quickFilter === "ALL") return true;
  const key = String(status || "").toUpperCase();
  if (quickFilter === "PROBLEMATIC") return PROBLEMATIC_DOCUMENT_STATUSES.has(key);
  return key === quickFilter;
}

export function fmtProfileDate(v: string | null | undefined): string {
  if (!v) return "—";
  const dt = new Date(v);
  if (Number.isNaN(dt.getTime())) return v;
  return dt.toLocaleDateString("ru-RU");
}
