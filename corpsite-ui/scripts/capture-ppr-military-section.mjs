import { chromium } from "playwright";
import { execSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const outDir = path.resolve(__dirname, "../ppr-military-section-verify");
const baseUrl = process.env.CAPTURE_BASE_URL ?? "http://localhost:3000";
const devUserId = process.env.CAPTURE_DEV_USER_ID ?? "1";
const personId = process.env.PPR_REFERENCE_PERSON_ID ?? "100";

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
  await page.waitForTimeout(1500);

  const createBtn = page.getByTestId("military-create-btn");
  if (await createBtn.count()) {
    await createBtn.click();
    await page.waitForTimeout(500);
  }

  const composition = page.getByTestId("military-form-composition");
  if (await composition.count()) {
    await composition.click();
    await composition.fill("рядов");
    await page.getByTestId("military-form-composition-option-0").click();
    await page.waitForTimeout(300);
    const rank = page.getByTestId("military-form-rank");
    await rank.click();
    await page.waitForTimeout(300);
  }

  const militarySection = page.locator("#military");
  await militarySection.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);

  const outPath = path.join(outDir, `person-${personId}-military-section.png`);
  await militarySection.screenshot({ path: outPath });
  console.log(`Saved ${outPath}`);
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
