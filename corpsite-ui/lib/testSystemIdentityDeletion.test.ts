import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({ apiFetchJson: vi.fn() }));

import { apiFetchJson } from "@/lib/api";
import {
  previewSystemIdentities,
  probeSystemIdentityDeletionAccess,
  searchSystemIdentities,
} from "./testSystemIdentityDeletion";

const fetchJson = vi.mocked(apiFetchJson);

beforeEach(() => fetchJson.mockReset().mockResolvedValue({}));

describe("test system identity deletion API contract", () => {
  it("uses a mask only in search", async () => {
    await searchSystemIdentities({ objectType: "USER", field: "login", selector: "test.?ser*" });
    expect(fetchJson).toHaveBeenLastCalledWith("/directory/test-system-identity-deletion/search", {
      method: "POST",
      body: { object_type: "USER", field: "login", mask: "test.?ser*" },
    });
  });

  it("maps a numeric selector to one exact technical ID", async () => {
    await searchSystemIdentities({ objectType: "ROLE", field: "code", selector: " 42 " });
    expect(fetchJson).toHaveBeenLastCalledWith("/directory/test-system-identity-deletion/search", {
      method: "POST",
      body: { object_type: "ROLE", field: "code", object_ids: [42] },
    });
  });

  it("previews only the exact typed selection", async () => {
    const targets = [{ object_type: "ROLE" as const, object_id: 9 }];
    await previewSystemIdentities(targets);
    expect(fetchJson).toHaveBeenLastCalledWith("/directory/test-system-identity-deletion/preview", {
      method: "POST", body: { targets },
    });
  });

  it("uses a read-only exact-ID search to probe the backend permission", async () => {
    await probeSystemIdentityDeletionAccess();
    expect(fetchJson).toHaveBeenLastCalledWith("/directory/test-system-identity-deletion/search", {
      method: "POST",
      body: { object_type: "USER", field: "full_name", object_ids: [2147483647] },
    });
  });
});
