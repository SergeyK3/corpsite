import type { PersonnelOrderItem } from "./personnelOrdersApi.client";
import { PERSONNEL_ORDER_TYPE_LABELS } from "./personnelOrderLabels";

/**
 * UI form types for the personnel order item editor (WP-PO-ITEM-001A).
 * RATE_CHANGE is a UI-only alias that persists as backend TRANSFER with to_rate only.
 */
export type PersonnelOrderItemFormType =
  | "TRANSFER"
  | "TERMINATION"
  | "RATE_CHANGE"
  | "CONCURRENT_DUTY_START"
  | "CONCURRENT_DUTY_END"
  | "HIRE";

export type ItemFormRegistryEntry = {
  /** Show employee search + manual employee_id field. */
  employeePicker: boolean;
  /** When true, search uses status=active and filters non-active rows. */
  employeePickerActiveOnly: boolean;
  employeeRequired: boolean;
  showCurrentPlacement: boolean;
  showTargetPlacement: boolean;
  /** Editable new rate field (maps to employment_rate or to_rate depending on backend type). */
  showTargetRate: boolean;
  showTerminationReason: boolean;
  showConcurrentDutyStartFields: boolean;
  showConcurrentDutyEndFields: boolean;
  /** Legacy HIRE placement cascade — pending WP-PO-HIRE-001. */
  showHirePlacement: boolean;
  clearTargetOnEmployeeChange: boolean;
  /** item_type_code sent to the API on save. */
  backendItemType: string;
  hireLegacyPending?: boolean;
};

const REGISTRY: Record<PersonnelOrderItemFormType, ItemFormRegistryEntry> = {
  TRANSFER: {
    employeePicker: true,
    employeePickerActiveOnly: true,
    employeeRequired: true,
    showCurrentPlacement: true,
    showTargetPlacement: true,
    showTargetRate: true,
    showTerminationReason: false,
    showConcurrentDutyStartFields: false,
    showConcurrentDutyEndFields: false,
    showHirePlacement: false,
    clearTargetOnEmployeeChange: true,
    backendItemType: "TRANSFER",
  },
  TERMINATION: {
    employeePicker: true,
    employeePickerActiveOnly: true,
    employeeRequired: true,
    showCurrentPlacement: true,
    showTargetPlacement: false,
    showTargetRate: false,
    showTerminationReason: true,
    showConcurrentDutyStartFields: false,
    showConcurrentDutyEndFields: false,
    showHirePlacement: false,
    clearTargetOnEmployeeChange: false,
    backendItemType: "TERMINATION",
  },
  RATE_CHANGE: {
    employeePicker: true,
    employeePickerActiveOnly: true,
    employeeRequired: true,
    showCurrentPlacement: true,
    showTargetPlacement: false,
    showTargetRate: true,
    showTerminationReason: false,
    showConcurrentDutyStartFields: false,
    showConcurrentDutyEndFields: false,
    showHirePlacement: false,
    clearTargetOnEmployeeChange: true,
    backendItemType: "TRANSFER",
  },
  CONCURRENT_DUTY_START: {
    employeePicker: true,
    employeePickerActiveOnly: true,
    employeeRequired: true,
    showCurrentPlacement: true,
    showTargetPlacement: false,
    showTargetRate: false,
    showTerminationReason: false,
    showConcurrentDutyStartFields: true,
    showConcurrentDutyEndFields: false,
    showHirePlacement: false,
    clearTargetOnEmployeeChange: false,
    backendItemType: "CONCURRENT_DUTY_START",
  },
  CONCURRENT_DUTY_END: {
    employeePicker: true,
    employeePickerActiveOnly: true,
    employeeRequired: true,
    showCurrentPlacement: true,
    showTargetPlacement: false,
    showTargetRate: false,
    showTerminationReason: false,
    showConcurrentDutyStartFields: false,
    showConcurrentDutyEndFields: true,
    showHirePlacement: false,
    clearTargetOnEmployeeChange: false,
    backendItemType: "CONCURRENT_DUTY_END",
  },
  HIRE: {
    employeePicker: true,
    employeePickerActiveOnly: false,
    employeeRequired: false,
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
  },
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
  { value: "HIRE", label: `${PERSONNEL_ORDER_TYPE_LABELS.HIRE} (WP-PO-HIRE-001)` },
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
  return getItemFormRegistry(itemTypeCode)?.employeeRequired === true;
}

export function itemFormTypeLabel(itemTypeCode: string | null | undefined): string {
  const normalized = String(itemTypeCode || "").trim().toUpperCase();
  const option = PERSONNEL_ORDER_ITEM_FORM_TYPE_OPTIONS.find((row) => row.value === normalized);
  if (option) return option.label;
  return PERSONNEL_ORDER_TYPE_LABELS[normalized as keyof typeof PERSONNEL_ORDER_TYPE_LABELS] || normalized || "—";
}
