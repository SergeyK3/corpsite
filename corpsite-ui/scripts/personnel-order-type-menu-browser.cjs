// Local browser acceptance against the real application and PostgreSQL.
const { chromium, request } = require('playwright');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

const root = path.resolve(__dirname, '../..');
const folder = path.join(root, 'runtime/hr-order-type-menu');
fs.mkdirSync(folder, { recursive: true });
const token = execFileSync('python', ['-X', 'utf8', '-c', [
  'from app.db.engine import engine',
  'from app.auth import create_access_token',
  'from sqlalchemy import text',
  'assert engine.url.host == "127.0.0.1" and engine.url.database == "corpsite"',
  'with engine.connect() as c:',
  ' row=c.execute(text("SELECT u.user_id,coalesce(u.token_version,1) AS token_version FROM users u JOIN roles r ON r.role_id=u.role_id WHERE upper(r.code)=\'HR_HEAD\' AND u.is_active=true AND u.locked_at IS NULL ORDER BY u.user_id LIMIT 1")).mappings().one()',
  'print(create_access_token(row["user_id"], token_version=row["token_version"]))',
].join('\n')], { cwd: root, encoding: 'utf8' }).trim();

const expectedCodes = ['HIRE', 'TRANSFER', 'TERMINATION', 'CONCURRENT_DUTY_START', 'CONCURRENT_DUTY_END', 'RETURN_FROM_CHILDCARE_LEAVE', 'LEAVE.ANNUAL.GRANT', 'LEAVE.UNPAID.GRANT', 'LEAVE.CHILDCARE.GRANT', 'SUPPLEMENTARY_PAY'];
const russianGroups = ['Трудовой отпуск', 'Беременность, роды и уход за ребёнком', 'Отпуск без содержания', 'Другие отпуска', 'Приём, увольнение, назначение, перевод', 'Совмещение и доплаты', 'Учётные данные и изменения приказов'];
const canonicalSource = fs.readFileSync(path.join(root, 'corpsite-ui/app/directory/personnel/_lib/personnelOrderCanonicalTitles.ts'), 'utf8');
const canonical = Object.fromEntries([...canonicalSource.matchAll(/^\s*(?:"([^"]+)"|([A-Z_]+)):\s*\{\s*ru:\s*"([^"]+)",\s*kk:\s*"([^"]+)"/gm)].map(match => [match[1] || match[2], { ru: match[3], kk: match[4] }]));

async function waitTitle(page, expected) {
  await page.waitForFunction(value => document.querySelector('textarea[aria-label="Название приказа"]')?.value === value, expected);
}

async function openForm(page, documentLanguage) {
  await page.goto('http://127.0.0.1:3000/directory/personnel/orders');
  await page.waitForFunction(() => document.querySelector('details select')?.disabled === false);
  await page.getByTestId('personnel-order-create-button').click();
  await page.getByLabel('Язык', { exact: true }).selectOption(documentLanguage);
}

async function selected(page, api, code, locale) {
  const trigger = page.getByRole('button', { name: 'Тип кадрового приказа', exact: true });
  assert.equal(await trigger.getAttribute('value'), code);
  assert.equal(await page.getByLabel('Язык', { exact: true }).inputValue(), locale);
  assert.equal(await page.getByTestId('personnel-order-type-menu').count(), 0);
  const published = await api.get(`/directory/personnel-orders/templates/${encodeURIComponent(code)}/published-title`);
  assert.ok([200, 404].includes(published.status()), `${code}: ${await published.text()}`);
  const titles = published.status() === 200 ? await published.json() : null;
  const title = titles ? titles[`title_${locale}`] : canonical[code][locale];
  await waitTitle(page, title);
  const period = ['LEAVE.UNPAID.GRANT', 'LEAVE.CHILDCARE.GRANT'].includes(code);
  assert.equal(await page.getByLabel('Дата начала', { exact: true }).count(), period ? 1 : 0);
  assert.equal(await page.getByLabel('Дата действия', { exact: true }).count(), period ? 0 : 1);
  if (code === 'LEAVE.CHILDCARE.GRANT') assert.equal(await page.getByText('Дата выдачи свидетельства о рождении', { exact: true }).count(), 1);
  return { code, documentLanguage: locale, title, dateFieldsCorrect: true, publishedTemplate: published.status() === 200 };
}

(async () => {
  const api = await request.newContext({ baseURL: 'http://127.0.0.1:8000', extraHTTPHeaders: { Authorization: `Bearer ${token}` } });
  const initial = await api.get('/personnel/settings');
  assert.equal(initial.status(), 200);
  const originalLanguage = (await initial.json()).language;
  const browser = await chromium.launch({ headless: true });
  const report = { languages: [], selected: [], browserErrors: [], writes: [], edge: null, touch: null };
  try {
    for (const language of process.env.HR_ORDER_MENU_ONLY_TOUCH ? [] : ['kk', 'ru']) {
      assert.equal((await api.put('/personnel/settings', { data: { language } })).status(), 200);
      const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
      await context.addInitScript(value => localStorage.setItem('access_token', value), token);
      const page = await context.newPage();
      page.setDefaultTimeout(20000);
      page.on('pageerror', error => report.browserErrors.push(error.message));
      page.on('request', req => { if (req.method() !== 'GET' && req.method() !== 'OPTIONS') report.writes.push({ method: req.method(), path: new URL(req.url()).pathname }); });
      const locale = language === 'kk' ? 'ru' : 'kk';
      await openForm(page, locale);
      const trigger = page.getByRole('button', { name: 'Тип кадрового приказа', exact: true });
      await trigger.click();
      const popup = page.getByTestId('personnel-order-type-menu');
      const groupButtons = popup.locator('button[data-group]');
      assert.equal(await groupButtons.count(), 7);
      if (language === 'ru') assert.deepEqual(await groupButtons.locator('span:first-child').allTextContents(), russianGroups);
      else assert.equal(await groupButtons.first().innerText(), 'Еңбек демалысы\n›');
      const allCodes = [];
      for (let index = 0; index < 7; index++) {
        await groupButtons.nth(index).click();
        const codes = await popup.locator('button[data-type-code]').evaluateAll(nodes => nodes.map(node => node.dataset.typeCode));
        allCodes.push(...codes);
      }
      assert.deepEqual(allCodes.sort(), [...expectedCodes].sort());

      // Cross neighbouring group rows diagonally to an item in the side panel.
      const employment = popup.locator('[data-group="employment"]');
      await employment.hover();
      const hire = popup.locator('[data-type-code="HIRE"]');
      await hire.waitFor();
      const from = await employment.boundingBox();
      const to = await hire.boundingBox();
      await page.mouse.move(from.x + from.width - 18, from.y + from.height / 2);
      await page.mouse.move(to.x + 24, to.y + to.height / 2, { steps: 20 });
      assert.equal(await hire.isVisible(), true);
      assert.equal(await employment.getAttribute('aria-expanded'), 'true');
      await page.screenshot({ path: path.join(folder, `hover-${language}.png`) });
      await hire.click();
      report.selected.push(await selected(page, api, 'HIRE', locale));

      for (const [code, query] of language === 'kk'
        ? [['LEAVE.UNPAID.GRANT', 'без'], ['LEAVE.CHILDCARE.GRANT', 'неоплачиваемом']]
        : [['TRANSFER', 'Ауыстыру туралы'], ['LEAVE.ANNUAL.GRANT', 'Еңбек демалысы'], ['SUPPLEMENTARY_PAY', 'Қосымша ақы']]) {
        await trigger.click();
        await popup.getByRole('searchbox').fill(query);
        await popup.locator(`[data-type-code="${code}"]`).click();
        report.selected.push(await selected(page, api, code, locale));
      }

      // Escape closes only the menu; clicking a form field closes it as well.
      await trigger.click();
      await page.keyboard.press('Escape');
      assert.equal(await popup.count(), 0);
      assert.equal(await page.getByRole('dialog').count(), 1);
      await trigger.click();
      await page.getByRole('heading', { name: 'Создать приказ', exact: true }).click();
      assert.equal(await popup.count(), 0);

      // Keyboard-only group -> type selection, using the normal native Enter.
      await trigger.focus();
      await page.keyboard.press('Enter');
      await page.keyboard.press('ArrowDown');
      await page.keyboard.press('ArrowRight');
      await popup.locator('[data-type-code="LEAVE.ANNUAL.GRANT"]').waitFor();
      await page.waitForFunction(() => document.activeElement?.getAttribute('data-type-code') === 'LEAVE.ANNUAL.GRANT');
      await page.keyboard.press('Enter');
      report.selected.push(await selected(page, api, 'LEAVE.ANNUAL.GRANT', locale));

      // Place the field near the right edge to exercise the left-opening path.
      await page.getByRole('dialog').evaluate(element => { element.style.width = '320px'; element.style.marginLeft = 'auto'; element.style.marginRight = '0'; });
      await trigger.click();
      await popup.locator('[data-group="employment"]').click();
      assert.equal(await popup.getAttribute('data-side'), 'left');
      const edgeBox = await popup.boundingBox();
      assert.ok(edgeBox.x >= 8 && edgeBox.x + edgeBox.width <= 1432);
      report.edge = { opensLeft: true, withinViewport: true };
      await page.screenshot({ path: path.join(folder, `edge-${language}.png`) });
      await page.keyboard.press('Escape');
      report.languages.push({ language, sevenGroups: true, allTenTypes: true, diagonalHover: true, crossLanguageSearch: true, keyboard: true, escape: true, outsideClick: true, documentLanguageIndependent: true });
      await context.close();
    }

    const touch = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    await touch.addInitScript(value => localStorage.setItem('access_token', value), token);
    const page = await touch.newPage();
    page.setDefaultTimeout(20000);
    await openForm(page, 'kk');
    await page.getByRole('button', { name: 'Тип кадрового приказа', exact: true }).tap();
    const popup = page.getByTestId('personnel-order-type-menu');
    await popup.locator('[data-group="employment"]').tap();
    assert.equal(await popup.getAttribute('data-side'), 'below');
    await page.screenshot({ path: path.join(folder, 'touch-menu.png') });
    await popup.locator('[data-type-code="TRANSFER"]').tap();
    await selected(page, api, 'TRANSFER', 'kk');
    report.touch = { groupTap: true, typeTap: true, narrowViewport: true };
    await page.screenshot({ path: path.join(folder, 'touch-selected.png') });
    await touch.close();
    assert.deepEqual(report.browserErrors, []);
    assert.deepEqual(report.writes, []); // No order, template or event writes.
    report.result = 'passed';
  } finally {
    await api.put('/personnel/settings', { data: { language: originalLanguage } });
    await browser.close(); await api.dispose();
    fs.writeFileSync(path.join(folder, 'browser-report.json'), JSON.stringify(report, null, 2));
  }
  console.log(JSON.stringify(report, null, 2));
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
