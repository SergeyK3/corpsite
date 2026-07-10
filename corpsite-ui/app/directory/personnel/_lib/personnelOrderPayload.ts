import type { PersonnelOrderType } from "./personnelOrderLabels";

export type ItemPayloadDraft = {
  org_unit_id?: string;
  position_id?: string;
  employment_rate?: string;
  to_org_unit_id?: string;
  to_position_id?: string;
  to_rate?: string;
  termination_reason?: string;
  concurrent_rate?: string;
  total_rate?: string;
  remaining_rate?: string;
};

function optionalNumber(raw: string | undefined): number | undefined {
  const trimmed = String(raw || "").trim();
  if (!trimmed) return undefined;
  const value = Number(trimmed);
  return Number.isFinite(value) ? value : undefined;
}

export function emptyItemPayloadDraft(): ItemPayloadDraft {
  return {
    org_unit_id: "",
    position_id: "",
    employment_rate: "1",
    to_org_unit_id: "",
    to_position_id: "",
    to_rate: "",
    termination_reason: "",
    concurrent_rate: "0.5",
    total_rate: "",
    remaining_rate: "",
  };
}

export function itemPayloadDraftFromRecord(payload: Record<string, unknown> | null | undefined): ItemPayloadDraft {
  const source = payload || {};
  const asString = (key: string, fallback = "") =>
    source[key] == null || source[key] === "" ? fallback : String(source[key]);

  return {
    org_unit_id: asString("org_unit_id"),
    position_id: asString("position_id"),
    employment_rate: asString("employment_rate", "1"),
    to_org_unit_id: asString("to_org_unit_id"),
    to_position_id: asString("to_position_id"),
    to_rate: asString("to_rate", asString("to_employment_rate")),
    termination_reason: asString("termination_reason"),
    concurrent_rate: asString("concurrent_rate", "0.5"),
    total_rate: asString("total_rate"),
    remaining_rate: asString("remaining_rate"),
  };
}

/** Build apply-compatible payload. Does not enforce business rules — backend validates. */
export function buildItemPayload(
  itemTypeCode: string,
  draft: ItemPayloadDraft,
): Record<string, unknown> {
  const type = String(itemTypeCode || "").trim().toUpperCase() as PersonnelOrderType;
  const payload: Record<string, unknown> = {};

  if (type === "HIRE") {
    const orgUnitId = optionalNumber(draft.org_unit_id);
    const positionId = optionalNumber(draft.position_id);
    const rate = optionalNumber(draft.employment_rate);
    if (orgUnitId != null) payload.org_unit_id = orgUnitId;
    if (positionId != null) payload.position_id = positionId;
    if (rate != null) payload.employment_rate = rate;
    return payload;
  }

  if (type === "TRANSFER") {
    const toOrg = optionalNumber(draft.to_org_unit_id);
    const toPos = optionalNumber(draft.to_position_id);
    const toRate = optionalNumber(draft.to_rate);
    if (toOrg != null) payload.to_org_unit_id = toOrg;
    if (toPos != null) payload.to_position_id = toPos;
    if (toRate != null) payload.to_rate = toRate;
    return payload;
  }

  if (type === "TERMINATION") {
    const reason = String(draft.termination_reason || "").trim();
    if (reason) payload.termination_reason = reason;
    return payload;
  }

  if (type === "CONCURRENT_DUTY_START") {
    const concurrentRate = optionalNumber(draft.concurrent_rate);
    const totalRate = optionalNumber(draft.total_rate);
    if (concurrentRate != null) payload.concurrent_rate = concurrentRate;
    if (totalRate != null) payload.total_rate = totalRate;
    return payload;
  }

  if (type === "CONCURRENT_DUTY_END") {
    const remaining = optionalNumber(draft.remaining_rate);
    const concurrentRate = optionalNumber(draft.concurrent_rate);
    const totalRate = optionalNumber(draft.total_rate);
    if (remaining != null) payload.remaining_rate = remaining;
    if (concurrentRate != null) payload.concurrent_rate = concurrentRate;
    if (totalRate != null) payload.total_rate = totalRate;
    return payload;
  }

  return payload;
}
