/**
 * Capture HR applicant workplace UI screenshots for architecture report.
 * Run: node scripts/capture-hr-applicant-workplace-screenshots.mjs
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, "../hr-applicant-workplace-verify");

const samples = [
  {
    name: "01-applicants-journal",
    title: "Претенденты — журнал HR",
    body: `
      <nav class="tabs"><span class="active">Претенденты</span><span>Адаптация</span></nav>
      <h1>Претенденты</h1>
      <p class="muted">Рабочее место HR: регистрация, ссылка на заполнение личной карточки, контроль этапов.</p>
      <table>
        <thead><tr><th>ФИО</th><th>ИИН</th><th>Статус</th><th>Анкета</th></tr></thead>
        <tbody>
          <tr><td>Ахметов Айдар Серикович</td><td>900101300123</td><td><span class="badge sky">Ожидает заполнения</span></td><td>Выдана</td></tr>
          <tr><td>Сейтова Алия Маратовна</td><td>950505400456</td><td><span class="badge green">Личная карточка заполнена</span></td><td>Отправлена</td></tr>
        </tbody>
      </table>
    `,
  },
  {
    name: "02-applicant-detail-intake-link",
    title: "Карточка претендента — выдача ссылки",
    body: `
      <h2>Кадровое обращение #42</h2>
      <p class="muted">Ахметов Айдар Серикович · person #204</p>
      <section>
        <h3>Заполнение личной карточки</h3>
        <div class="link-box">http://localhost:3000/intake/demo-token-abc123</div>
        <div class="actions">
          <button class="primary">Создать ссылку на заполнение личной карточки</button>
          <button>Скопировать ссылку</button>
          <button class="danger">Аннулировать ссылку</button>
        </div>
      </section>
    `,
  },
  {
    name: "03-applicant-card-gated-hire",
    title: "Личная карточка — приказ доступен после анкеты",
    body: `
      <div class="banner">Заявитель</div>
      <h1>Личная карточка по учёту кадров</h1>
      <p class="note">Личная карточка заполнена. Можно перейти к оформлению приказа о приёме.</p>
      <button class="cta">Создать приказ о приёме</button>
    `,
  },
  {
    name: "04-staff-without-applicants",
    title: "Персонал — без заявителей, переход в Претенденты",
    body: `
      <h1>Персонал</h1>
      <div class="toolbar"><a class="link-btn" href="#">Претенденты</a><button>Обновить</button></div>
      <p class="muted">В этом разделе отображаются только действующие сотрудники. Претенденты обрабатываются в «Кадровые процессы → Претенденты».</p>
    `,
  },
];

const pageStyles = `
  body { font-family: Segoe UI, sans-serif; background: #fafafa; color: #18181b; margin: 0; padding: 24px; }
  .frame { max-width: 960px; margin: 0 auto; background: #fff; border: 1px solid #e4e4e7; border-radius: 16px; padding: 24px; }
  h1, h2, h3 { margin: 0 0 12px; }
  .muted, .note { color: #71717a; font-size: 14px; }
  .tabs { display: flex; gap: 8px; margin-bottom: 16px; }
  .tabs span { padding: 8px 12px; border-radius: 8px; background: #f4f4f5; font-size: 14px; }
  .tabs .active { background: #2563eb; color: #fff; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 16px; }
  th, td { border-bottom: 1px solid #e4e4e7; padding: 10px 12px; text-align: left; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; }
  .badge.sky { background: #e0f2fe; color: #075985; }
  .badge.green { background: #d1fae5; color: #065f46; }
  .link-box { background: #f0f9ff; border: 1px solid #bae6fd; padding: 12px; border-radius: 8px; font-family: monospace; font-size: 12px; margin: 12px 0; }
  .actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
  button, .link-btn { border-radius: 8px; border: 1px solid #d4d4d8; padding: 8px 12px; background: #fff; font-size: 14px; }
  button.primary, .cta { background: #0284c7; color: #fff; border-color: #0284c7; }
  button.danger { color: #b91c1c; border-color: #fecaca; }
  .banner { color: #92400e; font-weight: 700; letter-spacing: 0.08em; font-size: 12px; margin-bottom: 8px; }
  .toolbar { display: flex; gap: 8px; margin: 12px 0; }
  .link-btn { background: #f0f9ff; color: #0c4a6e; text-decoration: none; border-color: #7dd3fc; }
`;

async function main() {
  await mkdir(outDir, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });

  for (const sample of samples) {
    await page.setContent(`
      <!doctype html><html><head><style>${pageStyles}</style></head>
      <body><div class="frame">${sample.body}</div></body></html>
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
