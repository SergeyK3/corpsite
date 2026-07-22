import { chromium } from "playwright";
import { execSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const outDir = path.resolve(__dirname, "../ppr-military-ux-verify");
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

  const editBtn = page.getByTestId(/^military-edit-btn-/);
  await editBtn.waitFor({ state: "visible", timeout: 15000 });
  await editBtn.click();
  await page.waitForSelector('[data-testid="military-supersede-form"]');

  const form = page.getByTestId("military-supersede-form");
  const composition = form.getByTestId("military-form-composition");
  const rank = form.getByTestId("military-form-rank");

  await composition.click();
  await form.getByText("Сержантский состав", { exact: true }).click();
  await page.waitForTimeout(300);

  await rank.click();
  await form.getByTestId("military-form-rank-list").waitFor({ state: "visible" });
  await form.getByText("Сержант 3 класса", { exact: true }).click();
  await page.waitForTimeout(300);

  await form.getByTestId("military-supersede-submit").click();
  await page.waitForTimeout(1500);

  await page.reload({ waitUntil: "networkidle" });
  await page.locator("#military").scrollIntoViewIfNeeded();

  const compositionValue = await page.getByTestId("military-form-composition").inputValue().catch(() => "");
  const activeCard = page.locator('[data-testid^="military-record-"]').first();
  const cardText = await activeCard.innerText();

  await page.screenshot({
    path: path.join(outDir, `person-${personId}-military-after-save-reload.png`),
    fullPage: false,
  });

  console.log(
    JSON.stringify(
      {
        personId,
        cardContainsSergeantComposition: cardText.includes("Сержантский состав"),
        cardContainsSergeantRank: cardText.includes("Сержант 3 класса"),
        cardContainsSeniorLieutenant: cardText.includes("Старший лейтенант"),
        cardTextPreview: cardText.split("\n").slice(0, 8),
      },
      null,
      2,
    ),
  );

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
