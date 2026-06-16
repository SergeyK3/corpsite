/**
 * Same-origin API prefix support.
 *
 * Dev (split ports): NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
 * Prod (nginx /api):  NEXT_PUBLIC_API_BASE_URL=/api
 * SSR on VPS:         BACKEND_URL=http://127.0.0.1:8000 (direct to FastAPI, no /api)
 *
 * In development (or on localhost), relative `/api` is overridden to DEFAULT_DEV_BACKEND.
 *
 * Client bundle MUST use static process.env.NEXT_PUBLIC_API_BASE_URL so Next.js
 * can inline the value at build time (dynamic process.env[name] is not inlined).
 */

const DEFAULT_DEV_BACKEND = "http://127.0.0.1:8000";

const DEV_API_BASE_OVERRIDE_WARN =
  "[corpsite] NEXT_PUBLIC_API_BASE_URL=/api in development; using http://127.0.0.1:8000 instead.";

let devApiBaseOverrideWarned = false;

export function normalizeApiBase(base: string): string {
  return base.trim().replace(/\/+$/, "");
}

function isAbsoluteHttpUrl(base: string): boolean {
  return /^https?:\/\//i.test(base);
}

/** Server-only: direct FastAPI URL for SSR fetches. */
function readBackendUrl(): string {
  return normalizeApiBase(String(process.env.BACKEND_URL ?? "").trim());
}

/**
 * Public API base from build-time env. Static property access is required for
 * client bundles; do not replace with process.env[name].
 */
function readPublicApiBaseUrl(): string {
  return normalizeApiBase(String(process.env.NEXT_PUBLIC_API_BASE_URL ?? "").trim());
}

function isDevelopment(): boolean {
  return process.env.NODE_ENV === "development";
}

/** True when the UI is opened on a local dev host (works even under `next start`). */
function isLocalFrontendHost(): boolean {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  return host === "localhost" || host === "127.0.0.1";
}

function shouldOverrideRelativeApiForLocalDev(): boolean {
  return isDevelopment() || isLocalFrontendHost();
}

function isRelativeApiPrefix(base: string): boolean {
  const normalized = normalizeApiBase(base);
  return normalized === "/api" || normalized === "api";
}

function warnDevApiBaseOverrideOnce(): void {
  if (devApiBaseOverrideWarned) return;
  devApiBaseOverrideWarned = true;
  console.warn(DEV_API_BASE_OVERRIDE_WARN);
}

function serverSideBackendBase(): string {
  const backend = readBackendUrl();
  if (backend) return backend;

  const publicBase = readPublicApiBaseUrl();
  if (publicBase && isAbsoluteHttpUrl(publicBase)) return publicBase;

  return DEFAULT_DEV_BACKEND;
}

function clientPublicBase(): string {
  const raw = readPublicApiBaseUrl();

  if (shouldOverrideRelativeApiForLocalDev()) {
    if (!raw) return DEFAULT_DEV_BACKEND;
    if (isRelativeApiPrefix(raw)) {
      warnDevApiBaseOverrideOnce();
      return DEFAULT_DEV_BACKEND;
    }
    return raw;
  }

  return raw || DEFAULT_DEV_BACKEND;
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
