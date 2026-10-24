import { afterEach, expect, it, vi } from "vitest";
import { allExportPages, downloadTableExcel, normalizeExportPage } from "./tableExport";

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("fetches every page, retaining filter values and order", async () => {
  const rows = Array.from({ length: 231 }, (_, i) => i);
  const load = vi.fn(async ({ offset, limit }) => ({ items: rows.slice(offset, offset + limit), total: rows.length }));
  expect(await allExportPages(load)).toEqual(rows);
  expect(load.mock.calls.map(([page]) => page.offset)).toEqual([0, 50, 100, 150, 200]);
});
it("does not return a silent partial export when a page fails or disappears", async () => {
  const load = vi.fn().mockResolvedValueOnce({ items: [1], total: 2 }).mockRejectedValueOnce(new Error("403"));
  await expect(allExportPages(load)).rejects.toThrow("403");
  load.mockReset().mockResolvedValueOnce({ items: [1], total: 2 }).mockResolvedValueOnce({ items: [], total: 2 });
  await expect(allExportPages(load)).rejects.toThrow("Список изменился");
});
it("supports unpaginated legacy responses", () => {
  expect(normalizeExportPage([1, 2])).toEqual({ items: [1, 2], total: 2 });
  expect(normalizeExportPage({ data: [1], total: 3 })).toEqual({ items: [1], total: 3 });
});
it("downloads a real XLSX response and cleans up the link", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => new Blob(["xlsx"]) });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("URL", class extends URL {
    static createObjectURL = vi.fn(() => "blob:export");
    static revokeObjectURL = vi.fn();
  });
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const table = { headers: ["ИИН"], rows: [["001234567890"]] };
  await downloadTableExcel(table, "Карточки.xlsx");
  expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining("/exports/table.xlsx"), expect.objectContaining({ method: "POST", body: JSON.stringify(table), cache: "no-store" }));
  expect(click).toHaveBeenCalledOnce();
  expect(document.querySelector("a[download]")).toBeNull();
});
it("reports an empty result without sending a request", async () => {
  vi.stubGlobal("fetch", vi.fn());
  await expect(downloadTableExcel({ headers: ["ID"], rows: [] }, "Данные.xlsx")).rejects.toThrow("Нет записей");
  expect(fetch).not.toHaveBeenCalled();
});
it("does not download when formatting is denied", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 }));
  await expect(downloadTableExcel({ headers: ["ID"], rows: [[1]] }, "Данные.xlsx")).rejects.toThrow("Не удалось выгрузить");
});
