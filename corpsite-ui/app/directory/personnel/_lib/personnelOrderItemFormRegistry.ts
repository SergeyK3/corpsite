import type { PersonnelOrderItem } from "./personnelOrdersApi.client";
import { PERSONNEL_ORDER_TYPE_LABELS } from "./personnelOrderLabels";

/**
 * UI form types for the personnel order item editor (WP-PO-ITEM-001A / WP-PO-UX-001).
 * RATE_CHANGE is a UI-only alias that persists as backend TRANSFER with to_rate only.
 */
export type PersonnelOrderItemFormType =
  | "TRANSFER"
  | "TERMINATION"
  | "RATE_CHANGE"
  | "CONCURRENT_DUTY_START"
  | "CONCURRENT_DUTY_END"
  | "HIRE";

/** Unified form sections — order is per item type via fieldSectionOrder. */
export type ItemFormSection =
  | "item_type"
  | "employee"
  | "current_placement"
  | "org_placement"
  | "effective_date"
  | "additional";

export type EmployeePickerMode = "required" | "optional" | "pending_new_allowed";

export type ItemFormRegistryEntry = {
  /** Show employee search (+ optional manual id in advanced row). */
  employeePicker: boolean;
  /** When true, search uses status=active and filters non-active rows. */
  employeePickerActiveOnly: boolean;
  /** @deprecated Use employeePickerMode — kept for existing callers. */
  employeeRequired: boolean;
  employeePickerMode: EmployeePickerMode;
  showCurrentPlacement: boolean;
  showTargetPlacement: boolean;
  /** Editable new rate field (maps to employment_rate or to_rate depending on backend type). */
  showTargetRate: boolean;
  showTerminationReason: boolean;
  showConcurrentDutyStartFields: boolean;
  showConcurrentDutyEndFields: boolean;
  /** HIRE placement cascade — pending WP-PO-HIRE-001 full new-employee flow. */
  showHirePlacement: boolean;
  clearTargetOnEmployeeChange: boolean;
  /** item_type_code sent to the API on save. */
  backendItemType: string;
  hireLegacyPending?: boolean;
  /** Visual section order in the item form (WP-PO-UX-001). */
  fieldSectionOrder: readonly ItemFormSection[];
  /** Title for org_placement block. */
  orgPlacementSectionTitle: string;
};

const DEFAULT_SECTION_ORDER: readonly ItemFormSection[] = [
  "item_type",
  "employee",
  "current_placement",
  "org_placement",
  "effective_date",
  "additional",
] as const;

const HIRE_SECTION_ORDER: readonly ItemFormSection[] = [
  "item_type",
  "org_placement",
  "effective_date",
  "employee",
  "additional",
] as const;

function entry(
  partial: Omit<ItemFormRegistryEntry, "employeeRequired" | "fieldSectionOrder"> & {
    fieldSectionOrder?: readonly ItemFormSection[];
  },
): ItemFormRegistryEntry {
  const employeeRequired = partial.employeePickerMode === "required";
  return {
    ...partial,
    employeeRequired,
    fieldSectionOrder: partial.fieldSectionOrder ?? DEFAULT_SECTION_ORDER,
  };
}

const REGISTRY: Record<PersonnelOrderItemFormType, ItemFormRegistryEntry> = {
  TRANSFER: entry({
    employeePicker: true,
    employeePickerActiveOnly: true,
    employeePickerMode: "required",
    showCurrentPlacement: true,
    showTargetPlacement: true,
    showTargetRate: true,
    showTerminationReason: false,
    showConcurrentDutyStartFields: false,
    showConcurrentDutyEndFields: false,
    showHirePlacement: false,
    clearTargetOnEmployeeChange: true,
    backendItemType: "TRANSFER",
    orgPlacementSectionTitle: "Новое назначение",
  }),
  TERMINATION: entry({
    employeePicker: true,
    employeePickerActiveOnly: true,
    employeePickerMode: "required",
    showCurrentPlacement: true,
    showTargetPlacement: false,
    showTargetRate: false,
    showTerminationReason: true,
    showConcurrentDutyStartFields: false,
    showConcurrentDutyEndFields: false,
    showHirePlacement: false,
    clearTargetOnEmployeeChange: false,
    backendItemType: "TERMINATION",
    orgPlacementSectionTitle: "Назначение",
    fieldSectionOrder: [
      "item_type",
      "employee",
      "current_placement",
      "effective_date",
      "additional",
    ],
  }),
  RATE_CHANGE: entry({
    employeePicker: true,
    employeePickerActiveOnly: true,
    employeePickerMode: "required",
    showCurrentPlacement: true,
    showTargetPlacement: false,
    showTargetRate: true,
    showTerminationReason: false,
    showConcurrentDutyStartFields: false,
    showConcurrentDutyEndFields: false,
    showHirePlacement: false,
    clearTargetOnEmployeeChange: true,
    backendItemType: "TRANSFER",
    orgPlacementSectionTitle: "Назначение",
    fieldSectionOrder: [
      "item_type",
      "employee",
      "current_placement",
      "effective_date",
      "additional",
    ],
  }),
  CONCURRENT_DUTY_START: entry({
    employeePicker: true,
    employeePickerActiveOnly: true,
    employeePickerMode: "required",
    showCurrentPlacement: true,
    showTargetPlacement: false,
    showTargetRate: false,
    showTerminationReason: false,
    showConcurrentDutyStartFields: true,
    showConcurrentDutyEndFields: false,
    showHirePlacement: false,
    clearTargetOnEmployeeChange: false,
    backendItemType: "CONCURRENT_DUTY_START",
    orgPlacementSectionTitle: "Назначение",
    fieldSectionOrder: [
      "item_type",
      "employee",
      "current_placement",
      "effective_date",
      "additional",
    ],
  }),
  CONCURRENT_DUTY_END: entry({
    employeePicker: true,
    employeePickerActiveOnly: true,
    employeePickerMode: "required",
    showCurrentPlacement: true,
    showTargetPlacement: false,
    showTargetRate: false,
    showTerminationReason: false,
    showConcurrentDutyStartFields: false,
    showConcurrentDutyEndFields: true,
    showHirePlacement: false,
    clearTargetOnEmployeeChange: false,
    backendItemType: "CONCURRENT_DUTY_END",
    orgPlacementSectionTitle: "Назначение",
    fieldSectionOrder: [
      "item_type",
      "employee",
      "current_placement",
      "effective_date",
      "additional",
    ],
  }),
  HIRE: entry({
    employeePicker: true,
    employeePickerActiveOnly: false,
    employeePickerMode: "pending_new_allowed",
    showCurrentPlacement: false,
    showTargetPlacement: false,
    showTargetRate: false,
    showTerminationReason: false,
    showConcurrentDutyStartFields: false,
    showConcurrentDutyEndFields: false,
    showHirePlacement: true,
    clearTargetOnEmployeeChange: false,
    backendItemType: "HIRE",
    hireLegacyPending: true,
    orgPlacementSectionTitle: "Назначение (приём)",
    fieldSectionOrder: HIRE_SECTION_ORDER,
  }),
};

export const PERSONNEL_ORDER_ITEM_FORM_TYPE_OPTIONS: ReadonlyArray<{
  value: PersonnelOrderItemFormType;
  label: string;
}> = [
  { value: "TRANSFER", label: PERSONNEL_ORDER_TYPE_LABELS.TRANSFER },
  { value: "TERMINATION", label: PERSONNEL_ORDER_TYPE_LABELS.TERMINATION },
  { value: "RATE_CHANGE", label: "Изменение ставки" },
  {
    value: "CONCURRENT_DUTY_START",
    label: PERSONNEL_ORDER_TYPE_LABELS.CONCURRENT_DUTY_START,
  },
  {
    value: "CONCURRENT_DUTY_END",
    label: PERSONNEL_ORDER_TYPE_LABELS.CONCURRENT_DUTY_END,
  },
  { value: "HIRE", label: PERSONNEL_ORDER_TYPE_LABELS.HIRE },
];

export function normalizeItemFormType(
  itemTypeCode: string | null | undefined,
): PersonnelOrderItemFormType | null {
  const normalized = String(itemTypeCode || "").trim().toUpperCase();
  if (normalized in REGISTRY) {
    return normalized as PersonnelOrderItemFormType;
  }
  return null;
}

export function getItemFormRegistry(
  itemTypeCode: string | null | undefined,
): ItemFormRegistryEntry | null {
  const key = normalizeItemFormType(itemTypeCode);
  return key != null ? REGISTRY[key] : null;
}

export function isTargetOrgScopedFormType(itemTypeCode: string | null | undefined): boolean {
  return getItemFormRegistry(itemTypeCode)?.showTargetPlacement === true;
}

export function isHirePlacementFormType(itemTypeCode: string | null | undefined): boolean {
  return getItemFormRegistry(itemTypeCode)?.showHirePlacement === true;
}

/** Map UI form type to backend item_type_code for create/update. */
export function resolveBackendItemTypeCode(itemTypeCode: string | null | undefined): string {
  const config = getItemFormRegistry(itemTypeCode);
  if (config) return config.backendItemType;
  return String(itemTypeCode || "").trim().toUpperCase();
}

/**
 * Detect UI form type when loading an existing item.
 * TRANSFER with only to_rate maps to RATE_CHANGE.
 */
export function detectUiItemTypeFromRecord(item: PersonnelOrderItem): string {
  const backendType = String(item.item_type_code || "").trim().toUpperCase();
  if (backendType === "TRANSFER") {
    const payload = item.payload || {};
    const hasOrg = payload.to_org_unit_id != null && payload.to_org_unit_id !== "";
    const hasPos = payload.to_position_id != null && payload.to_position_id !== "";
    const hasRate =
      payload.to_rate != null ||
      payload.to_employment_rate != null;
    if (hasRate && !hasOrg && !hasPos) {
      return "RATE_CHANGE";
    }
  }
  return backendType;
}

export function usesActiveEmployeeSearch(itemTypeCode: string | null | undefined): boolean {
  return getItemFormRegistry(itemTypeCode)?.employeePickerActiveOnly === true;
}

export function requiresEmployeeForFormType(itemTypeCode: string | null | undefined): boolean {
  return getItemFormRegistry(itemTypeCode)?.employeePickerMode === "required";
}

export function allowsPendingNewEmployee(itemTypeCode: string | null | undefined): boolean {
  return getItemFormRegistry(itemTypeCode)?.employeePickerMode === "pending_new_allowed";
}

export function itemFormTypeLabel(itemTypeCode: string | null | undefined): string {
  const normalized = String(itemTypeCode || "").trim().toUpperCase();
  const option = PERSONNEL_ORDER_ITEM_FORM_TYPE_OPTIONS.find((row) => row.value === normalized);
  if (option) return option.label;
  return PERSONNEL_ORDER_TYPE_LABELS[normalized as keyof typeof PERSONNEL_ORDER_TYPE_LABELS] || normalized || "—";
}

/** Default item form type when adding a line to an order (WP-PO-UX-001). */
export function resolveDefaultItemFormTypeForOrder(
  orderTypeCode: string | null | undefined,
): PersonnelOrderItemFormType {
  const normalized = String(orderTypeCode || "").trim().toUpperCase();
  if (normalized === "COMPOSITE" || !normalized) return "TRANSFER";
  const asItem = normalizeItemFormType(normalized);
  if (asItem) return asItem;
  return "TRANSFER";
}

/** Item type options for the add/edit form — composite orders expose all line types. */
export function itemFormTypeOptionsForOrder(
  orderTypeCode: string | null | undefined,
): ReadonlyArray<{ value: PersonnelOrderItemFormType; label: string }> {
  const normalized = String(orderTypeCode || "").trim().toUpperCase();
  if (normalized === "COMPOSITE" || !normalized) {
    return PERSONNEL_ORDER_ITEM_FORM_TYPE_OPTIONS;
  }
  const primary = normalizeItemFormType(normalized);
  if (!primary) return PERSONNEL_ORDER_ITEM_FORM_TYPE_OPTIONS;
  const extras: PersonnelOrderItemFormType[] =
    primary === "TRANSFER" ? ["RATE_CHANGE"] : [];
  const values = new Set<PersonnelOrderItemFormType>([primary, ...extras]);
  return PERSONNEL_ORDER_ITEM_FORM_TYPE_OPTIONS.filter((row) => values.has(row.value));
}

export function orderTypeLabelForItemHint(orderTypeCode: string | null | undefined): string | null {
  const normalized = String(orderTypeCode || "").trim().toUpperCase();
  if (!normalized || normalized === "COMPOSITE") return null;
  return PERSONNEL_ORDER_TYPE_LABELS[normalized as keyof typeof PERSONNEL_ORDER_TYPE_LABELS] ?? null;
}
