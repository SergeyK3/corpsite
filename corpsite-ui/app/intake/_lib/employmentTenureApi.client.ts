import { readJsonSafe, toApiError } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";
import {
  isValidPersonnelDayDateIso,
  parsePersonnelDayDateInput,
} from "@/lib/personnelDayDate";

import type { IntakeEmploymentBiographyEntry } from "./intakeEmploymentBiography";
import { ensureEmploymentBiographyRecordId } from "./intakeEmploymentBiography";
import type {
  EmploymentTenureCalculation,
  EmploymentTenureRecordInput,
} from "./employmentTenureFormat";

function publicHeaders(): Record<string, string> {
  return { Accept: "application/json", "Content-Type": "application/json" };
}

/** Normalize stored intake date to canonical ISO for the tenure API; empty -> null. */
export function normalizeTenureDateForApi(value: string | null | undefined): string | null {
  const text = String(value ?? "").trim();
  if (!text) return null;
  if (isValidPersonnelDayDateIso(text)) return text;
  const parsed = parsePersonnelDayDateInput(text);
  if (isValidPersonnelDayDateIso(parsed)) return parsed;
  return null;
}

export function prepareEmploymentTenureRecords(
  items: readonly IntakeEmploymentBiographyEntry[],
): EmploymentTenureRecordInput[] {
  return items.map((item, index) => ({
    record_id: ensureEmploymentBiographyRecordId(item, index),
    organization: item.organization,
    position: item.position,
    year_from: normalizeTenureDateForApi(item.year_from),
    year_to: normalizeTenureDateForApi(item.year_to),
    reason_for_leaving: item.reason_for_leaving,
  }));
}

export async function calculateEmploymentTenure(
  items: readonly IntakeEmploymentBiographyEntry[],
  opts?: { calculationDate?: string | null; serverSide?: boolean },
): Promise<EmploymentTenureCalculation> {
  const path = "/intake/employment-tenure/calculate";
  const records = prepareEmploymentTenureRecords(items);
  const requestBody: { records: EmploymentTenureRecordInput[]; calculation_date?: string } = { records };
  const calculationDate = String(opts?.calculationDate ?? "").trim();
  if (calculationDate) {
    requestBody.calculation_date = calculationDate;
  }
  const res = await fetch(resolveApiUrl(path, { serverSide: opts?.serverSide }), {
    method: "POST",
    headers: publicHeaders(),
    body: JSON.stringify(requestBody),
    cache: "no-store",
  });
  const responseBody = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, responseBody, { method: "POST", url: path });
  return responseBody as EmploymentTenureCalculation;
}

export type { EmploymentTenureCalculation, EmploymentTenureRecordInput, EmploymentTenureRecordResult, EmploymentTenureYmd } from "./employmentTenureFormat";
