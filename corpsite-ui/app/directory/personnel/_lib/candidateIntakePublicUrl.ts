/** Build a candidate URL only when this stand has a phone-accessible origin. */
export function candidateIntakePublicUrl(
  path: string | null | undefined,
  configuredBaseUrl: string | null | undefined,
  currentOrigin: string | null | undefined,
): string | null {
  const intakePath = String(path || "").trim();
  if (!/^\/intake\/[A-Za-z0-9_-]+$/.test(intakePath)) return null;

  const configured = String(configuredBaseUrl || "").trim();
  const base = String(configured || currentOrigin || "").trim();
  try {
    const url = new URL(base);
    const host = url.hostname.toLowerCase();
    if (!(["http:", "https:"].includes(url.protocol))) return null;
    if (host === "0.0.0.0") return null;
    if (configured && (host === "localhost" || host === "::1" || /^127\./.test(host))) return null;
    if (url.username || url.password || url.search || url.hash || url.pathname !== "/") return null;
    return `${url.origin}${intakePath}`;
  } catch {
    return null;
  }
}
