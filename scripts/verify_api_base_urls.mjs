/**
 * Verify resolveApiUrl join logic and apiBase.ts env inlining rules.
 * Run: node scripts/verify_api_base_urls.mjs
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");
const apiBasePath = path.join(repoRoot, "corpsite-ui", "lib", "apiBase.ts");

const DEFAULT_DEV_BACKEND = "http://127.0.0.1:8000";

function normalizeApiBase(base) {
  return base.trim().replace(/\/+$/, "");
}

function isAbsoluteHttpUrl(base) {
  return /^https?:\/\//i.test(base);
}

function isRelativeApiPrefix(base) {
  const normalized = normalizeApiBase(base);
  return normalized === "/api" || normalized === "api";
}

function clientPublicBase(base, nodeEnv, { localHost = false } = {}) {
  const raw = normalizeApiBase(base ?? "");

  if (nodeEnv === "development" || localHost) {
    if (!raw) return DEFAULT_DEV_BACKEND;
    if (isRelativeApiPrefix(raw)) return DEFAULT_DEV_BACKEND;
    return raw;
  }

  return raw || DEFAULT_DEV_BACKEND;
}

function serverSideBackendBase({ base, backendUrl = "" }) {
  const backend = normalizeApiBase(backendUrl ?? "");
  if (backend) return backend;

  const publicBase = normalizeApiBase(base ?? "");
  if (publicBase && isAbsoluteHttpUrl(publicBase)) return publicBase;

  return DEFAULT_DEV_BACKEND;
}

function resolveApiUrl(
  path,
  {
    base = "",
    origin = "https://mmc.004.kz",
    nodeEnv = "production",
    serverSide = false,
    backendUrl = "",
    hasWindow = true,
    localHost = false,
  } = {},
) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  if (serverSide) {
    return `${serverSideBackendBase({ base, backendUrl })}${normalizedPath}`;
  }

  const resolvedBase = clientPublicBase(base, nodeEnv, { localHost: localHost || (hasWindow && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(origin)) });

  if (isAbsoluteHttpUrl(resolvedBase)) {
    return `${resolvedBase}${normalizedPath}`;
  }

  const prefix = resolvedBase.startsWith("/") ? resolvedBase : `/${resolvedBase}`;

  if (hasWindow) {
    return `${origin}${prefix}${normalizedPath}`;
  }

  return `${serverSideBackendBase({ base, backendUrl })}${normalizedPath}`;
}

function verifyApiBaseSource() {
  const src = fs.readFileSync(apiBasePath, "utf8");
  let failed = 0;

  if (!src.includes("process.env.NEXT_PUBLIC_API_BASE_URL")) {
    failed += 1;
    console.error(
      "FAIL apiBase.ts must use static process.env.NEXT_PUBLIC_API_BASE_URL for client inlining",
    );
  }

  if (/process\.env\s*\[\s*['"]NEXT_PUBLIC_API_BASE_URL['"]\s*\]/.test(src)) {
    failed += 1;
    console.error("FAIL apiBase.ts must not use dynamic process.env['NEXT_PUBLIC_API_BASE_URL']");
  }

  if (/trimEnv\s*\(\s*['"]NEXT_PUBLIC_API_BASE_URL['"]\s*\)/.test(src)) {
    failed += 1;
    console.error("FAIL apiBase.ts must not read NEXT_PUBLIC_API_BASE_URL via trimEnv()");
  }

  if (/function\s+trimEnv\s*\(/.test(src)) {
    failed += 1;
    console.error("FAIL apiBase.ts must not use generic trimEnv(name) for NEXT_PUBLIC_*");
  }

  if (!src.includes("process.env.BACKEND_URL")) {
    failed += 1;
    console.error("FAIL apiBase.ts must keep static process.env.BACKEND_URL for SSR");
  }

  if (!src.includes("process.env.NODE_ENV")) {
    failed += 1;
    console.error("FAIL apiBase.ts must gate dev /api override on process.env.NODE_ENV");
  }

  if (failed === 0) {
    console.log("OK   apiBase.ts static env access for NEXT_PUBLIC_API_BASE_URL");
  }

  return failed;
}

const cases = [
  {
    name: "dev empty base → direct backend auth/me",
    base: "",
    path: "/auth/me",
    nodeEnv: "development",
    want: `${DEFAULT_DEV_BACKEND}/auth/me`,
  },
  {
    name: "dev /api → direct backend auth/me",
    base: "/api",
    path: "/auth/me",
    nodeEnv: "development",
    want: `${DEFAULT_DEV_BACKEND}/auth/me`,
  },
  {
    name: "dev api (no slash) → direct backend auth/me",
    base: "api",
    path: "/auth/me",
    nodeEnv: "development",
    want: `${DEFAULT_DEV_BACKEND}/auth/me`,
  },
  {
    name: "prod /api + localhost origin → local override to direct backend",
    base: "/api",
    path: "/auth/me",
    nodeEnv: "production",
    origin: "http://localhost:3000",
    want: `${DEFAULT_DEV_BACKEND}/auth/me`,
  },
  {
    name: "absolute http://127.0.0.1:8000 → direct backend auth/me",
    base: "http://127.0.0.1:8000",
    path: "/auth/me",
    nodeEnv: "development",
    want: "http://127.0.0.1:8000/auth/me",
  },
  {
    name: "serverSide BACKEND_URL bypasses /api",
    base: "/api",
    path: "/auth/me",
    nodeEnv: "production",
    serverSide: true,
    backendUrl: "http://127.0.0.1:8000",
    want: "http://127.0.0.1:8000/auth/me",
  },
  {
    name: "serverSide no BACKEND_URL → DEFAULT_DEV_BACKEND",
    base: "/api",
    path: "/auth/me",
    nodeEnv: "production",
    serverSide: true,
    backendUrl: "",
    want: `${DEFAULT_DEV_BACKEND}/auth/me`,
  },
  {
    name: "prod relative /api",
    base: "/api",
    path: "/directory/employees",
    nodeEnv: "production",
    want: "https://mmc.004.kz/api/directory/employees",
  },
  {
    name: "prod absolute base",
    base: "https://mmc.004.kz/api",
    path: "/auth/login",
    nodeEnv: "production",
    want: "https://mmc.004.kz/api/auth/login",
  },
  {
    name: "prod auth/me relative /api",
    base: "/api",
    path: "/auth/me",
    nodeEnv: "production",
    want: "https://mmc.004.kz/api/auth/me",
  },
  {
    name: "dev direct backend",
    base: "http://127.0.0.1:8000",
    path: "/tasks",
    nodeEnv: "development",
    want: "http://127.0.0.1:8000/tasks",
  },
];

let failed = verifyApiBaseSource();

for (const c of cases) {
  const got = resolveApiUrl(c.path, c);
  if (got !== c.want) {
    failed += 1;
    console.error(`FAIL ${c.name}\n  want: ${c.want}\n  got:  ${got}`);
  } else {
    console.log(`OK   ${c.name}`);
  }
}

const legacyBug = new URL("/auth/login", "https://mmc.004.kz/api").toString();
if (legacyBug === "https://mmc.004.kz/auth/login") {
  console.log("OK   legacy new URL() bug reproduced (drops /api)");
} else {
  failed += 1;
  console.error(`FAIL legacy new URL() bug\n  got: ${legacyBug}`);
}

if (failed > 0) {
  process.exitCode = 1;
  console.error(`\n${failed} case(s) failed`);
} else {
  console.log(`\nAll checks passed (${cases.length} URL cases + source guard)`);
}
