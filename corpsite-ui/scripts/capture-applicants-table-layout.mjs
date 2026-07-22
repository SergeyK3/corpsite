/**
 * Capture personnel applications table layout at common viewport widths.
 * Requires local frontend (:3000) and Python venv for JWT minting.
 */
import { chromium } from "playwright";
import { execSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const baseUrl = process.env.CAPTURE_BASE_URL ?? "http://localhost:3000";
const devUserId = process.env.CAPTURE_DEV_USER_ID ?? "34";
const outputDir =
  process.env.CAPTURE_OUTPUT_DIR ??
  path.join(repoRoot, "docs-work", "screenshots", "personnel-applications-table");

const VIEWPORTS = [
  { width: 1366, height: 900, name: "1366px" },
  { width: 1600, height: 900, name: "1600px" },
  { width: 1920, height: 900, name: "1920px" },
];

function mintDevJwt(userId) {
  const python = path.join(repoRoot, "venv", "Scripts", "python.exe");
  const cmd = `from app.auth import create_access_token; print(create_access_token(${Number(userId)}))`;
  return execSync(`"${python}" -c "${cmd}"`, { cwd: repoRoot, encoding: "utf8" }).trim();
}

async function main() {
  await mkdir(outputDir, { recursive: true });
  const token = mintDevJwt(devUserId);
  const browser = await chromium.launch();

  for (const viewport of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
    });
    const page = await context.newPage();

    await page.goto(`${baseUrl}/login`, { waitUntil: "domcontentloaded" });
    await page.evaluate(
      ({ tokenValue, loginValue }) => {
        localStorage.setItem("access_token", tokenValue);
        localStorage.setItem("login", loginValue);
      },
      { tokenValue: token, loginValue: `dev_user_${devUserId}@corp.local` },
    );

    await page.goto(`${baseUrl}/directory/personnel/applicants`, {
      waitUntil: "networkidle",
      timeout: 120000,
    });
    await page.waitForSelector('[data-testid="personnel-applicants-workplace-page"]', {
      timeout: 120000,
    });
    await page.waitForSelector(
      '[data-testid="personnel-applications-table"], [data-testid="personnel-applications-empty"], [data-testid="personnel-applications-table-skeleton"]',
      { timeout: 120000 },
    );

    const screenshotPath = path.join(outputDir, `applicants-page-${viewport.name}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: true });

    const table = page.locator('[data-testid="personnel-applications-table"]');
    if (await table.count()) {
      await table.screenshot({
        path: path.join(outputDir, `applicants-table-${viewport.name}.png`),
      });
    }

    await context.close();
    console.log(`Saved ${viewport.name}`);
  }

  await browser.close();
  console.log(`Screenshots written to ${outputDir}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
