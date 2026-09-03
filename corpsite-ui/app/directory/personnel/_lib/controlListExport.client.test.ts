import { webcrypto } from "node:crypto";

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ControlListExportUiError,
  exportControlListFile,
  filenameFromContentDisposition,
  suggestedControlListFilename,
} from "./controlListExport.client";

const XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
const CONTENT = new Uint8Array([80, 75, 3, 4, 1, 2, 3]);

function response(
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(CONTENT, {
    status,
    headers: {
      "Content-Type": XLSX_MIME,
      "Content-Disposition":
        "attachment; filename=control-list.xlsx; filename*=UTF-8''%D0%9A%D0%BE%D0%BD%D1%82%D1%80%D0%BE%D0%BB%D1%8C%D0%BD%D1%8B%D0%B9_%D1%81%D0%BF%D0%B8%D1%81%D0%BE%D0%BA_2026-09-03.xlsx",
      ...headers,
    },
  });
}

async function checksum(): Promise<string> {
  const value = await webcrypto.subtle.digest("SHA-256", CONTENT);
  return Array.from(new Uint8Array(value), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function fallbackDeps(fetchImpl: typeof fetch) {
  const cleanupTasks: Array<() => void> = [];
  return {
    browserWindow: window,
    browserDocument: document,
    fetchImpl,
    cryptoImpl: webcrypto as Crypto,
    urlApi: {
      createObjectURL: vi.fn(() => "blob:control-list"),
      revokeObjectURL: vi.fn(),
    },
    scheduleCleanup: vi.fn((callback: () => void) => cleanupTasks.push(callback)),
    cleanupTasks,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("control-list export browser client", () => {
  it("opens the system picker before the backend request and writes the complete blob", async () => {
    const order: string[] = [];
    const write = vi.fn(async () => undefined);
    const close = vi.fn(async () => undefined);
    const picker = vi.fn(async () => {
      order.push("picker");
      return { createWritable: async () => ({ write, close }) };
    });
    const fetchImpl = vi.fn(async () => {
      order.push("fetch");
      return response();
    }) as unknown as typeof fetch;

    const outcome = await exportControlListFile({
      browserWindow: { ...window, showSaveFilePicker: picker } as never,
      fetchImpl,
      now: new Date("2026-09-03T00:00:00Z"),
    });

    expect(order).toEqual(["picker", "fetch"]);
    expect(picker).toHaveBeenCalledWith({
      suggestedName: "Контрольный_список_2026-09-03.xlsx",
      excludeAcceptAllOption: true,
      types: [{ description: "Книга Excel", accept: { [XLSX_MIME]: [".xlsx"] } }],
    });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(write).toHaveBeenCalledWith(expect.any(Blob));
    expect(close).toHaveBeenCalledTimes(1);
    expect(outcome).toBe("saved");
  });

  it("treats picker cancellation as a silent outcome without a backend request", async () => {
    const fetchImpl = vi.fn() as unknown as typeof fetch;
    const picker = vi.fn(async () => {
      throw new DOMException("cancelled", "AbortError");
    });
    await expect(
      exportControlListFile({
        browserWindow: { ...window, showSaveFilePicker: picker } as never,
        fetchImpl,
      }),
    ).resolves.toBe("cancelled");
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("uses the UTF-8 Content-Disposition filename and always cleans up fallback resources", async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const fetchImpl = vi.fn(async () => response()) as unknown as typeof fetch;
    const deps = fallbackDeps(fetchImpl);
    const outcome = await exportControlListFile(deps);

    expect(outcome).toBe("downloaded");
    expect(click).toHaveBeenCalledTimes(1);
    expect(deps.urlApi.createObjectURL).toHaveBeenCalledTimes(1);
    expect(deps.urlApi.revokeObjectURL).not.toHaveBeenCalled();
    expect(deps.cleanupTasks).toHaveLength(1);
    deps.cleanupTasks[0]();
    expect(deps.urlApi.revokeObjectURL).toHaveBeenCalledWith("blob:control-list");
    expect(document.querySelector('a[download="Контрольный_список_2026-09-03.xlsx"]')).toBeNull();
    expect(fetchImpl).toHaveBeenCalledWith(
      expect.any(URL),
      expect.objectContaining({ method: "POST", cache: "no-store" }),
    );
    expect((fetchImpl.mock.calls[0][0] as URL).pathname).toBe(
      "/directory/personnel/control-list/export",
    );
  });

  it("sanitizes Content-Disposition and enforces the xlsx extension", () => {
    expect(filenameFromContentDisposition('attachment; filename="report"')).toBe("report.xlsx");
    expect(filenameFromContentDisposition('attachment; filename="../../bad?.exe"')).toBe("bad_.xlsx");
    expect(
      filenameFromContentDisposition(
        "attachment; filename=control-list.xlsx; filename*=UTF-8''%E0%A4%A",
      ),
    ).toBe("control-list.xlsx");
    expect(filenameFromContentDisposition("attachment; filename=bad\r\nInjected: yes")).toBe(
      "Контрольный_список.xlsx",
    );
    expect(suggestedControlListFilename(new Date("2026-09-03T00:00:00Z"))).toMatch(/\.xlsx$/);
  });

  it("accepts a matching SHA-256 and rejects a mismatch before fallback download", async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const goodFetch = vi.fn(async () => response(200, { "X-Content-SHA256": await checksum() })) as unknown as typeof fetch;
    await expect(exportControlListFile(fallbackDeps(goodFetch))).resolves.toBe("downloaded");
    expect(click).toHaveBeenCalledTimes(1);

    const badFetch = vi.fn(async () => response(200, { "X-Content-SHA256": "0".repeat(64) })) as unknown as typeof fetch;
    const badDeps = fallbackDeps(badFetch);
    await expect(exportControlListFile(badDeps)).rejects.toMatchObject({ kind: "INTEGRITY" });
    expect(badDeps.urlApi.createObjectURL).not.toHaveBeenCalled();
    expect(click).toHaveBeenCalledTimes(1);
  });

  it("accepts an uppercase SHA-256 and rejects malformed checksum values", async () => {
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const upperFetch = vi.fn(async () =>
      response(200, { "X-Content-SHA256": (await checksum()).toUpperCase() }),
    ) as unknown as typeof fetch;
    await expect(exportControlListFile(fallbackDeps(upperFetch))).resolves.toBe("downloaded");

    const malformedFetch = vi.fn(async () =>
      response(200, { "X-Content-SHA256": "not-a-sha256" }),
    ) as unknown as typeof fetch;
    await expect(exportControlListFile(fallbackDeps(malformedFetch))).rejects.toMatchObject({
      kind: "INTEGRITY",
    });
  });

  it.each([
    [403, "FORBIDDEN"],
    [409, "CONFLICT"],
    [500, "SERVER"],
  ])("maps HTTP %s to a safe %s error", async (status, kind) => {
    const fetchImpl = vi.fn(async () => response(status)) as unknown as typeof fetch;
    await expect(exportControlListFile(fallbackDeps(fetchImpl))).rejects.toMatchObject({ kind });
  });

  it("maps a network failure to a safe server error", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error("network details");
    }) as unknown as typeof fetch;
    await expect(exportControlListFile(fallbackDeps(fetchImpl))).rejects.toEqual(
      new ControlListExportUiError("SERVER"),
    );
  });

  it.each(["backend", "checksum"] as const)(
    "does not open the selected file for writing after a %s failure",
    async (failure) => {
      const createWritable = vi.fn();
      const picker = vi.fn(async () => ({ createWritable }));
      const fetchImpl = vi.fn(async () =>
        failure === "backend"
          ? response(500)
          : response(200, { "X-Content-SHA256": "0".repeat(64) }),
      ) as unknown as typeof fetch;

      await expect(
        exportControlListFile({
          browserWindow: { ...window, showSaveFilePicker: picker } as never,
          fetchImpl,
          cryptoImpl: webcrypto as Crypto,
        }),
      ).rejects.toBeInstanceOf(ControlListExportUiError);
      expect(createWritable).not.toHaveBeenCalled();
    },
  );

  it("reports a write error without repeating the backend request", async () => {
    const abort = vi.fn(async () => undefined);
    const fetchImpl = vi.fn(async () => response()) as unknown as typeof fetch;
    const picker = vi.fn(async () => ({
      createWritable: async () => ({
        write: async () => {
          throw new Error("disk details");
        },
        close: async () => undefined,
        abort,
      }),
    }));
    await expect(
      exportControlListFile({
        browserWindow: { ...window, showSaveFilePicker: picker } as never,
        fetchImpl,
      }),
    ).rejects.toEqual(new ControlListExportUiError("WRITE"));
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(abort).toHaveBeenCalledTimes(1);
  });

  it("does not persist the blob in browser storage", async () => {
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const storageWrite = vi.spyOn(Storage.prototype, "setItem");
    const indexedDbOpen = vi.fn();
    vi.stubGlobal("indexedDB", { open: indexedDbOpen });
    const fetchImpl = vi.fn(async () => response()) as unknown as typeof fetch;
    await exportControlListFile(fallbackDeps(fetchImpl));
    expect(storageWrite).not.toHaveBeenCalled();
    expect(indexedDbOpen).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
