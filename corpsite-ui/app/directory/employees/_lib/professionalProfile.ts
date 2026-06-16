// FILE: corpsite-ui/app/directory/employees/_lib/professionalProfile.ts
import type { EmployeeDocumentRow } from "../../personnel/_lib/documentsApi.client";

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
  documents: EmployeeDocumentRow[];
  available: boolean;
};

const RISK_ORDER: Record<string, number> = {
  EXPIRED: 0,
  EXPIRING_30: 1,
  EXPIRING_60: 2,
  VALID: 3,
  NO_EXPIRY: 4,
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
  NO_EXPIRY: {
    label: "Без срока",
    className: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  },
};

/** Summary card order for the documents register (ADR-037 Phase 1A). */
export const DOCUMENT_STATUS_SUMMARY_ORDER = [
  "EXPIRED",
  "EXPIRING_30",
  "EXPIRING_60",
  "VALID",
  "NO_EXPIRY",
] as const;

export function documentExpiryStatus(row: EmployeeDocumentRow): string {
  return String(row.expiry_status || "").toUpperCase();
}

export function countDocumentsByExpiryStatus(
  items: EmployeeDocumentRow[]
): Record<string, number> {
  const counts: Record<string, number> = {
    EXPIRED: 0,
    EXPIRING_30: 0,
    EXPIRING_60: 0,
    VALID: 0,
    NO_EXPIRY: 0,
  };
  for (const row of items) {
    const key = documentExpiryStatus(row);
    if (key in counts) counts[key] += 1;
  }
  return counts;
}

function worstExpiryStatus(documents: EmployeeDocumentRow[]): string {
  if (!documents.length) return "VALID";
  return documents.reduce((worst, row) => {
    const status = documentExpiryStatus(row);
    const currentRank = RISK_ORDER[status] ?? 99;
    const worstRank = RISK_ORDER[worst] ?? 99;
    return currentRank < worstRank ? status : worst;
  }, "NO_EXPIRY");
}

function mapWorstStatusToRisk(worst: string, documents: EmployeeDocumentRow[]): ProfessionalRiskLevel {
  if (!documents.length) return "INCOMPLETE";
  switch (worst) {
    case "EXPIRED":
      return "CRITICAL";
    case "EXPIRING_30":
      return "URGENT";
    case "EXPIRING_60":
      return "ATTENTION";
    default:
      return "OK";
  }
}

function nearestExpirationIso(documents: EmployeeDocumentRow[]): string | null {
  const dates = documents
    .map((d) => d.valid_until)
    .filter((v): v is string => Boolean(v))
    .sort((a, b) => new Date(a).getTime() - new Date(b).getTime());
  return dates[0] ?? null;
}

function inferMainSpecialtyFromDocuments(documents: EmployeeDocumentRow[]): string {
  const credential = documents.find(
    (d) =>
      d.medical_specialty_name &&
      (d.document_type_code === "SPECIALIST_CERTIFICATION")
  );
  if (credential?.medical_specialty_name) return credential.medical_specialty_name;

  const anySpecialty = documents.find((d) => d.medical_specialty_name);
  return anySpecialty?.medical_specialty_name || "—";
}

export function buildProfessionalProfileSummary(args: {
  employeeId: number;
  documents: EmployeeDocumentRow[];
  available: boolean;
}): ProfessionalProfileSummary {
  const employeeDocuments = args.documents.filter((d) => d.employee_id === args.employeeId);
  const worst = worstExpiryStatus(employeeDocuments);
  const riskLevel = mapWorstStatusToRisk(worst, employeeDocuments);

  return {
    mainSpecialty: inferMainSpecialtyFromDocuments(employeeDocuments),
    category: "—",
    riskLevel,
    riskLabel: RISK_META[riskLevel].label,
    nearestExpiration: nearestExpirationIso(employeeDocuments),
    documents: employeeDocuments,
    available: args.available,
  };
}

/** Statuses that need management attention. */
export const PROBLEMATIC_DOCUMENT_STATUSES = new Set(["EXPIRED", "EXPIRING_30", "EXPIRING_60"]);

export type DocumentQuickFilter =
  | ""
  | "ALL"
  | "PROBLEMATIC"
  | "EXPIRED"
  | "EXPIRING_30"
  | "EXPIRING_60"
  | "VALID"
  | "NO_EXPIRY";

export const DOCUMENT_QUICK_FILTERS: { value: DocumentQuickFilter; label: string }[] = [
  { value: "ALL", label: "Все" },
  { value: "PROBLEMATIC", label: "Проблемные" },
  { value: "EXPIRED", label: "Истёк" },
  { value: "EXPIRING_30", label: "≤ 30 дней" },
  { value: "EXPIRING_60", label: "≤ 60 дней" },
  { value: "VALID", label: "Действует" },
  { value: "NO_EXPIRY", label: "Без срока" },
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

export function expiryStatusMeta(status: string) {
  const key = String(status || "").toUpperCase();
  return (
    DOCUMENT_STATUS_META[key] ?? {
      label: status,
      className: "bg-zinc-100 text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200",
    }
  );
}
