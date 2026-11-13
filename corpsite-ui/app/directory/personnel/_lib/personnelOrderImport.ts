export function isImportedPersonnelOrder(
  orderNumber: string | null | undefined,
  storage: Record<string, unknown> | null | undefined,
): boolean {
  const number = String(orderNumber || "").trim().toUpperCase();
  return number.startsWith("CSV-PILOT-")
    || number.startsWith("PERSONNEL-IMPORT-")
    || Boolean(storage?.import_source_order_number)
    || Boolean(storage?.import_source_id);
}
