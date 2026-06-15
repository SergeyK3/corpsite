/**
 * Verify resolveApiUrl join logic (no TS build required).
 * Run: node scripts/verify_api_base_urls.mjs
 */

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
    name: "dev direct backend",
    base: "http://127.0.0.1:8000",
    path: "/tasks",
    want: "http://127.0.0.1:8000/tasks",
  },
  {
    name: "prod absolute base auth login",
    base: "https://mmc.004.kz/api",
    path: "/auth/login",
    want: "https://mmc.004.kz/api/auth/login",
  },
];

let failed = 0;

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
  console.log(`\nAll ${cases.length} cases passed`);
}
