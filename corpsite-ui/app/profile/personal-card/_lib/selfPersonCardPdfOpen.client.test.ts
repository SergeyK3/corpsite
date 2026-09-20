import { afterEach, describe, expect, it, vi } from "vitest";

import { downloadMyPersonalCardPdf } from "./selfPersonCardPdfOpen.client";

const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);
vi.mock("@/lib/api", () => ({ buildHeaders: (headers: Record<string, string>) => headers }));

afterEach(() => fetchMock.mockReset());

describe("downloadMyPersonalCardPdf", () => {
  it("uses an ID-free self PDF route", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 409 }));

    await expect(downloadMyPersonalCardPdf()).resolves.toEqual({ ok: false, error: "Личная карточка ещё не создана." });
    expect(fetchMock).toHaveBeenCalledWith(
      "/profile/personal-card/pdf",
      expect.objectContaining({ method: "GET" }),
    );
    expect(String(fetchMock.mock.calls[0]?.[0])).not.toMatch(/person_id|employee_id|persons|employees/);
  });
});
