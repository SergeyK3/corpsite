import type { PersonnelOrderType } from "./personnelOrderLabels";

export type ItemPayloadDraft = {
  work_periods?: Array<{ start: string; end: string; days: string }>;
  leave_start?: string;
  leave_end?: string;
  leave_days?: string;
  work_period_start?: string;
  work_period_end?: string;
  work_period_days?: string;
  application_date?: string;
  application_number?: string;
  vacation_benefit_applicable?: boolean;
  vacation_benefit_rule?: string;
  leave_note?: string;
  person_id?: string;
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
    leave_start: "", leave_end: "", leave_days: "", work_period_start: "", work_period_end: "", work_period_days: "", work_periods: [{ start: "", end: "", days: "" }],
    application_date: "", application_number: "", vacation_benefit_applicable: false, vacation_benefit_rule: "", leave_note: "",
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

  const sourcePeriods = Array.isArray(source.work_periods) ? source.work_periods : [];
  const workPeriods = sourcePeriods
    .filter((period): period is Record<string, unknown> => Boolean(period) && typeof period === "object")
    .map((period) => ({ start: String(period.start || ""), end: String(period.end || ""), days: String(period.days || "") }));
  if (workPeriods.length === 0 && (source.work_period_start || source.work_period_end || source.work_period_days)) {
    workPeriods.push({ start: String(source.work_period_start || ""), end: String(source.work_period_end || ""), days: String(source.work_period_days || "") });
  }
  return {
    work_periods: workPeriods.length ? workPeriods : [{ start: "", end: "", days: "" }],
    leave_start: asString("leave_start"), leave_end: asString("leave_end"), leave_days: asString("leave_days"),
    work_period_start: asString("work_period_start"), work_period_end: asString("work_period_end"), work_period_days: asString("work_period_days"),
    application_date: asString("basis_date", asString("application_date")), application_number: asString("basis_number", asString("application_number")),
    vacation_benefit_applicable: source.vacation_benefit_applicable === true,
    vacation_benefit_rule: asString("vacation_benefit_rule"), leave_note: asString("note"),
    org_unit_id: asString("org_unit_id"),
    position_id: asString("position_id"),
    employment_rate: asString("employment_rate", "1"),
    person_id: asString("person_id"),
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

  if (type === "LEAVE.ANNUAL.GRANT" || type === "LEAVE.UNPAID.GRANT") {
    const leaveStart = String(draft.leave_start || "").trim();
    const leaveEnd = String(draft.leave_end || "").trim();
    const explicitLeaveDays = optionalNumber(draft.leave_days);
    const startMs = Date.parse(`${leaveStart}T00:00:00`);
    const endMs = Date.parse(`${leaveEnd}T00:00:00`);
    const leaveDays = explicitLeaveDays ?? (Number.isFinite(startMs) && Number.isFinite(endMs) ? Math.floor((endMs - startMs) / 86400000) + 1 : undefined);
    payload.leave_start = leaveStart;
    payload.leave_end = leaveEnd;
    if (leaveDays != null) payload.leave_days = leaveDays;
    payload.basis = { kind: "PERSONAL_APPLICATION", date: String(draft.application_date || "").trim(), number: String(draft.application_number || "").trim() || null };
    if (String(draft.leave_note || "").trim()) payload.note = String(draft.leave_note).trim();
    if (type === "LEAVE.ANNUAL.GRANT") {
      const periods = (draft.work_periods && draft.work_periods.length ? draft.work_periods : [{ start: String(draft.work_period_start || ""), end: String(draft.work_period_end || ""), days: String(draft.work_period_days || "") }])
        .map((period) => ({ start: String(period.start || "").trim(), end: String(period.end || "").trim(), days: optionalNumber(period.days) }));
      payload.work_periods = periods;
      payload.work_period_start = periods[0]?.start || "";
      payload.work_period_end = periods[0]?.end || "";
      payload.calculation_status = "REQUESTED";
      payload.vacation_benefit_applicable = Boolean(draft.vacation_benefit_applicable);
      if (draft.vacation_benefit_applicable) payload.vacation_benefit_rule = String(draft.vacation_benefit_rule || "").trim();
    }
    return payload;
  }

  if (type === "HIRE") {
    const orgUnitId = optionalNumber(draft.org_unit_id);
    const positionId = optionalNumber(draft.position_id);
    const rate = optionalNumber(draft.employment_rate);
    if (orgUnitId != null) payload.org_unit_id = orgUnitId;
    if (positionId != null) payload.position_id = positionId;
    if (rate != null) payload.employment_rate = rate;
    const personId = optionalNumber(draft.person_id);
    if (personId != null) payload.person_id = personId;
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
