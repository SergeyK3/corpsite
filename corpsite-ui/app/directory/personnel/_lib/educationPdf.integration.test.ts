// @vitest-environment node
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { expect, it, vi } from "vitest";
import { GET } from "../orders/[orderId]/pdf/route";

it.skipIf(process.env.EDUCATION_PDF_TEST !== "1").each(["DIRECTORY", "MANUAL"])("renders the official authenticated PDF route for %s against the isolated synthetic database only", async mode => {
  const root = path.resolve("..");
  const folder = path.join(root, "runtime/education-cycle");
  const output = path.join(root, "runtime/education-single-language");
  const state = JSON.parse(readFileSync(path.join(folder, "database.json"), "utf8"));
  expect(state.synthetic_only).toBe(true);
  expect(state.database).toMatch(/^corpsite_education_[a-f0-9]+_test$/);
  expect(state.port).toBe(8044);
  const prefix = mode.toLowerCase() + "-";
  const browser = JSON.parse(readFileSync(path.join(folder, prefix + "browser.json"), "utf8"));
  expect(browser.subject_mode).toBe(mode);
  const run = (flag: string) => execFileSync("python", ["runtime/education-cycle/api-check.py", flag], { cwd: root, encoding: "utf8" }).trim();
  const token = run("--token"), before = run("--state");
  vi.stubEnv("BACKEND_URL", "http://127.0.0.1:8044");
  const requests: string[] = [];
  const nativeFetch = global.fetch;
  const spy = vi.spyOn(global, "fetch").mockImplementation((input, init) => {
    const url = String(input);
    expect(url.startsWith("http://127.0.0.1:8044/")).toBe(true);
    expect(init?.method).toBe("GET");
    requests.push(url);
    // Auth/state checks between scenarios outlast uvicorn's keep-alive window.
    return nativeFetch(input, { ...init, headers: { ...init?.headers, Connection: "close" } });
  });
  try {
    for (const language of ["ru", "kk"]) {
      const response = await GET(new Request(`http://localhost/directory/personnel/orders/${browser.orderId}/pdf?language=${language}`, { headers: { authorization: `Bearer ${token}` } }), { params: { orderId: String(browser.orderId) } });
      expect(response.status).toBe(200);
      expect(response.headers.get("Content-Type")).toBe("application/pdf");
      const pdf = Buffer.from(await response.arrayBuffer());
      expect(pdf.subarray(0, 5).toString()).toBe("%PDF-");
      writeFileSync(path.join(output, `${prefix}official-${language}.pdf`), pdf);
    }
    const bilingual = await GET(new Request(`http://localhost/directory/personnel/orders/${browser.orderId}/pdf?language=kk-ru`, { headers: { authorization: `Bearer ${token}` } }), { params: { orderId: String(browser.orderId) } });
    expect(bilingual.status).toBe(422);
    expect(await bilingual.json()).toMatchObject({error:{code:"EDUCATION_SINGLE_LANGUAGE_REQUIRED"}});
    expect(requests).toHaveLength(12);
    expect(run("--state")).toBe(before);
    writeFileSync(path.join(output, prefix + "official-pdf-results.json"), JSON.stringify({ subject_mode: mode, order_id: browser.orderId, languages: ["ru", "kk"], bilingual_rejected: true, status: 200, authenticated_route: true, all_requests_to_synthetic_backend: true, protected_unchanged: true }, null, 2));
  } finally { spy.mockRestore(); vi.unstubAllEnvs(); }
}, 120000);
