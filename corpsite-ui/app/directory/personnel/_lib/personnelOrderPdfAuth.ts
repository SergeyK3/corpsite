import { sanitizeBearerToken } from "@/lib/bearerToken";

export type PersonnelOrderPdfAuthContext = {
  authorizationHeader: string | null;
  bearerToken: string | null;
  /** Dev-only X-User-Id passthrough (never in production). */
  devUserId: string | null;
  requestingUserId: string | null;
};

function decodeJwtSub(token: string): string | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payloadB64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = payloadB64 + "=".repeat((4 - (payloadB64.length % 4)) % 4);
    const json = Buffer.from(padded, "base64").toString("utf8");
    const payload = JSON.parse(json) as { sub?: unknown; user_id?: unknown };
    const sub = payload.sub ?? payload.user_id;
    if (sub == null) return null;
    const text = String(sub).trim();
    return text || null;
  } catch {
    return null;
  }
}

function isProductionAppEnv(): boolean {
  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || process.env.NODE_ENV || "").trim().toLowerCase();
  return appEnv === "prod" || appEnv === "production";
}

/**
 * Extract caller auth from the PDF Route Handler request.
 * Does not log tokens. Relies on the same Bearer model as the rest of the UI.
 */
export function extractPersonnelOrderPdfAuth(request: Request): PersonnelOrderPdfAuthContext {
  const authorizationHeader = request.headers.get("authorization");
  const bearerToken = sanitizeBearerToken(
    authorizationHeader?.replace(/^Bearer\s+/i, "") ?? "",
  );
  const token = bearerToken || null;

  let devUserId: string | null = null;
  if (!isProductionAppEnv()) {
    const fromHeader = String(request.headers.get("x-user-id") || "").trim();
    const fromEnv = String(process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
    devUserId = fromHeader || fromEnv || null;
  }

  const requestingUserId = (token ? decodeJwtSub(token) : null) || devUserId;

  return {
    authorizationHeader: token ? `Bearer ${token}` : null,
    bearerToken: token,
    devUserId,
    requestingUserId,
  };
}

export function isPersonnelOrderPdfAuthenticated(auth: PersonnelOrderPdfAuthContext): boolean {
  return Boolean(auth.bearerToken || auth.devUserId);
}
