#!/usr/bin/env node
"use strict";

// Reusable browser entry for the protected acceptance stand. Credentials and
// storage state stay in the server's private directory, never in this source.
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.TEST_STAND_PLAYWRIGHT_MODULE ||
  path.resolve(__dirname, "../../corpsite-ui/node_modules/playwright"));

process.umask(0o077);

function option(name, fallback) {
  const position = process.argv.indexOf(name);
  return position < 0 ? fallback : process.argv[position + 1];
}

function privateFile(file) {
  const info = fs.lstatSync(file);
  if (!info.isFile() || info.isSymbolicLink() || (info.mode & 0o077) !== 0 ||
      (process.getuid && info.uid !== process.getuid())) {
    throw new Error("private_file_permissions");
  }
  return fs.readFileSync(file, "utf8");
}

function privateDirectory(directory) {
  fs.mkdirSync(directory, { recursive: true, mode: 0o700 });
  const info = fs.lstatSync(directory);
  if (!info.isDirectory() || info.isSymbolicLink() || (info.mode & 0o077) !== 0 ||
      (process.getuid && info.uid !== process.getuid())) {
    throw new Error("private_directory_permissions");
  }
}

function accountPassword(file, accountKey) {
  const row = privateFile(file).split(/\r?\n/).find(line => line.startsWith(`${accountKey}=`));
  if (!row) throw new Error("account_missing");
  return row.slice(accountKey.length + 1).trim();
}

async function saveState(context, sessionFile) {
  const temporary = `${sessionFile}.${process.pid}.tmp`;
  try {
    await context.storageState({ path: temporary });
    fs.chmodSync(temporary, 0o600);
    fs.renameSync(temporary, sessionFile);
  } finally {
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
  }
}

async function main() {
  const origin = new URL(process.env.TEST_STAND_URL || "");
  if (origin.protocol !== "https:" || origin.hostname !== "test.mmc.004.kz" ||
      origin.pathname !== "/" || origin.search || origin.hash) {
    throw new Error("unexpected_stand_origin");
  }
  const accountKey = option("--account-key", process.env.TEST_STAND_ACCOUNT_KEY);
  const route = option("--path", "/directory/personnel/orders");
  const readySelector = option("--ready-selector", "[data-testid='electronic-hire-open-button']");
  if (!accountKey || !/^[A-Za-z0-9_-]+$/.test(accountKey) || !route?.startsWith("/") ||
      route.startsWith("//") || route.includes("\\") || !readySelector) throw new Error("invalid_check_arguments");

  const sessionDirectory = process.env.TEST_STAND_SESSION_DIR;
  const gateFile = process.env.TEST_STAND_GATE_PASSWORD_FILE;
  const accountsFile = process.env.TEST_STAND_ACCOUNTS_FILE;
  if (!sessionDirectory || !gateFile || !accountsFile) throw new Error("missing_private_environment");
  privateDirectory(sessionDirectory);
  const sessionFile = path.join(sessionDirectory, `${accountKey}.json`);
  const hasState = fs.existsSync(sessionFile);
  if (hasState) privateFile(sessionFile);

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  let context;
  let step = "open";
  try {
    try {
      context = await browser.newContext(hasState ? { storageState: sessionFile } : {});
    } catch {
      context = await browser.newContext();
    }
    const page = await context.newPage();
    const apiRequests = [];
    page.on("request", request => {
      const pathname = new URL(request.url()).pathname;
      if (pathname.startsWith("/api/")) apiRequests.push(pathname);
    });
    let gateLogin = false;
    let accountLogin = false;
    const targetUrl = new URL(route, origin);
    if (targetUrl.origin !== origin.origin) throw new Error("unexpected_target_origin");
    const target = targetUrl.toString();

    for (let attempt = 0; attempt < 4; attempt++) {
      step = "navigate";
      await page.goto(target, { waitUntil: "domcontentloaded" });
      if (new URL(page.url()).origin !== origin.origin) throw new Error("unexpected_redirect_origin");
      if (new URL(page.url()).pathname === "/_unlock") {
        step = "gateway";
        await page.locator("input[name=password]").fill(privateFile(gateFile).trim());
        await page.getByRole("button", { name: "Enter" }).click();
        await page.waitForURL(url => url.pathname !== "/_unlock", { timeout: 20000 });
        gateLogin = true;
        continue;
      }

      step = "session_check";
      const token = await page.evaluate(() => localStorage.getItem("access_token"));
      let authorized = false;
      if (token) {
        const response = await context.request.get(new URL("/api/auth/me", origin).toString(), {
          headers: { Authorization: `Bearer ${token}` }, maxRedirects: 0,
        });
        authorized = response.status() === 200 &&
          (response.headers()["content-type"] || "").includes("application/json");
        if (!authorized && response.status() !== 401) throw new Error("session_check_failed");
      }
      if (!authorized) {
        step = "account_login";
        await page.goto(new URL("/login", origin).toString());
        await page.locator("input[name=login]").fill(accountKey);
        await page.locator("input[name=password]").fill(accountPassword(accountsFile, accountKey));
        await page.getByRole("button", { name: /Войти/ }).click();
        await page.waitForURL(url => url.pathname !== "/login", { timeout: 20000 });
        accountLogin = true;
        continue;
      }

      step = "page_ready";
      await page.locator(readySelector).waitFor({ state: "visible", timeout: 30000 });
      await page.waitForTimeout(5000);
      const settledAt = apiRequests.length;
      await page.waitForTimeout(4000);
      const afterSettled = apiRequests.slice(settledAt);
      if (afterSettled.length) throw new Error("repeated_api_requests");
      await saveState(context, sessionFile);
      console.log(`stand=ready gateway=${gateLogin ? "renewed" : "reused"} account=${accountLogin ? "renewed" : "reused"} idle_api_requests=0`);
      return;
    }
    throw new Error("authentication_retry_limit");
  } catch (error) {
    console.error(`check_failed_at=${step} type=${error instanceof Error ? error.message : "unknown"}`);
    process.exitCode = 1;
  } finally {
    if (context) await context.close();
    await browser.close();
  }
}

main().catch(error => {
  console.error(`check_failed_at=configuration type=${error instanceof Error ? error.message : "unknown"}`);
  process.exitCode = 1;
});
