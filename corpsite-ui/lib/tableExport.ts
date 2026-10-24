import { buildHeaders } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";

export const EXCEL_BUTTON_CLASS = "rounded-lg border border-emerald-300 bg-emerald-100 px-3 py-2 text-[length:inherit] font-normal text-emerald-950 transition hover:bg-emerald-200 disabled:opacity-50 dark:border-emerald-300 dark:bg-emerald-100 dark:text-emerald-950 dark:hover:bg-emerald-200";
export const EMPTY_EXPORT_MESSAGE = "Нет записей для выгрузки по текущим фильтрам.";
export type ExcelCell = string | number | boolean | null;
export type ExcelTable = { headers: string[]; rows: ExcelCell[][] };
export type ExportPage<T> = { items: T[]; total?: number };

/** Fetch from zero without touching the table's URL, state or current page. */
export async function allExportPages<T>(load: (page: { limit: number; offset: number }) => Promise<ExportPage<T>>, limit = 50): Promise<T[]> {
  const rows: T[] = [];
  while (true) {
    const page = await load({ limit, offset: rows.length });
    if (!page.items.length) {
      if (page.total != null && rows.length < page.total) throw new Error("Список изменился во время выгрузки. Повторите выгрузку.");
      break;
    }
    rows.push(...page.items);
    if (page.total != null ? rows.length >= page.total : page.items.length < limit) break;
  }
  return rows;
}

export function normalizeExportPage<T>(body: T[] | { items?: T[]; data?: T[]; total?: number }): ExportPage<T> {
  if (Array.isArray(body)) return { items: body, total: body.length };
  return { items: body.items ?? body.data ?? [], total: body.total };
}

export function downloadExcelBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  try {
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
  } finally {
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

export async function downloadTableExcel(table: ExcelTable, filename: string): Promise<void> {
  if (!table.rows.length) throw new Error(EMPTY_EXPORT_MESSAGE);
  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
  const devUserId = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  const extraHeaders: Record<string, string> = { "Content-Type": "application/json" };
  if (appEnv !== "prod" && appEnv !== "production" && devUserId) extraHeaders["X-User-Id"] = devUserId;
  const response = await fetch(resolveApiUrl("/exports/table.xlsx"), {
    method: "POST",
    headers: buildHeaders(extraHeaders),
    body: JSON.stringify(table),
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Не удалось выгрузить список в Excel. Попробуйте ещё раз.");
  downloadExcelBlob(await response.blob(), filename);
}
