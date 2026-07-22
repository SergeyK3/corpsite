/**
 * Composite education parser verification screenshots — Abdikarimov A.M., batch 809.
 */
import { chromium } from "playwright";
import { execSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const outDir = path.resolve(__dirname, "../education-composite-verify");
const baseUrl = process.env.CAPTURE_BASE_URL ?? "http://localhost:3000";
const devUserId = process.env.CAPTURE_DEV_USER_ID ?? "1";
const batchId = process.env.CAPTURE_BATCH_ID ?? "809";
const employeeName = "Абдикаримов Ануар Маратович";
const employeeIin = "861019300094";
const collegeTitle = "Семипалатинский бизнес-колледж";
const academyTitle = "Семипалатинская государственная медицинская академия";

function mintDevJwt(userId) {
  const python = path.join(repoRoot, "venv", "Scripts", "python.exe");
  const cmd = `from app.auth import create_access_token; print(create_access_token(${Number(userId)}))`;
  return execSync(`"${python}" -c "${cmd}"`, { cwd: repoRoot, encoding: "utf8" }).trim();
}

async function login(page, token, loginValue) {
  await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
  await page.evaluate(
    ({ tokenValue, login }) => {
      localStorage.setItem("access_token", tokenValue);
      localStorage.setItem("login", login);
    },
    { tokenValue: token, login: loginValue },
  );
}

async function openFilteredEducationReview(page) {
  await page.goto(`${baseUrl}/directory/personnel/import/review?batch=${batchId}`, {
    waitUntil: "networkidle",
    timeout: 120000,
  });
  await page.locator('select:has(option[value="education"])').selectOption("education");
  await page.getByPlaceholder("Поиск по ФИО сотрудника").fill(employeeName);
  await page.getByPlaceholder("Поиск по ИИН").fill(employeeIin);
  await page.waitForTimeout(1800);
  await page.waitForSelector(`text=${collegeTitle}`, { timeout: 120000 });
  await page.waitForSelector(`text=${academyTitle}`, { timeout: 120000 });
}

async function main() {
  await mkdir(outDir, { recursive: true });
  const token = mintDevJwt(devUserId);
  const loginValue = devUserId === "1" ? "admin_legacy_1@corp.local" : `dev_user_${devUserId}@corp.local`;

  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
  const page = await context.newPage();
  await login(page, token, loginValue);

  await openFilteredEducationReview(page);
  await page.screenshot({
    path: path.join(outDir, "01-review-normalized-list-before-apply.png"),
    fullPage: true,
  });

  await page.locator("table tbody tr").filter({ hasText: collegeTitle }).first().click();
  const drawer = page.locator(".overflow-y-auto").last();
  await drawer.waitFor({ timeout: 120000 });
  await drawer.evaluate((node) => {
    node.scrollTop = node.scrollHeight;
  });
  await page.waitForTimeout(800);
  await page.screenshot({
    path: path.join(outDir, "02-review-diff-before-apply.png"),
    fullPage: false,
  });

  const batchReviewUrl = `${baseUrl}/directory/personnel/import/${batchId}/review?q_name=${encodeURIComponent(employeeName)}`;
  await page.goto(batchReviewUrl, { waitUntil: "networkidle", timeout: 120000 });
  await page.waitForSelector('[data-testid="import-training-date-quality-panel"]', { timeout: 120000 });
  await page
    .locator('[data-testid="import-training-date-quality-panel"] tr')
    .filter({ hasText: employeeName })
    .first()
    .scrollIntoViewIfNeeded();
  await page.waitForTimeout(800);
  await page.screenshot({
    path: path.join(outDir, "04-quality-remarks-before-apply.png"),
    fullPage: false,
  });

  await openFilteredEducationReview(page);
  await page.screenshot({
    path: path.join(outDir, "03-review-after-reimport-no-conflicts.png"),
    fullPage: true,
  });

  await browser.close();
  console.log(JSON.stringify({ batchId: Number(batchId), outDir, employeeIin }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
