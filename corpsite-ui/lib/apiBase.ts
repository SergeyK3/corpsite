/**
 * Same-origin API prefix support.
 *
 * Dev (split ports): NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
 * Prod (nginx /api):  NEXT_PUBLIC_API_BASE_URL=/api
 * SSR on VPS:         BACKEND_URL=http://127.0.0.1:8000 (direct to FastAPI, no /api)
 */

const DEFAULT_DEV_BACKEND = "http://127.0.0.1:8000";

function trimEnv(name: string): string {
  return (process.env[name] ?? "").toString().trim();
}

export function normalizeApiBase(base: string): string {
  return base.trim().replace(/\/+$/, "");
}

function isAbsoluteHttpUrl(base: string): boolean {
  return /^https?:\/\//i.test(base);
}

function serverSideBackendBase(): string {
  const backend = normalizeApiBase(trimEnv("BACKEND_URL"));
  if (backend) return backend;

  const publicBase = normalizeApiBase(trimEnv("NEXT_PUBLIC_API_BASE_URL"));
  if (publicBase && isAbsoluteHttpUrl(publicBase)) return publicBase;

  return DEFAULT_DEV_BACKEND;
}

function clientPublicBase(): string {
  return normalizeApiBase(trimEnv("NEXT_PUBLIC_API_BASE_URL")) || DEFAULT_DEV_BACKEND;
}

/**
 * Build a full request URL for a backend path such as `/directory/employees`.
 */
export function resolveApiUrl(
  path: string,
  opts?: {
    /** Prefer BACKEND_URL for Next.js server-side fetch (bypass nginx /api). */
    serverSide?: boolean;
  },
): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  if (opts?.serverSide) {
    return `${serverSideBackendBase()}${normalizedPath}`;
  }

  const base = clientPublicBase();

  if (isAbsoluteHttpUrl(base)) {
    return `${base}${normalizedPath}`;
  }

  const prefix = base.startsWith("/") ? base : `/${base}`;

  if (typeof window !== "undefined") {
    return `${window.location.origin}${prefix}${normalizedPath}`;
  }

  // SSR without window: never proxy through public /api without an origin.
  return `${serverSideBackendBase()}${normalizedPath}`;
}

export function buildUrl(
  path: string,
  query?: Record<string, string | number | boolean | undefined | null>,
  opts?: { serverSide?: boolean },
): URL {
  const url = new URL(resolveApiUrl(path, opts));

  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null) continue;
      url.searchParams.set(k, String(v));
    }
  }

  return url;
}
