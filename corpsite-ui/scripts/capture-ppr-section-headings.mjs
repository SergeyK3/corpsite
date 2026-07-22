import { chromium } from "playwright";
import { execSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const outDir = path.resolve(__dirname, "../ppr-section-headings-verify");
const baseUrl = process.env.CAPTURE_BASE_URL ?? "http://localhost:3000";
const devUserId = process.env.CAPTURE_DEV_USER_ID ?? "1";
const personId = process.env.PPR_VERIFY_PERSON_ID ?? "534";

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

async function main() {
  await mkdir(outDir, { recursive: true });
  const token = mintDevJwt(devUserId);
  const loginValue = devUserId === "1" ? "admin_legacy_1@corp.local" : `dev_user_${devUserId}@corp.local`;
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
  await login(page, token, loginValue);

  const url = `${baseUrl}/directory/personnel/persons/${personId}/card#military`;
  await page.goto(url, { waitUntil: "networkidle" });

  await page.locator("#military").scrollIntoViewIfNeeded();
  await page.waitForTimeout(400);

  const militaryHeading = page.locator("#military-heading");
  const employmentHeading = page.locator("#employment_biography-heading");
  const intendedHeading = page.locator("#intended_employment-heading");

  await employmentHeading.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);

  const militaryBox = await militaryHeading.boundingBox();
  const employmentBox = await employmentHeading.boundingBox();
  const intendedBox = await intendedHeading.boundingBox();

  if (!militaryBox || !employmentBox || !intendedBox) {
    throw new Error("Could not locate section headings for screenshot");
  }

  const top = Math.min(militaryBox.y, employmentBox.y, intendedBox.y) - 24;
  const bottom = Math.max(
    militaryBox.y + militaryBox.height,
    employmentBox.y + employmentBox.height,
    intendedBox.y + intendedBox.height,
  ) + 220;

  await page.screenshot({
    path: path.join(outDir, "ppr-section-headings-military-employment-intended.png"),
    clip: {
      x: 0,
      y: Math.max(0, top),
      width: 1440,
      height: Math.min(960, bottom - Math.max(0, top)),
    },
  });

  console.log(`Saved screenshot to ${outDir}`);
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
