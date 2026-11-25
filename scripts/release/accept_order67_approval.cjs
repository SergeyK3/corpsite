#!/usr/bin/env node
"use strict";
// Uses private test-stand sessions; does not read or print account passwords.
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.TEST_STAND_PLAYWRIGHT_MODULE);
const origin = "https://test.mmc.004.kz";
const applicationId = Number(process.env.ACCEPT_APPLICATION_ID || 79);
const orderId = Number(process.env.ACCEPT_ORDER_ID || 68);
const base = `/api/directory/electronic-hire/applications/${applicationId}`;

async function withAccount(browser, account, run) {
  const state = JSON.parse(fs.readFileSync(path.join(process.env.TEST_STAND_SESSION_DIR, `${account}.json`), "utf8"));
  const context = await browser.newContext({ storageState: state });
  try {
    const page = await context.newPage();
    await page.goto(`${origin}/directory/personnel/orders?order_id=${orderId}`, { waitUntil: "domcontentloaded" });
    const token = await page.evaluate(() => localStorage.getItem("access_token"));
    if (!token) throw new Error(`${account}:missing_token`);
    async function api(method, route, body) {
      const response = await context.request.fetch(`${origin}${route}`, {
        method, headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        data: body == null ? undefined : JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok()) throw new Error(`${account}:${method}:${route}:${response.status()}:${JSON.stringify(payload).slice(0, 1000)}`);
      return payload;
    }
    const me = await api("GET", "/api/auth/me");
    console.log(`${account}_user_id=${me.user_id}`);
    await run(api, me);
  } finally { await context.close(); }
}

async function main() {
  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  try {
    await withAccount(browser, "hire_test_hr", async api => {
      const before = await api("GET", base);
      console.log(`approval_mode=${before.approval_mode} before_rate=${before.intended_employment_rate}`);
      const updated = await api("PATCH", `${base}/conditions`, {
        org_unit_id: 25, position_id: 17, employment_rate: "0.5", planned_start_date: "2026-12-02",
      });
      console.log(`updated_rate=${updated.intended_employment_rate}`);
      await api("POST", `${base}/candidate-checked`, {});
      console.log("identity_reconfirmed=true");
    });
    await withAccount(browser, "hire_test_head", async (api, me) => {
      if (me.user_id !== 6) throw new Error(`Unexpected head user ${me.user_id}`);
      const visa = await api("POST", `${base}/visa`, { decision: "approved", explanation: null });
      console.log(`visa_decision=${visa.decision} visa_id=${visa.visa_id}`);
    });
  } finally { await browser.close(); }
}
main().catch(error => { console.error(`approval_failed=${error.message}`); process.exitCode = 1; });
