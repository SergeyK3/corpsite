/**
 * Browser verification for applicant intake link persistence.
 * Requires local backend (:8000), frontend (:3000), and .demo-intake-verify.json
 * produced by scripts/verify_applicant_intake_demo.py --skip-revoke
 */
import { chromium } from "playwright";
import { execSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const baseUrl = process.env.CAPTURE_BASE_URL ?? "http://localhost:3000";
const apiBase = process.env.CAPTURE_API_BASE_URL ?? "http://127.0.0.1:8000";
const devUserId = process.env.CAPTURE_DEV_USER_ID ?? "34";

function mintDevJwt(userId) {
  const python = path.join(repoRoot, "venv", "Scripts", "python.exe");
  const cmd = `from app.auth import create_access_token; print(create_access_token(${Number(userId)}))`;
  return execSync(`"${python}" -c "${cmd}"`, { cwd: repoRoot, encoding: "utf8" }).trim();
}

function mintAuthHeaders(userId) {
  const python = path.join(repoRoot, "venv", "Scripts", "python.exe");
  const cmd =
    "from tests.conftest import auth_headers; import json; print(json.dumps(auth_headers(" +
    Number(userId) +
    ")))";
  return JSON.parse(execSync(`"${python}" -c "${cmd}"`, { cwd: repoRoot, encoding: "utf8" }));
}

async function main() {
  const artifactPath = path.join(repoRoot, ".demo-intake-verify.json");
  const artifact = JSON.parse(await readFile(artifactPath, "utf8"));
  const applicationId = Number(artifact.application_id);
  const intakePath = String(artifact.intake_url_path || "").trim();
  if (!applicationId || !intakePath.startsWith("/intake/")) {
    throw new Error(`Invalid demo artifact: ${artifactPath}`);
  }

  const token = mintDevJwt(devUserId);
  const authHeaders = mintAuthHeaders(devUserId);
  const checks = [];

  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
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
    waitUntil: "domcontentloaded",
    timeout: 120000,
  });
  await page.waitForSelector("text=Адрес ЛК", { timeout: 120000 });
  checks.push(["column header visible", true]);

  const copyBtn = page.locator(`[data-testid="applicant-intake-link-copy-${applicationId}"]`);
  const openBtn = page.locator(`[data-testid="applicant-intake-link-open-${applicationId}"]`);
  await copyBtn.waitFor({ timeout: 120000 });
  await openBtn.waitFor({ timeout: 120000 });
  checks.push(["copy/open controls visible", true]);

  await page.evaluate(() => sessionStorage.clear());
  await page.reload({ waitUntil: "domcontentloaded" });
  await copyBtn.waitFor({ timeout: 120000 });
  checks.push(["link restored after sessionStorage clear", true]);

  const [intakePage] = await Promise.all([
    context.waitForEvent("page"),
    openBtn.click(),
  ]);
  await intakePage.waitForLoadState("domcontentloaded");
  await intakePage.waitForSelector("text=Личная карточка", { timeout: 120000 }).catch(() => null);
  checks.push(["intake opens from table", intakePage.url().includes("/intake/")]);

  await page.goto(`${baseUrl}${intakePath}`, { waitUntil: "networkidle", timeout: 120000 });
  const submittedMarker = page.locator("text=Анкета отправлена");
  await submittedMarker.first().waitFor({ timeout: 120000 });
  checks.push(["submitted intake read-only view", true]);

  const revokeRes = await page.request.post(
    `${apiBase}/directory/personnel-applications/${applicationId}/intake-link/revoke`,
    { headers: authHeaders },
  );
  checks.push(["revoke API", revokeRes.ok()]);

  await page.goto(`${baseUrl}/directory/personnel/applicants`, {
    waitUntil: "domcontentloaded",
    timeout: 120000,
  });
  const statusCell = page.locator(`[data-testid="applicant-intake-link-status-${applicationId}"]`);
  await statusCell.waitFor({ timeout: 120000 });
  const statusText = ((await statusCell.textContent()) || "").trim();
  checks.push(["revoked status in table", /отозван/i.test(statusText)]);

  await browser.close();

  const failed = checks.filter(([, ok]) => !ok);
  for (const [name, ok] of checks) {
    console.log(`[${ok ? "OK" : "FAIL"}] ${name}`);
  }
  if (failed.length) {
    throw new Error(`${failed.length} browser check(s) failed`);
  }
  console.log(`Browser verification passed (${checks.length}/${checks.length})`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
