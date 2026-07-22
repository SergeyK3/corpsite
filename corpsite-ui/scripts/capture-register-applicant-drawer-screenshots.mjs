/**
 * Capture register applicant drawer screenshots for WP report.
 * Run: node scripts/capture-register-applicant-drawer-screenshots.mjs
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, "../register-applicant-drawer-verify");

const pageStyles = `
  body { font-family: Segoe UI, sans-serif; background: rgba(0,0,0,0.3); margin: 0; }
  aside { margin-left: auto; width: 640px; min-height: 100vh; background: #fff; border-left: 1px solid #e4e4e7; padding: 16px; box-sizing: border-box; }
  h2 { margin: 0 0 4px; font-size: 18px; }
  h3 { margin: 16px 0 8px; font-size: 14px; }
  .muted { color: #71717a; font-size: 13px; }
  .preview { background: #fafafa; border: 1px solid #e4e4e7; border-radius: 8px; padding: 12px; font-size: 13px; margin-top: 8px; }
  label { display: block; font-size: 13px; margin-bottom: 12px; }
  label span { display: block; color: #52525b; margin-bottom: 4px; }
  select, input { width: 100%; padding: 8px 12px; border-radius: 8px; border: 1px solid #d4d4d8; font-size: 13px; box-sizing: border-box; }
  select:disabled { opacity: 0.55; background: #f4f4f5; }
  .section-note { font-size: 12px; color: #71717a; margin-top: 4px; }
  button.primary { background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 8px 16px; margin-top: 16px; }
`;

const samples = [
  {
    name: "01-after-iin-preview",
    title: "После проверки ИИН",
    body: `
      <h2>Зарегистрировать претендента</h2>
      <p class="muted">Регистрация бумажного кадрового обращения</p>
      <h3>ИИН</h3>
      <input value="900101300123" readonly />
      <div class="preview">Person: не найден · Активное обращение: нет · Активный сотрудник: нет</div>
      <h3>Основные данные</h3>
      <label><span>ФИО</span><input value="Новый Претендент" /></label>
    `,
  },
  {
    name: "02-intended-placement-cascade",
    title: "Каскад предполагаемого места трудоустройства",
    body: `
      <h2>Зарегистрировать претендента</h2>
      <h3>Предполагаемое место трудоустройства</h3>
      <p class="section-note">Сохраняется в кадровом обращении и используется для предзаполнения личной карточки и приказа о приёме.</p>
      <label><span>Группа отделений *</span><select><option selected>Терапевтическое отделение</option></select></label>
      <label><span>Отделение *</span><select><option selected>Отделение №1</option></select></label>
      <label><span>Должность *</span><select><option selected>Медицинская сестра</option></select></label>
      <label><span>Ставка</span><input value="1" /></label>
      <button class="primary">Зарегистрировать</button>
    `,
  },
  {
    name: "03-unit-disabled-before-group",
    title: "Отделение отключено до выбора группы",
    body: `
      <h2>Зарегистрировать претендента</h2>
      <h3>Предполагаемое место трудоустройства</h3>
      <label><span>Группа отделений *</span><select><option>Выберите группу отделений</option></select></label>
      <label><span>Отделение *</span><select disabled><option>Выберите отделение</option></select></label>
      <label><span>Должность *</span><select disabled><option>Сначала выберите отделение</option></select></label>
    `,
  },
];

async function main() {
  await mkdir(outDir, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 900, height: 900 } });

  for (const sample of samples) {
    await page.setContent(`
      <!doctype html><html><head><style>${pageStyles}</style></head>
      <body><aside>${sample.body}</aside></body></html>
    `);
    const outPath = path.join(outDir, `${sample.name}.png`);
    await page.screenshot({ path: outPath, fullPage: true });
    console.log(`Saved ${outPath}`);
  }

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
