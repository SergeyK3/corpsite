#!/usr/bin/env node
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.TEST_STAND_PLAYWRIGHT_MODULE);
const orderId = Number(process.env.ACCEPT_ORDER_ID || 68);

async function main() {
  const state = JSON.parse(fs.readFileSync(path.join(process.env.TEST_STAND_SESSION_DIR, "hire_test_hr.json"), "utf8"));
  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  try {
    const context = await browser.newContext({ storageState: state });
    const page = await context.newPage();
    page.on("response", async response => {
      if (response.request().method() === "POST" && new URL(response.url()).pathname.endsWith(`/personnel-orders/${orderId}/apply`)) {
        console.log(`apply_http_status=${response.status()}`);
        if (!response.ok()) console.log(`apply_error=${(await response.text()).slice(0, 1800)}`);
      }
    });
    await page.goto(`https://test.mmc.004.kz/directory/personnel/orders?order_id=${orderId}&tab=data`, { waitUntil: "domcontentloaded" });
    const apply = page.getByTestId("personnel-order-apply-button");
    await apply.waitFor({ state: "visible", timeout: 30000 });
    await apply.click();
    await page.getByTestId("personnel-order-apply-confirm").click();
    await page.waitForTimeout(10000);
    console.log(`lifecycle=${(await page.getByTestId("personnel-order-lifecycle-actions").innerText()).slice(0, 1800)}`);
    await context.close();
  } finally { await browser.close(); }
}
main().catch(error => { console.error(`apply_browser_failed=${error.message}`); process.exitCode = 1; });
