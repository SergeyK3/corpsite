import { PROMOTION_BLOCKER_CODES, sumBlockersByCodes } from "./normalizedRecordPromotionLabels";

export type PromotionDryRunResult = {
  dry_run: boolean;
  requested: number;
  would_promote: number;
  would_fail: number;
  summary_by_blocker: Record<string, number>;
};

export const PROMOTE_DISABLED_MESSAGES = {
  NO_BATCH: "Нет выбранного batch.",
  NO_NORMALIZED_RECORDS:
    "Нет нормализованных записей для promotion. Проверьте этап нормализации.",
  DRY_RUN_REQUIRED: "Сначала выполните Dry Run.",
  NO_READY_RECORDS: "Нет записей, готовых к promotion.",
  ALL_BLOCKED: "Все approved записи имеют блокирующие ошибки.",
  TABLE_UNAVAILABLE: "Таблица нормализованных записей недоступна — promotion отключён.",
  DRY_RUN_IN_PROGRESS: "Выполняется dry-run…",
  PROMOTE_IN_PROGRESS: "Выполняется promotion…",
} as const;

export type PromoteDisabledReasonCode =
  | "NO_BATCH"
  | "NO_NORMALIZED_RECORDS"
  | "TABLE_UNAVAILABLE"
  | "DRY_RUN_REQUIRED"
  | "NO_READY_RECORDS"
  | "ALL_BLOCKED"
  | "DRY_RUN_IN_PROGRESS"
  | "PROMOTE_IN_PROGRESS"
  | null;

export type PromotionScopeKind = "batch" | "employee";

export type PromoteDisabledState = {
  canPromote: boolean;
  reasonCode: PromoteDisabledReasonCode;
  message: string | null;
};

export type DryRunSummary = {
  approved: number;
  wouldPromote: number;
  blocked: number;
};

export type BlockerReasonLine = {
  key: string;
  label: string;
  count: number;
};

const VALIDATION_BLOCKER_CODES = [
  "VALIDATION_MISSING_VALID_UNTIL",
  "VALIDATION_MISSING_HOURS_OR_ISSUED_AT",
] as const;

const OTHER_BLOCKER_CODES = PROMOTION_BLOCKER_CODES.filter(
  (code) => code !== "EMPLOYEE_REQUIRED" && !VALIDATION_BLOCKER_CODES.includes(code as (typeof VALIDATION_BLOCKER_CODES)[number]),
);

export const BLOCKER_REASON_DISPLAY_GROUPS: ReadonlyArray<{
  key: string;
  label: string;
  codes: readonly string[];
}> = [
  {
    key: "employee",
    label: "Сотрудник не привязан (отсутствует employee_id)",
    codes: ["EMPLOYEE_REQUIRED"],
  },
  {
    key: "validation",
    label: "Ошибка валидации",
    codes: VALIDATION_BLOCKER_CODES,
  },
  {
    key: "other",
    label: "Прочее",
    codes: OTHER_BLOCKER_CODES,
  },
];

export function buildPromotionScopeLabel(input: {
  scope?: PromotionScopeKind;
  batchId?: string | number | null;
  employeeLabel?: string | null;
  recordKindLabel?: string | null;
}): string {
  const scope = input.scope ?? "batch";
  if (scope === "employee" && input.employeeLabel?.trim()) {
    return `Current employee: ${input.employeeLabel.trim()}`;
  }
  if (input.batchId) {
    const base = `Batch #${input.batchId}`;
    return input.recordKindLabel ? `${base} · ${input.recordKindLabel}` : base;
  }
  return "Batch не выбран";
}

export function buildDryRunSummary(result: PromotionDryRunResult): DryRunSummary {
  return {
    approved: result.requested,
    wouldPromote: result.would_promote,
    blocked: result.would_fail,
  };
}

export function buildBlockerReasonLines(
  summaryByBlocker: Record<string, number>,
): BlockerReasonLine[] {
  return BLOCKER_REASON_DISPLAY_GROUPS.map((group) => ({
    key: group.key,
    label: group.label,
    count: sumBlockersByCodes(summaryByBlocker, group.codes),
  })).filter((line) => line.count > 0);
}

export function resolvePromoteDisabledState(input: {
  batchSelected: boolean;
  tableUnavailable: boolean;
  dryRunning: boolean;
  promoting: boolean;
  promotionResult: PromotionDryRunResult | null;
  approvedInBatch?: number;
  normalizedInBatch?: number;
}): PromoteDisabledState {
  if (!input.batchSelected) {
    return {
      canPromote: false,
      reasonCode: "NO_BATCH",
      message: PROMOTE_DISABLED_MESSAGES.NO_BATCH,
    };
  }
  if (input.tableUnavailable) {
    return {
      canPromote: false,
      reasonCode: "TABLE_UNAVAILABLE",
      message: PROMOTE_DISABLED_MESSAGES.TABLE_UNAVAILABLE,
    };
  }
  if (input.dryRunning) {
    return {
      canPromote: false,
      reasonCode: "DRY_RUN_IN_PROGRESS",
      message: PROMOTE_DISABLED_MESSAGES.DRY_RUN_IN_PROGRESS,
    };
  }
  if (input.promoting) {
    return {
      canPromote: false,
      reasonCode: "PROMOTE_IN_PROGRESS",
      message: PROMOTE_DISABLED_MESSAGES.PROMOTE_IN_PROGRESS,
    };
  }

  if (input.normalizedInBatch === 0) {
    return {
      canPromote: false,
      reasonCode: "NO_NORMALIZED_RECORDS",
      message: PROMOTE_DISABLED_MESSAGES.NO_NORMALIZED_RECORDS,
    };
  }

  const dryRunDone = input.promotionResult?.dry_run === true;
  if (!dryRunDone) {
    if (input.approvedInBatch === 0) {
      return {
        canPromote: false,
        reasonCode: "NO_READY_RECORDS",
        message: PROMOTE_DISABLED_MESSAGES.NO_READY_RECORDS,
      };
    }
    return {
      canPromote: false,
      reasonCode: "DRY_RUN_REQUIRED",
      message: PROMOTE_DISABLED_MESSAGES.DRY_RUN_REQUIRED,
    };
  }

  const requested = input.promotionResult?.requested ?? 0;
  const wouldPromote = input.promotionResult?.would_promote ?? 0;

  if (requested === 0) {
    return {
      canPromote: false,
      reasonCode: "NO_READY_RECORDS",
      message: PROMOTE_DISABLED_MESSAGES.NO_READY_RECORDS,
    };
  }
  if (wouldPromote === 0) {
    return {
      canPromote: false,
      reasonCode: "ALL_BLOCKED",
      message: PROMOTE_DISABLED_MESSAGES.ALL_BLOCKED,
    };
  }

  return {
    canPromote: true,
    reasonCode: null,
    message: null,
  };
}
