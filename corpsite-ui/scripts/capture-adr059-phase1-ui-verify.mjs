/**
 * ADR-059 Phase 1 UI verification — auto-complete after "Пересчитать diff".
 * Run: node scripts/capture-adr059-phase1-ui-verify.mjs
 */
import { chromium } from "playwright";
import { execSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const outDir = path.resolve(__dirname, "../adr059-phase1-ui-verify");
const baseUrl = process.env.CAPTURE_BASE_URL ?? "http://localhost:3000";
const batchId = process.env.CAPTURE_BATCH_ID ?? "1357";
const devUserId = process.env.CAPTURE_DEV_USER_ID ?? "34";

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

async function waitForReviewReady(page) {
  await page.waitForSelector("text=Сравнение с каноническим эталоном", { timeout: 120000 });
  await page.waitForSelector("button:has-text('Пересчитать diff')", { timeout: 120000 });
}

async function readBatchStatus(page) {
  return page.evaluate(async (id) => {
    const token = localStorage.getItem("access_token");
    const resp = await fetch(`http://localhost:8000/directory/personnel/import/batches/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!resp.ok) return { error: resp.status };
    const body = await resp.json();
    return { status: body.status, import_code: body.import_code };
  }, batchId);
}

async function main() {
  await mkdir(outDir, { recursive: true });
  const token = mintDevJwt(devUserId);
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  await login(page, token);

  const reviewUrl = `${baseUrl}/directory/personnel/import/${batchId}/review`;
  await page.goto(reviewUrl, { waitUntil: "networkidle", timeout: 120000 });
  await waitForReviewReady(page);
  await page.waitForTimeout(1500);

  const beforeStatus = await readBatchStatus(page);
  console.log("before", beforeStatus);
  await page.screenshot({ path: path.join(outDir, "01-review-before-recalc.png"), fullPage: true });

  const recalcButton = page.getByRole("button", { name: "Пересчитать diff" });
  await recalcButton.click();
  await page.waitForTimeout(2500);
  await page.waitForFunction(
    () => !document.body.textContent?.includes("Пересчёт…"),
    undefined,
    { timeout: 120000 },
  ).catch(() => {});
  await page.waitForTimeout(1500);

  const afterStatus = await readBatchStatus(page);
  console.log("after", afterStatus);
  await page.screenshot({ path: path.join(outDir, "02-review-after-recalc.png"), fullPage: true });

  const importListUrl = `${baseUrl}/directory/personnel/import`;
  await page.goto(importListUrl, { waitUntil: "domcontentloaded", timeout: 120000 });
  await page.waitForSelector("text=Импорт", { timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(outDir, "03-import-list-after-recalc.png"), fullPage: true });

  console.log(JSON.stringify({ beforeStatus, afterStatus, outDir }, null, 2));
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
