export const REPORT_LINK_EMPTY_LABEL = "пока нет";

export const REPORT_LINK_NETWORK_HINT =
  "Сетевой путь, скопируйте и откройте в проводнике";

const REPORT_LINK_KEYS = [
  "report_link",
  "reportLink",
  "report_url",
  "reportUrl",
  "link",
  "url",
] as const;

export function resolveTaskReportLink(src: unknown): string {
  if (!src || typeof src !== "object") return "";

  const obj = src as Record<string, unknown>;
  for (const key of REPORT_LINK_KEYS) {
    const value = obj[key];
    if (typeof value === "string") {
      const trimmed = value.trim();
      if (trimmed) return trimmed;
    }
  }

  return "";
}

export function isHttpUrl(value: string): boolean {
  return /^https?:\/\//i.test((value || "").trim());
}

export function isUncPath(value: string): boolean {
  const v = (value || "").trim();
  if (!v.startsWith("\\")) return false;

  const withoutLeading = v.replace(/^\\+/, "");
  return withoutLeading.includes("\\");
}

export function isWindowsDrivePath(value: string): boolean {
  return /^[a-zA-Z]:[\\/]/.test((value || "").trim());
}

export function isLocalOrNetworkPath(value: string): boolean {
  const v = (value || "").trim();
  if (!v) return false;
  return isUncPath(v) || isWindowsDrivePath(v);
}

export function reportLinkDisplayText(link: string): string {
  const trimmed = (link || "").trim();
  return trimmed || REPORT_LINK_EMPTY_LABEL;
}

export function reportLinkHint(link: string): string | null {
  const trimmed = (link || "").trim();
  if (!trimmed) return null;
  if (isHttpUrl(trimmed)) return null;
  if (isLocalOrNetworkPath(trimmed)) return REPORT_LINK_NETWORK_HINT;
  return "Ссылка не является http(s).";
}

export function shouldShowReportSection(src: unknown): boolean {
  if (!src || typeof src !== "object") return false;

  const obj = src as Record<string, unknown>;
  if (resolveTaskReportLink(obj)) return true;
  if (obj.report_submitted_at) return true;
  if (obj.report_approved_at) return true;
  if (obj.requires_report === true) return true;

  return false;
}
