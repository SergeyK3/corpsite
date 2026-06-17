/**
 * Sanitize JWT / bearer token before putting it in Authorization.
 * CR/LF in the header value makes fetch fail with "Failed to fetch".
 */
export function sanitizeBearerToken(raw: unknown): string {
  if (!raw) return "";
  let s = String(raw);

  s = s.replace(/\uFEFF/g, "").replace(/\u0000/g, "");
  s = s.replace(/[\u0000-\u001F\u007F]/g, "");
  s = s.trim();

  if (/^bearer\s+/i.test(s)) {
    s = s.replace(/^bearer\s+/i, "").trim();
  }

  return s;
}
