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

function normalizeApiBase(base) {
  return base.trim().replace(/\/+$/, "");
}

function resolveApiUrl(path, { base, origin = "https://mmc.004.kz" } = {}) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const trimmed = normalizeApiBase(base);

  if (/^https?:\/\//i.test(trimmed)) {
    return `${trimmed}${normalizedPath}`;
  }

  const prefix = trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  return `${origin}${prefix}${normalizedPath}`;
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

  if (failed === 0) {
    console.log("OK   apiBase.ts static env access for NEXT_PUBLIC_API_BASE_URL");
  }

  return failed;
}

const cases = [
  {
    name: "prod relative /api",
    base: "/api",
    path: "/directory/employees",
    want: "https://mmc.004.kz/api/directory/employees",
  },
  {
    name: "prod absolute base",
    base: "https://mmc.004.kz/api",
    path: "/auth/login",
    want: "https://mmc.004.kz/api/auth/login",
  },
  {
    name: "prod auth/me relative /api",
    base: "/api",
    path: "/auth/me",
    want: "https://mmc.004.kz/api/auth/me",
  },
  {
    name: "dev direct backend",
    base: "http://127.0.0.1:8000",
    path: "/tasks",
    want: "http://127.0.0.1:8000/tasks",
  },
];

let failed = verifyApiBaseSource();

for (const c of cases) {
  const got = resolveApiUrl(c.path, { base: c.base });
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
