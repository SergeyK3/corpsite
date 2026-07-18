export function formatImportBatchLabel(batchId: number): string {
  return `Импорт ${batchId}`;
}

export function formatImportBatchNumber(batchId: number): string {
  return String(batchId);
}

export function formatImportBatchDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("ru-RU");
  } catch {
    return value;
  }
}
