import type { NormalizedRecord } from "./importApi.client";

const MASKED_IIN_PATTERN = /\*/;

/** Never render masked placeholders in authenticated personnel UI. */
export function displayNormalizedRecordIin(
  record: Pick<NormalizedRecord, "iin"> | null | undefined
): string {
  const iin = String(record?.iin ?? "").trim();
  if (!iin || MASKED_IIN_PATTERN.test(iin)) {
    return "—";
  }
  return iin;
}

export function isMaskedIin(value: string | null | undefined): boolean {
  const iin = String(value ?? "").trim();
  return !iin || MASKED_IIN_PATTERN.test(iin);
}
