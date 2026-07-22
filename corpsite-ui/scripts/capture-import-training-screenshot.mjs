/**
 * Capture import training page screenshot (batch #39) for verification report.
 * Uses a dev JWT for user 34 (NEXT_PUBLIC_DEV_X_USER_ID) and real API data.
 * Run: node scripts/capture-import-training-screenshot.mjs
 */
import { chromium } from "playwright";
import { execSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const outDir = path.resolve(__dirname, "../import-training-verify");
const baseUrl = process.env.CAPTURE_BASE_URL ?? "http://localhost:3000";
const batchId = process.env.CAPTURE_BATCH_ID ?? "39";
const devUserId = process.env.CAPTURE_DEV_USER_ID ?? "34";

function mintDevJwt(userId) {
  const python = path.join(repoRoot, "venv", "Scripts", "python.exe");
  const cmd = `from app.auth import create_access_token; print(create_access_token(${Number(userId)}))`;
  return execSync(`"${python}" -c "${cmd}"`, { cwd: repoRoot, encoding: "utf8" }).trim();
}

async function main() {
  await mkdir(outDir, { recursive: true });
  const token = mintDevJwt(devUserId);

  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  const page = await context.newPage();

  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate(
    ({ tokenValue, loginValue }) => {
      localStorage.setItem("access_token", tokenValue);
      localStorage.setItem("login", loginValue);
    },
    { tokenValue: token, loginValue: `dev_user_${devUserId}@corp.local` }
  );

  const target = `${baseUrl}/directory/personnel/import/${batchId}/training`;
  await page.goto(target, { waitUntil: "domcontentloaded", timeout: 120000 });
  await page.waitForSelector('[data-testid="import-training-summary"]', { timeout: 120000 });
  await page.waitForSelector('[data-testid="import-training-table"]', { timeout: 90000 });
  await page.waitForSelector("text=Жетысайский высший медицинский колледж", { timeout: 90000 }).catch(() => {});
  await page.waitForTimeout(1200);

  const outPath = path.join(outDir, "training-batch-39.png");
  await page.screenshot({ path: outPath, fullPage: false });
  console.log(`Saved ${outPath}`);

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
