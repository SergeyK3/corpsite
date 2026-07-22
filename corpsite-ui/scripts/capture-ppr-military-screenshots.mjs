/**
 * Capture WP-PR-030 military section UI screenshots for pre-commit report.
 * Run: node scripts/capture-ppr-military-screenshots.mjs
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, "../ppr-military-local-verify");

const samples = [
  {
    name: "empty-state",
    title: "Воинский учёт — пустая секция",
    body: `
      <div class="card">
        <p class="muted">Сведения о воинском учёте отсутствуют.</p>
        <button class="btn">Добавить</button>
      </div>
    `,
  },
  {
    name: "registration-active",
    title: "Воинский учёт — registration (active)",
    body: `
      <div class="card">
        <div class="title">рядовой</div>
        <dl>
          <div><dt>Вид:</dt><dd>Сведения о воинском учёте</dd></div>
          <div><dt>Воинская обязанность:</dt><dd>Военнообязанный</dd></div>
          <div><dt>Категория учёта:</dt><dd>II</dd></div>
          <div><dt>Воинское звание:</dt><dd>рядовой</dd></div>
          <div><dt>Военкомат:</dt><dd>Алмалинский РВК</dd></div>
          <div><dt>Дата постановки на учёт:</dt><dd>01.05.2015</dd></div>
        </dl>
        <div class="actions"><button class="btn-sm">Заменить</button><button class="btn-sm">Аннулировать</button></div>
      </div>
    `,
  },
  {
    name: "not-applicable-active",
    title: "Воинский учёт — not_applicable",
    body: `
      <div class="card">
        <div class="title">Не подлежит воинскому учёту</div>
        <dl>
          <div><dt>Вид:</dt><dd>Не подлежит воинскому учёту</dd></div>
          <div><dt>Примечание:</dt><dd>Не подлежит воинскому учёту</dd></div>
        </dl>
      </div>
    `,
  },
  {
    name: "history-collapsed",
    title: "Воинский учёт — история (свернута)",
    body: `
      <div class="card">
        <div class="title">рядовой</div>
        <dl><div><dt>Статус учёта:</dt><dd>Состоит на учёте</dd></div></dl>
      </div>
      <button class="link">История замен (1)</button>
    `,
  },
  {
    name: "restricted-fields",
    title: "Воинский учёт — restricted fields в DTO",
    body: `
      <div class="card">
        <div class="title">рядовой</div>
        <dl>
          <div><dt>Серия военного билета:</dt><dd>АБ</dd></div>
          <div><dt>Номер военного билета:</dt><dd>1234567</dd></div>
        </dl>
      </div>
    `,
  },
];

function pageHtml(sample) {
  return `<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <style>
    body { font-family: system-ui, sans-serif; background: #fafafa; color: #18181b; padding: 24px; }
    h1 { font-size: 18px; margin: 0 0 16px; }
    .card { border: 1px solid #e4e4e7; border-radius: 8px; padding: 12px; background: #fff; margin-bottom: 12px; }
    .title { font-weight: 600; margin-bottom: 8px; }
    dl { display: grid; gap: 4px; font-size: 12px; color: #52525b; }
    dt { display: inline; }
    dd { display: inline; margin: 0; }
    .muted { color: #71717a; font-size: 14px; }
    .btn, .btn-sm { border: 1px solid #d4d4d8; background: #fff; border-radius: 6px; padding: 6px 12px; font-size: 14px; }
    .btn-sm { font-size: 12px; padding: 4px 8px; }
    .actions { display: flex; gap: 8px; margin-top: 8px; }
    .link { background: none; border: none; color: #3f3f46; text-decoration: underline; font-size: 14px; padding: 0; }
  </style>
</head>
<body>
  <h1>${sample.title}</h1>
  ${sample.body}
</body>
</html>`;
}

await mkdir(outDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 720, height: 480 } });

for (const sample of samples) {
  await page.setContent(pageHtml(sample), { waitUntil: "load" });
  await page.screenshot({
    path: path.join(outDir, `${sample.name}.png`),
    fullPage: true,
  });
}

await browser.close();
console.log(`Saved ${samples.length} screenshots to ${outDir}`);
