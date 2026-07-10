export type PersonnelOrderStatus =
  | "DRAFT"
  | "READY_FOR_SIGNATURE"
  | "SIGNED"
  | "REGISTERED"
  | "VOIDED";

export type PersonnelOrderType =
  | "HIRE"
  | "TRANSFER"
  | "TERMINATION"
  | "CONCURRENT_DUTY_START"
  | "CONCURRENT_DUTY_END"
  | "COMPOSITE";

export const PERSONNEL_ORDER_STATUSES: readonly PersonnelOrderStatus[] = [
  "DRAFT",
  "READY_FOR_SIGNATURE",
  "SIGNED",
  "REGISTERED",
  "VOIDED",
] as const;

export const PERSONNEL_ORDER_TYPES: readonly PersonnelOrderType[] = [
  "HIRE",
  "TRANSFER",
  "TERMINATION",
  "CONCURRENT_DUTY_START",
  "CONCURRENT_DUTY_END",
  "COMPOSITE",
] as const;

export const PERSONNEL_ORDER_STATUS_LABELS: Record<PersonnelOrderStatus, string> = {
  DRAFT: "Черновик",
  READY_FOR_SIGNATURE: "На подписи",
  SIGNED: "Подписан",
  REGISTERED: "Зарегистрирован",
  VOIDED: "Аннулирован",
};

export const PERSONNEL_ORDER_TYPE_LABELS: Record<PersonnelOrderType, string> = {
  HIRE: "Приём",
  TRANSFER: "Перевод",
  TERMINATION: "Увольнение",
  CONCURRENT_DUTY_START: "Совмещение (начало)",
  CONCURRENT_DUTY_END: "Совмещение (окончание)",
  COMPOSITE: "Составной",
};

export const PERSONNEL_ORDER_SOURCE_MODE_LABELS: Record<string, string> = {
  PAPER: "Бумажный",
  DIGITAL: "Электронный",
};

export const PERSONNEL_ORDER_STATUS_FILTER_OPTIONS: ReadonlyArray<{
  value: "" | PersonnelOrderStatus;
  label: string;
}> = [
  { value: "", label: "Все статусы" },
  ...PERSONNEL_ORDER_STATUSES.map((value) => ({
    value,
    label: PERSONNEL_ORDER_STATUS_LABELS[value],
  })),
];

export const PERSONNEL_ORDER_TYPE_FILTER_OPTIONS: ReadonlyArray<{
  value: "" | PersonnelOrderType;
  label: string;
}> = [
  { value: "", label: "Все типы" },
  ...PERSONNEL_ORDER_TYPES.map((value) => ({
    value,
    label: PERSONNEL_ORDER_TYPE_LABELS[value],
  })),
];

export function personnelOrderStatusLabel(status: string | null | undefined): string {
  const normalized = String(status || "").trim().toUpperCase();
  if ((PERSONNEL_ORDER_STATUSES as readonly string[]).includes(normalized)) {
    return PERSONNEL_ORDER_STATUS_LABELS[normalized as PersonnelOrderStatus];
  }
  return normalized || "—";
}

export function personnelOrderTypeLabel(typeCode: string | null | undefined): string {
  const normalized = String(typeCode || "").trim().toUpperCase();
  if ((PERSONNEL_ORDER_TYPES as readonly string[]).includes(normalized)) {
    return PERSONNEL_ORDER_TYPE_LABELS[normalized as PersonnelOrderType];
  }
  return normalized || "—";
}

export function personnelOrderSourceModeLabel(sourceMode: string | null | undefined): string {
  const normalized = String(sourceMode || "").trim().toUpperCase();
  return PERSONNEL_ORDER_SOURCE_MODE_LABELS[normalized] || normalized || "—";
}

export function personnelOrderStatusBadgeClass(status: string | null | undefined): string {
  switch (String(status || "").trim().toUpperCase()) {
    case "DRAFT":
      return "border-zinc-200 bg-zinc-100 text-zinc-800 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200";
    case "READY_FOR_SIGNATURE":
      return "border-amber-200 bg-amber-100 text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200";
    case "SIGNED":
      return "border-blue-200 bg-blue-100 text-blue-900 dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-200";
    case "REGISTERED":
      return "border-emerald-200 bg-emerald-100 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200";
    case "VOIDED":
      return "border-red-200 bg-red-100 text-red-900 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200";
    default:
      return "border-zinc-200 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300";
  }
}

export function personnelOrderTypeBadgeClass(typeCode: string | null | undefined): string {
  switch (String(typeCode || "").trim().toUpperCase()) {
    case "HIRE":
      return "border-emerald-200 bg-emerald-100 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200";
    case "TRANSFER":
      return "border-blue-200 bg-blue-100 text-blue-900 dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-200";
    case "TERMINATION":
      return "border-zinc-300 bg-zinc-200 text-zinc-800 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200";
    case "CONCURRENT_DUTY_START":
    case "CONCURRENT_DUTY_END":
      return "border-cyan-200 bg-cyan-100 text-cyan-900 dark:border-cyan-800 dark:bg-cyan-950/50 dark:text-cyan-200";
    case "COMPOSITE":
      return "border-violet-200 bg-violet-100 text-violet-900 dark:border-violet-800 dark:bg-violet-950/50 dark:text-violet-200";
    default:
      return "border-zinc-200 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300";
  }
}

export const PERSONNEL_ORDER_CREATE_TYPES = [
  "HIRE",
  "TRANSFER",
  "TERMINATION",
  "CONCURRENT_DUTY_START",
  "CONCURRENT_DUTY_END",
] as const satisfies readonly PersonnelOrderType[];

export const PERSONNEL_ORDER_CREATE_TYPE_OPTIONS: ReadonlyArray<{
  value: (typeof PERSONNEL_ORDER_CREATE_TYPES)[number];
  label: string;
}> = PERSONNEL_ORDER_CREATE_TYPES.map((value) => ({
  value,
  label: PERSONNEL_ORDER_TYPE_LABELS[value],
}));

export function isEditablePersonnelOrderStatus(status: string | null | undefined): boolean {
  const normalized = String(status || "").trim().toUpperCase();
  return normalized === "DRAFT" || normalized === "READY_FOR_SIGNATURE";
}

export function canRegisterPersonnelOrder(status: string | null | undefined): boolean {
  const normalized = String(status || "").trim().toUpperCase();
  return normalized === "DRAFT" || normalized === "READY_FOR_SIGNATURE";
}

export function canApplyPersonnelOrder(status: string | null | undefined): boolean {
  const normalized = String(status || "").trim().toUpperCase();
  return normalized === "SIGNED" || normalized === "REGISTERED";
}

/** Applied is terminal UX state derived from linked employee_events, not a separate order.status. */
export function isPersonnelOrderApplied(linkedEventCount: number | null | undefined): boolean {
  return Number(linkedEventCount || 0) > 0;
}

/** Apply is allowed only for SIGNED/REGISTERED orders that have not yet produced linked events. */
export function canApplyPersonnelOrderAction(
  status: string | null | undefined,
  linkedEventCount: number | null | undefined,
): boolean {
  return canApplyPersonnelOrder(status) && !isPersonnelOrderApplied(linkedEventCount);
}

export const PERSONNEL_ORDER_APPLIED_LABEL = "Применён";

export function personnelOrderAppliedBadgeClass(): string {
  return "border-teal-200 bg-teal-100 text-teal-900 dark:border-teal-800 dark:bg-teal-950/50 dark:text-teal-200";
}

export function canVoidPersonnelOrder(status: string | null | undefined): boolean {
  const normalized = String(status || "").trim().toUpperCase();
  return normalized !== "" && normalized !== "VOIDED";
}

export function formatPersonnelOrderNumber(value: string | null | undefined): string {
  const trimmed = String(value || "").trim();
  return trimmed || "без номера";
}

export function formatPersonnelOrderDate(value: string | null | undefined): string {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleDateString("ru-RU");
}

export function formatPersonnelOrderDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}
