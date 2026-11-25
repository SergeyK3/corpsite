#!/usr/bin/env node
"use strict";
// Complete the fictional test order in the same browser UI used for draft acceptance.
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.TEST_STAND_PLAYWRIGHT_MODULE);
const origin = "https://test.mmc.004.kz";
const orderId = Number(process.env.ACCEPT_ORDER_ID || 68);
const orderNumber = `EHA-TEST-${orderId}`;

async function main() {
  const state = JSON.parse(fs.readFileSync(path.join(process.env.TEST_STAND_SESSION_DIR, "hire_test_hr.json"), "utf8"));
  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  try {
    const context = await browser.newContext({ storageState: state });
    const page = await context.newPage();
    page.on("response", async response => {
      const route = new URL(response.url()).pathname;
      if (response.request().method() !== "GET" && route.includes(`personnel-orders/${orderId}`)) {
        console.log(`mutation=${response.request().method()} ${response.status()} ${route}`);
        if (!response.ok()) console.log(`mutation_error=${(await response.text()).slice(0, 1500)}`);
      }
    });
    await page.goto(`${origin}/directory/personnel/orders?order_id=${orderId}&tab=data`, { waitUntil: "domcontentloaded" });
    await page.getByTestId("personnel-order-detail-drawer").waitFor({ state: "visible", timeout: 30000 });
    const rate = page.getByTestId("personnel-order-hire-rate-input");
    if (await rate.count()) console.log(`pre_register_rate=${await rate.inputValue()}`);
    const number = page.getByRole("textbox", { name: "№ приказа (из журнала)" });
    const numberDirty = (await number.inputValue()) !== orderNumber;
    if (numberDirty) await number.fill(orderNumber);
    const signatory = page.getByTestId("personnel-order-header-signatory-name");
    const signatoryDirty = !(await signatory.inputValue()).trim();
    if (signatoryDirty) await signatory.fill("Вымышленный директор");
    if (numberDirty || signatoryDirty) {
      await page.getByTestId("personnel-order-header-save-signatory").click();
      await page.waitForTimeout(3000);
      await page.reload({ waitUntil: "domcontentloaded" });
    }
    const lifecycle = page.getByTestId("personnel-order-lifecycle-actions");
    console.log(`after_header=${(await lifecycle.innerText()).slice(0, 1400)}`);
    const ready = lifecycle.getByRole("button", { name: "К подписи" });
    if (!(await ready.isEnabled())) throw new Error("ready_button_disabled");
    await ready.click();
    await page.waitForTimeout(3000);
    console.log(`after_ready=${(await lifecycle.innerText()).slice(0, 1800)}`);
    const register = lifecycle.getByRole("button", { name: "Зарегистрировать приказ" });
    await register.waitFor({ state: "visible", timeout: 10000 });
    await register.click();
    await lifecycle.getByRole("button", { name: "Подтвердить", exact: true }).click();
    await page.waitForTimeout(3000);
    console.log(`after_register=${(await lifecycle.innerText()).slice(0, 1800)}`);
    const apply = page.getByTestId("personnel-order-apply-button");
    await apply.waitFor({ state: "visible", timeout: 10000 });
    await apply.click();
    await page.getByTestId("personnel-order-apply-confirm").click();
    await page.waitForTimeout(5000);
    console.log(`after_apply=${(await lifecycle.innerText()).slice(0, 2000)}`);
    await context.close();
  } finally { await browser.close(); }
}
main().catch(error => { console.error(`finalize_failed=${error.message}`); process.exitCode = 1; });
