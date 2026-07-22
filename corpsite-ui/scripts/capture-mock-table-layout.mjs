import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const outputDir = path.join(repoRoot, "docs-work", "screenshots", "personnel-applications-table");
const mockHtml = path.join(outputDir, "mock-table.html");
const fileUrl = `file:///${mockHtml.replace(/\\/g, "/")}`;

const VIEWPORTS = [
  { width: 1366, height: 900, name: "1366px" },
  { width: 1600, height: 900, name: "1600px" },
  { width: 1920, height: 900, name: "1920px" },
];

async function main() {
  await mkdir(outputDir, { recursive: true });
  const browser = await chromium.launch();

  for (const viewport of VIEWPORTS) {
    const page = await browser.newPage({ viewport });
    await page.goto(fileUrl, { waitUntil: "load" });
    await page.locator('[data-testid="personnel-applications-table"]').screenshot({
      path: path.join(outputDir, `layout-preview-${viewport.name}.png`),
    });
    console.log(`Saved layout-preview-${viewport.name}.png`);
  }

  await browser.close();
}

main();
