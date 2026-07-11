import { chromium, type Browser, type BrowserContext, type Page } from "playwright";

const DEFAULT_TIMEOUT_MS = 30_000;
const DEFAULT_MAX_CONCURRENT = 2;

export type PersonnelOrderPdfBrowserLimits = {
  timeoutMs: number;
  maxConcurrent: number;
};

function readPositiveInt(name: string, fallback: number): number {
  const raw = Number(process.env[name] ?? "");
  if (!Number.isFinite(raw) || raw <= 0) return fallback;
  return Math.trunc(raw);
}

export function getPersonnelOrderPdfBrowserLimits(): PersonnelOrderPdfBrowserLimits {
  return {
    timeoutMs: readPositiveInt("PERSONNEL_ORDER_PDF_TIMEOUT_MS", DEFAULT_TIMEOUT_MS),
    maxConcurrent: readPositiveInt("PERSONNEL_ORDER_PDF_MAX_CONCURRENT", DEFAULT_MAX_CONCURRENT),
  };
}

let browserPromise: Promise<Browser> | null = null;
let activeGenerations = 0;
const waitQueue: Array<() => void> = [];

async function getBrowser(): Promise<Browser> {
  if (!browserPromise) {
    browserPromise = chromium
      .launch({
        headless: true,
        args: ["--disable-dev-shm-usage", "--no-sandbox"],
      })
      .catch((err) => {
        browserPromise = null;
        throw err;
      });
  }
  const browser = await browserPromise;
  if (!browser.isConnected()) {
    browserPromise = null;
    return getBrowser();
  }
  return browser;
}

async function acquireSlot(maxConcurrent: number): Promise<void> {
  if (activeGenerations < maxConcurrent) {
    activeGenerations += 1;
    return;
  }
  await new Promise<void>((resolve) => {
    waitQueue.push(() => {
      activeGenerations += 1;
      resolve();
    });
  });
}

function releaseSlot(): void {
  activeGenerations = Math.max(0, activeGenerations - 1);
  const next = waitQueue.shift();
  if (next) next();
}

export type WithPdfPageFn<T> = (page: Page, context: BrowserContext) => Promise<T>;

/**
 * Run work inside a fresh browser context/page with concurrency + timeout guards.
 * Always closes page/context; restarts browser after launch/runtime failures.
 */
export async function withPersonnelOrderPdfPage<T>(fn: WithPdfPageFn<T>): Promise<T> {
  const limits = getPersonnelOrderPdfBrowserLimits();
  await acquireSlot(limits.maxConcurrent);

  let context: BrowserContext | null = null;
  let page: Page | null = null;
  try {
    const browser = await getBrowser();
    context = await browser.newContext({
      javaScriptEnabled: false,
      viewport: { width: 794, height: 1123 },
    });
    page = await context.newPage();
    page.setDefaultTimeout(limits.timeoutMs);

    const result = await Promise.race([
      fn(page, context),
      new Promise<never>((_, reject) => {
        setTimeout(() => {
          reject(Object.assign(new Error("PDF generation timed out"), { code: "PDF_TIMEOUT" }));
        }, limits.timeoutMs);
      }),
    ]);
    return result;
  } catch (err) {
    // Force browser restart on next call after hard failures.
    const message = err instanceof Error ? err.message : String(err);
    if (/Target closed|Browser closed|Protocol error|timed out|PDF_TIMEOUT/i.test(message)) {
      try {
        const current = await browserPromise;
        await current?.close().catch(() => undefined);
      } catch {
        // ignore
      }
      browserPromise = null;
    }
    throw err;
  } finally {
    try {
      await page?.close().catch(() => undefined);
    } finally {
      try {
        await context?.close().catch(() => undefined);
      } finally {
        releaseSlot();
      }
    }
  }
}

/** Test/ops helper — close singleton browser if open. */
export async function closePersonnelOrderPdfBrowser(): Promise<void> {
  if (!browserPromise) return;
  try {
    const browser = await browserPromise;
    await browser.close().catch(() => undefined);
  } finally {
    browserPromise = null;
  }
}
