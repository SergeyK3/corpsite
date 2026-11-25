#!/usr/bin/env node
"use strict";
// Acceptance browser only. Credentials and storage state remain in the test server's private directory.
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(process.env.TEST_STAND_PLAYWRIGHT_MODULE);

const origin = "https://test.mmc.004.kz";
const personId = Number(process.env.ACCEPT_PERSON_ID || 87);
const card = `${origin}/directory/personnel/persons/${personId}/card`;

async function main() {
  const session = path.join(process.env.TEST_STAND_SESSION_DIR, "hire_test_hr.json");
  const state = JSON.parse(fs.readFileSync(session, "utf8"));
  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  try {
    const context = await browser.newContext({ storageState: state });
    const page = await context.newPage();
    page.on("console", msg => { if (msg.type() === "error") console.log(`browser_console_error=${msg.text().slice(0, 200)}`); });
    page.on("response", async response => {
      if (response.status() >= 400 && new URL(response.url()).pathname.startsWith("/api/"))
        console.log(`api_error=${response.status()} ${new URL(response.url()).pathname} ${(await response.text()).slice(0, 1500)}`);
      if (["POST", "PUT", "PATCH"].includes(response.request().method()) && new URL(response.url()).pathname.includes("personnel-orders/"))
        console.log(`order_mutation=${response.request().method()} ${response.status()} ${new URL(response.url()).pathname}`);
    });
    await page.goto(card, { waitUntil: "domcontentloaded" });
    const create = page.getByTestId("ppr-applicant-create-hire-order");
    try { await create.waitFor({ state: "visible", timeout: 30000 }); }
    catch (error) {
      console.log(`card_url=${page.url()}`);
      console.log(`card_body=${(await page.locator("body").innerText()).slice(0, 3000)}`);
      throw error;
    }
    await create.click();
    const name = page.getByTestId("hire-name-accusative-ru");
    if (await name.count()) {
      await name.fill("Тестовую Майру");
      await page.getByTestId("confirm-hire-order-draft").click();
    }
    try { await page.waitForURL(/order_id=\d+/, { timeout: 30000 }); }
    catch (error) { console.log(`card_after_create=${(await page.locator("body").innerText()).slice(0, 1800)}`); throw error; }
    const first = new URL(page.url()).searchParams.get("order_id");
    if (!first) throw new Error("order_id_missing");
    console.log(`created_order_id=${first}`);
    await page.goto(card, { waitUntil: "domcontentloaded" });
    await create.waitFor({ state: "visible", timeout: 30000 });
    await create.click();
    await page.waitForURL(/order_id=\d+/, { timeout: 30000 });
    const reopened = new URL(page.url()).searchParams.get("order_id");
    if (reopened !== first) throw new Error(`different_draft_on_reopen:${reopened}`);
    console.log(`reopened_order_id=${reopened}`);
    await page.waitForTimeout(2500);
    console.log(`order_url=${new URL(page.url()).pathname}${new URL(page.url()).search}`);
    const controls = await page.locator("button").allTextContents();
    console.log(`buttons=${JSON.stringify(controls.map(v => v.trim()).filter(Boolean).slice(-45))}`);
    const fields = await page.locator("input").evaluateAll(els => els.map(el => ({
      label: el.getAttribute("aria-label"), testid: el.getAttribute("data-testid"),
      placeholder: el.getAttribute("placeholder"), value: el.value,
    })).filter(x => x.label || x.testid || x.placeholder).slice(-45));
    console.log(`inputs=${JSON.stringify(fields)}`);
    const language = page.getByTestId("personnel-order-language-switcher");
    await language.getByRole("button", { name: "Русский" }).click();
    const ruVisible = (await page.locator("body").innerText()).includes("В соответствии со статьей 34 Трудового кодекса Республики Казахстан");
    await language.getByRole("button", { name: "Қазақша" }).click();
    const kkVisible = (await page.locator("body").innerText()).includes("Қазақстан Республикасы Еңбек кодексінің 34 - бабына сәйкес");
    console.log(`ru_article34_visible=${ruVisible}`);
    console.log(`kk_article34_visible=${kkVisible}`);
    if (!ruVisible || !kkVisible) throw new Error("article34_preamble_missing");
    const rate = page.getByTestId("personnel-order-hire-rate-input");
    await rate.fill("0.5");
    await page.getByRole("button", { name: "Сохранить пункт", exact: true }).click();
    await page.waitForTimeout(15000);
    console.log(`rate_after_save=${await rate.inputValue()}`);
    console.log(`alerts_after_save=${JSON.stringify(await page.getByRole("alert").allTextContents())}`);
    console.log(`body_after_save_tail=${(await page.locator("body").innerText()).slice(-2500)}`);
    await page.reload({ waitUntil: "domcontentloaded" });
    await rate.waitFor({ state: "visible", timeout: 30000 });
    const savedRate = await rate.inputValue();
    console.log(`rate_after_reopen=${savedRate}`);
    if (savedRate !== "0.5" && savedRate !== "0.50") throw new Error("rate_not_persisted");
    await context.close();
  } finally { await browser.close(); }
}
main().catch(error => { console.error(`accept_browser_failed=${error.message}`); process.exitCode = 1; });
