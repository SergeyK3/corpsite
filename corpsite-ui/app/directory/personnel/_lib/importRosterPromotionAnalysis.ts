import type { RosterPromotionItem, RosterPromotionOutcome } from "./importApi.client";

export const ROSTER_PROMOTION_OUTCOME_LABELS: Record<RosterPromotionOutcome, string> = {
  would_create: "Будет создан",
  would_update: "Будет обновлён",
  already_linked: "Уже привязан",
  exists: "Уже существует",
  conflict: "Конфликт",
  blocked: "Ошибка",
};

const DEPARTMENT_REASON_PATTERNS = [
  /^Отделение не сопоставлено:\s*(.+)$/,
  /^Отделение не сопоставлено с org_unit:\s*(.+)$/,
] as const;

const INVALID_IIN_REASON = "ИИН отсутствует или не содержит 12 цифр";

export const REASON_TYPE_UNMATCHED_DEPARTMENT = "unmatched_department";
export const REASON_TYPE_INVALID_IIN = "invalid_iin";

export type ReasonSummaryRow = {
  label: string;
  reasonKey: string;
  count: number;
};

export type ReasonDetailSummaryRow = {
  detailKey: string;
  detailLabel: string;
  reasonKey: string;
  count: number;
};

export type ReasonTypeSummaryRow = {
  typeKey: string;
  typeLabel: string;
  count: number;
  details: ReasonDetailSummaryRow[];
};

export type RosterPromotionFilters = {
  outcome: RosterPromotionOutcome | "";
  reasonTypeKey: string;
  reasonKey: string;
  department: string;
  qName: string;
  qIin: string;
};

export const EMPTY_ROSTER_PROMOTION_FILTERS: RosterPromotionFilters = {
  outcome: "",
  reasonTypeKey: "",
  reasonKey: "",
  department: "",
  qName: "",
  qIin: "",
};

export type ReasonClassification = {
  typeKey: string;
  typeLabel: string;
  detailKey: string;
  detailLabel: string;
  reasonKey: string;
};

export type RosterPromotionOverview = {
  total: number;
  wouldCreate: number;
  wouldUpdate: number;
  alreadyLinked: number;
  errors: number;
  conflicts: number;
  topProblem: { label: string; count: number } | null;
};

/** Human-readable reason label for table display and exact filtering. Returns null when row has no reason. */
export function normalizeReasonLabel(reason: string | null | undefined): string | null {
  return classifyReason(reason)?.reasonKey ?? null;
}

export function classifyReason(reason: string | null | undefined): ReasonClassification | null {
  const trimmed = (reason || "").trim();
  if (!trimmed) return null;

  for (const pattern of DEPARTMENT_REASON_PATTERNS) {
    const match = trimmed.match(pattern);
    if (match) {
      const department = match[1].trim();
      const reasonKey = `Не сопоставлено подразделение: ${department}`;
      return {
        typeKey: REASON_TYPE_UNMATCHED_DEPARTMENT,
        typeLabel: "Не сопоставлено подразделение",
        detailKey: reasonKey,
        detailLabel: department,
        reasonKey,
      };
    }
  }

  if (trimmed === INVALID_IIN_REASON) {
    return {
      typeKey: REASON_TYPE_INVALID_IIN,
      typeLabel: "Некорректный ИИН",
      detailKey: REASON_TYPE_INVALID_IIN,
      detailLabel: "Некорректный ИИН",
      reasonKey: "Некорректный ИИН",
    };
  }

  return {
    typeKey: `other:${trimmed}`,
    typeLabel: trimmed,
    detailKey: trimmed,
    detailLabel: trimmed,
    reasonKey: trimmed,
  };
}

export function getReasonFilterKey(reason: string | null | undefined): string {
  return normalizeReasonLabel(reason) ?? "";
}

export function getReasonTypeKey(reason: string | null | undefined): string {
  return classifyReason(reason)?.typeKey ?? "";
}

/** Department label for filters: resolved org unit or raw department from reason. */
export function getDepartmentLabel(item: RosterPromotionItem): string {
  const orgUnitName = (item.org_unit_name || "").trim();
  if (orgUnitName) return orgUnitName;

  const reason = (item.reason || "").trim();
  for (const pattern of DEPARTMENT_REASON_PATTERNS) {
    const match = reason.match(pattern);
    if (match) return match[1].trim();
  }

  return "—";
}

export function shouldShowReasonDetails(typeRow: ReasonTypeSummaryRow): boolean {
  if (typeRow.details.length === 0) return false;
  if (typeRow.details.length === 1) {
    return typeRow.details[0].detailLabel !== typeRow.typeLabel;
  }
  return true;
}

export function buildReasonTypeSummary(items: RosterPromotionItem[]): ReasonTypeSummaryRow[] {
  const types = new Map<
    string,
    {
      typeLabel: string;
      count: number;
      details: Map<string, ReasonDetailSummaryRow>;
    }
  >();

  for (const item of items) {
    const classification = classifyReason(item.reason);
    if (!classification) continue;

    const typeBucket =
      types.get(classification.typeKey) ??
      (() => {
        const bucket = {
          typeLabel: classification.typeLabel,
          count: 0,
          details: new Map<string, ReasonDetailSummaryRow>(),
        };
        types.set(classification.typeKey, bucket);
        return bucket;
      })();

    typeBucket.count += 1;

    const detailBucket = typeBucket.details.get(classification.detailKey);
    if (detailBucket) {
      detailBucket.count += 1;
    } else {
      typeBucket.details.set(classification.detailKey, {
        detailKey: classification.detailKey,
        detailLabel: classification.detailLabel,
        reasonKey: classification.reasonKey,
        count: 1,
      });
    }
  }

  return Array.from(types.entries())
    .map(([typeKey, bucket]) => ({
      typeKey,
      typeLabel: bucket.typeLabel,
      count: bucket.count,
      details: Array.from(bucket.details.values()).sort(
        (a, b) => b.count - a.count || a.detailLabel.localeCompare(b.detailLabel, "ru")
      ),
    }))
    .sort((a, b) => b.count - a.count || a.typeLabel.localeCompare(b.typeLabel, "ru"));
}

export function buildReasonSummary(items: RosterPromotionItem[]): ReasonSummaryRow[] {
  const counts = new Map<string, ReasonSummaryRow>();

  for (const item of items) {
    const label = normalizeReasonLabel(item.reason);
    if (!label) continue;

    const existing = counts.get(label);
    if (existing) {
      existing.count += 1;
    } else {
      counts.set(label, { label, reasonKey: label, count: 1 });
    }
  }

  return Array.from(counts.values()).sort(
    (a, b) => b.count - a.count || a.label.localeCompare(b.label, "ru")
  );
}

export function buildRosterPromotionOverview(
  items: RosterPromotionItem[],
  summary: Partial<Record<RosterPromotionOutcome, number>>
): RosterPromotionOverview {
  const typeSummary = buildReasonTypeSummary(items);
  const topProblem = typeSummary[0]
    ? { label: typeSummary[0].typeLabel, count: typeSummary[0].count }
    : null;

  return {
    total: items.length,
    wouldCreate: summary.would_create ?? 0,
    wouldUpdate: summary.would_update ?? 0,
    alreadyLinked: summary.already_linked ?? 0,
    errors: summary.blocked ?? 0,
    conflicts: summary.conflict ?? 0,
    topProblem,
  };
}

export function collectDepartmentOptions(items: RosterPromotionItem[]): string[] {
  const departments = new Set<string>();
  for (const item of items) {
    const label = getDepartmentLabel(item);
    if (label !== "—") departments.add(label);
  }
  return Array.from(departments).sort((a, b) => a.localeCompare(b, "ru"));
}

export function hasActiveRosterPromotionFilters(filters: RosterPromotionFilters): boolean {
  return Boolean(
    filters.outcome ||
      filters.reasonTypeKey ||
      filters.reasonKey ||
      filters.department ||
      filters.qName.trim() ||
      filters.qIin.trim()
  );
}

export function filterRosterPromotionItems(
  items: RosterPromotionItem[],
  filters: RosterPromotionFilters
): RosterPromotionItem[] {
  const nameQuery = filters.qName.trim().toLowerCase();
  const iinQuery = filters.qIin.replace(/\D/g, "");

  return items.filter((item) => {
    if (filters.outcome && item.outcome !== filters.outcome) return false;

    if (filters.reasonKey) {
      if (getReasonFilterKey(item.reason) !== filters.reasonKey) return false;
    } else if (filters.reasonTypeKey) {
      if (getReasonTypeKey(item.reason) !== filters.reasonTypeKey) return false;
    }

    if (filters.department && getDepartmentLabel(item) !== filters.department) return false;
    if (nameQuery && !(item.full_name || "").toLowerCase().includes(nameQuery)) return false;
    if (iinQuery && !(item.iin || "").includes(iinQuery)) return false;
    return true;
  });
}
