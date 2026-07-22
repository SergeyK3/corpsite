/**
 * ADR-059 Phase 2 — capture Import Review exception diff viewer screenshots.
 */
import { chromium } from "playwright";
import { execSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const outDir = path.resolve(__dirname, "../adr059-phase2-ui-verify");
const baseUrl = process.env.CAPTURE_BASE_URL ?? "http://localhost:3000";
const apiUrl = process.env.CAPTURE_API_URL ?? "http://localhost:8000";
const devUserId = process.env.CAPTURE_DEV_USER_ID ?? "34";
const batchIdEnv = process.env.CAPTURE_BATCH_ID ?? null;

function mintDevJwt(userId) {
  const python = path.join(repoRoot, "venv", "Scripts", "python.exe");
  const cmd = `from app.auth import create_access_token; print(create_access_token(${Number(userId)}))`;
  return execSync(`"${python}" -c "${cmd}"`, { cwd: repoRoot, encoding: "utf8" }).trim();
}

async function login(page, token) {
  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate(
    ({ tokenValue, loginValue }) => {
      localStorage.setItem("access_token", tokenValue);
      localStorage.setItem("login", loginValue);
    },
    { tokenValue: token, loginValue: "pall_head_34" },
  );
}

async function apiGet(token, urlPath) {
  const res = await fetch(`${apiUrl}${urlPath}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`GET ${urlPath} failed: HTTP ${res.status}`);
  return res.json();
}

async function discoverBatch(token) {
  if (batchIdEnv) return Number(batchIdEnv);
  const data = await apiGet(token, "/directory/personnel/import/batches?limit=100&offset=0");
  const batches = data.items || [];
  for (const batch of batches) {
    const list = await apiGet(token, `/directory/personnel/import/batches/${batch.batch_id}/review-exceptions?limit=50`);
    const statuses = new Set((list.items || []).map((item) => item.diff_status));
    if (statuses.has("NEW") || statuses.has("CONFLICT") || statuses.has("REMOVED")) {
      return batch.batch_id;
    }
  }
  if (batches[0]?.batch_id) return batches[0].batch_id;
  throw new Error("No import batch found");
}

async function pickExceptionKey(page, batchId, diffStatus) {
  return page.evaluate(
    async ({ id, status }) => {
      const token = localStorage.getItem("access_token");
      const resp = await fetch(
        `http://localhost:8000/directory/personnel/import/batches/${id}/review-exceptions?diff_status=${encodeURIComponent(status)}&limit=1`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/json",
            "X-User-Id": "34",
          },
        },
      );
      if (!resp.ok) return null;
      const body = await resp.json();
      return body.items?.[0]?.exception_key ?? null;
    },
    { id: batchId, status: diffStatus },
  );
}

async function main() {
  await mkdir(outDir, { recursive: true });
  const token = mintDevJwt(devUserId);
  const batchId = batchIdEnv ? Number(batchIdEnv) : 1361;

  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
  const page = await context.newPage();
  await login(page, token);

  for (const [status, filename] of [
    ["NEW", "01-review-exception-new.png"],
    ["CONFLICT", "02-review-exception-conflict.png"],
    ["REMOVED", "03-review-exception-removed.png"],
  ]) {
    const exceptionKey = await pickExceptionKey(page, batchId, status);
    if (!exceptionKey) {
      console.warn(`Skip ${status}: no exception in batch ${batchId}`);
      continue;
    }
    const url = `${baseUrl}/directory/personnel/import/${batchId}/review?adr059_exception=${encodeURIComponent(exceptionKey)}`;
    await page.goto(url, { waitUntil: "networkidle", timeout: 120000 });
    await page.waitForSelector('[data-testid="import-review-exception-drawer"]', { timeout: 30000 });
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(outDir, filename), fullPage: true });
    console.log(`Saved ${filename} (${exceptionKey})`);
  }

  await browser.close();
  console.log(JSON.stringify({ batchId, outDir }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
