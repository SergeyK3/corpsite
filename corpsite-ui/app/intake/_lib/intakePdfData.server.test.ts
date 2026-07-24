import { afterEach, describe, expect, it, vi } from "vitest";

import { emptyIntakeDraftPayload } from "./intakeApi.client";
import { loadIntakePdfModelByToken } from "./intakePdfData.server";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

function sessionPayload() {
  const payload = emptyIntakeDraftPayload();
  payload.personal.last_name = "Иванов";
  payload.personal.first_name = "Иван";
  payload.personal.photo_file_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  return {
    application_id: 42,
    draft_id: 1,
    link_id: 1,
    payload,
    status: "in_progress",
    read_only: false,
    link_status: "opened",
    submitted_at: null,
  };
}

describe("loadIntakePdfModelByToken photo resilience", () => {
  it("embeds JPEG data URI when photo is available", async () => {
    const jpeg = Buffer.from([0xff, 0xd8, 0xff, 0xd9]);
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/photo")) {
        return new Response(jpeg, { status: 200, headers: { "content-type": "image/jpeg" } });
      }
      return new Response(JSON.stringify(sessionPayload()), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }) as typeof fetch;

    const loaded = await loadIntakePdfModelByToken("token-abc");
    expect(loaded.model.photoDataUrl).toMatch(/^data:image\/jpeg;base64,/);
  });

  it("uses placeholder when photo is missing (404)", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/photo")) {
        return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
      }
      return new Response(JSON.stringify(sessionPayload()), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }) as typeof fetch;

    const loaded = await loadIntakePdfModelByToken("token-abc");
    expect(loaded.model.photoDataUrl).toBeNull();
  });

  it("does not abort PDF when photo is corrupt or upstream fails", async () => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/photo")) {
        return new Response(Buffer.from("not-jpeg"), {
          status: 200,
          headers: { "content-type": "image/jpeg" },
        });
      }
      return new Response(JSON.stringify(sessionPayload()), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }) as typeof fetch;

    const loaded = await loadIntakePdfModelByToken("token-corrupt");
    expect(loaded.model.photoDataUrl).toBeNull();
    expect(loaded.model.applicationId).toBe(42);

    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/photo")) {
        return new Response("boom", { status: 500 });
      }
      return new Response(JSON.stringify(sessionPayload()), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }) as typeof fetch;

    const soft = await loadIntakePdfModelByToken("token-500");
    expect(soft.model.photoDataUrl).toBeNull();
  });
});
