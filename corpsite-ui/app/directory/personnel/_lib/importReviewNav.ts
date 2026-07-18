export type ImportReviewMode = "personnel" | "declaration" | "technical";

export const IMPORT_REVIEW_MODE_TABS = [
  { key: "import-review-personnel", mode: "personnel" as const, title: "Мед. категории" },
  { key: "import-review-declaration", mode: "declaration" as const, title: "Декларации" },
  { key: "import-review-technical", mode: "technical" as const, title: "Технические" },
];

export function parseImportReviewMode(value: string | null | undefined): ImportReviewMode {
  if (value === "declaration" || value === "technical") return value;
  return "personnel";
}

export function buildImportReviewModeHref(batchId: number, mode: ImportReviewMode): string {
  return `/directory/personnel/import/${batchId}/review?mode=${mode}`;
}

export function isImportReviewListPath(pathname: string, batchId: number): boolean {
  return pathname === `/directory/personnel/import/${batchId}/review`;
}

export function isImportReviewModeNavActive(
  pathname: string,
  mode: ImportReviewMode,
  batchId: number | null,
  searchParams: Pick<URLSearchParams, "get">,
): boolean {
  if (batchId == null) return false;
  if (!isImportReviewListPath(pathname, batchId)) return false;
  return parseImportReviewMode(searchParams.get("mode")) === mode;
}
