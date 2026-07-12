import type { ItemPayloadDraft } from "./personnelOrderPayload";
import {
  isHirePlacementFormType,
  isTargetOrgScopedFormType,
} from "./personnelOrderItemFormRegistry";

export function isOrgScopedItemType(itemTypeCode: string | null | undefined): boolean {
  return (
    isTargetOrgScopedFormType(itemTypeCode) || isHirePlacementFormType(itemTypeCode)
  );
}

/** Clear TRANSFER / RATE_CHANGE target fields when the selected employee changes. */
export function clearTransferTargetFields(draft: ItemPayloadDraft): ItemPayloadDraft {
  return {
    ...draft,
    to_org_unit_id: "",
    to_position_id: "",
    to_rate: "",
  };
}

export function selectedOrgUnitIdFromDraft(
  draft: ItemPayloadDraft,
  itemTypeCode: string | null | undefined,
): number | null {
  const type = String(itemTypeCode || "").trim().toUpperCase();
  const raw =
    type === "TRANSFER" || type === "RATE_CHANGE"
      ? draft.to_org_unit_id
      : draft.org_unit_id;
  const unitId = Number(raw || 0);
  return Number.isFinite(unitId) && unitId > 0 ? Math.trunc(unitId) : null;
}

/** Clear unit + position when department group changes (UI-only filter). */
export function clearOrgDependentFields(
  draft: ItemPayloadDraft,
  itemTypeCode: string | null | undefined,
): ItemPayloadDraft {
  const type = String(itemTypeCode || "").trim().toUpperCase();
  if (type === "HIRE") {
    return { ...draft, org_unit_id: "", position_id: "" };
  }
  if (type === "TRANSFER" || type === "RATE_CHANGE") {
    return { ...draft, to_org_unit_id: "", to_position_id: "" };
  }
  return draft;
}

/** Set unit and clear position when org unit changes. */
export function setOrgUnitAndClearPosition(
  draft: ItemPayloadDraft,
  itemTypeCode: string | null | undefined,
  unitId: number | null,
): ItemPayloadDraft {
  const value = unitId != null && Number.isFinite(unitId) && unitId > 0 ? String(Math.trunc(unitId)) : "";
  const type = String(itemTypeCode || "").trim().toUpperCase();
  if (type === "HIRE") {
    return { ...draft, org_unit_id: value, position_id: "" };
  }
  if (type === "TRANSFER" || type === "RATE_CHANGE") {
    return { ...draft, to_org_unit_id: value, to_position_id: "" };
  }
  return draft;
}

export function selectedPositionIdFromDraft(
  draft: ItemPayloadDraft,
  itemTypeCode: string | null | undefined,
): string {
  const type = String(itemTypeCode || "").trim().toUpperCase();
  return type === "TRANSFER" || type === "RATE_CHANGE"
    ? String(draft.to_position_id || "")
    : String(draft.position_id || "");
}

export function setPositionId(
  draft: ItemPayloadDraft,
  itemTypeCode: string | null | undefined,
  positionId: string,
): ItemPayloadDraft {
  const type = String(itemTypeCode || "").trim().toUpperCase();
  if (type === "HIRE") {
    return { ...draft, position_id: positionId };
  }
  if (type === "TRANSFER" || type === "RATE_CHANGE") {
    return { ...draft, to_position_id: positionId };
  }
  return draft;
}
