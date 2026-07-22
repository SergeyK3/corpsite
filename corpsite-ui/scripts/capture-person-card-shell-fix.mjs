import { chromium } from "playwright";
import { execSync } from "node:child_process";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const outDir = path.resolve(__dirname, "../person-card-shell-fix-verify");
const baseUrl = process.env.CAPTURE_BASE_URL ?? "http://localhost:3000";
const devUserId = process.env.CAPTURE_DEV_USER_ID ?? "1";

function resolveReferencePersonId() {
  if (process.env.PPR_REFERENCE_PERSON_ID) {
    return String(process.env.PPR_REFERENCE_PERSON_ID).trim();
  }
  const python = path.join(repoRoot, "venv", "Scripts", "python.exe");
  const script = path.join(repoRoot, "scripts", "ops", "replay_reference_person_fixture.py");
  const raw = execSync(`"${python}" "${script}" --resolve-only`, {
    cwd: repoRoot,
    encoding: "utf8",
  }).trim();
  const payload = JSON.parse(raw);
  if (!payload.found || payload.person_id == null) {
    throw new Error(
      "Reference person not found. Run scripts/ops/replay_reference_person_fixture.py --execute first " +
        "or set PPR_REFERENCE_PERSON_ID.",
    );
  }
  return String(payload.person_id);
}

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
  const personId = resolveReferencePersonId();
  const url = `${baseUrl}/directory/personnel/persons/${personId}/card`;
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const outPath = path.join(outDir, `person-${personId}-card.png`);
  await page.screenshot({ path: outPath, fullPage: false });
  console.log(`Reference person_id=${personId}`);
  console.log(`Saved ${outPath}`);
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
