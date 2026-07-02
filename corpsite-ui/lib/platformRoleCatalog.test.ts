import { describe, expect, it, vi, beforeEach } from "vitest";

import { listPlatformRoleCatalog } from "./platformRoleCatalog";
import { apiFetchJson } from "./api";

vi.mock("./api", () => ({
  apiFetchJson: vi.fn(),
}));

describe("listPlatformRoleCatalog", () => {
  beforeEach(() => {
    vi.mocked(apiFetchJson).mockReset();
  });

  it("loads full public.roles catalog without org scope filters", async () => {
    vi.mocked(apiFetchJson).mockResolvedValue({
      items: [
        { role_id: 1, role_code: "QM_HEAD", role_name: "QM Head", is_active: true },
        { role_id: 99, role_code: "UNUSED_ROLE", role_name: "Unused Role", is_active: true },
      ],
    });

    const rows = await listPlatformRoleCatalog();

    expect(apiFetchJson).toHaveBeenCalledWith("/directory/roles", {
      query: {
        limit: 500,
        offset: 0,
        is_active: "true",
      },
    });
    expect(rows.map((r) => r.code)).toEqual(expect.arrayContaining(["QM_HEAD", "UNUSED_ROLE"]));
    expect(rows).toHaveLength(2);
  });

  it("does not pass org_group_id or org_unit_id (not roles-in-use filter)", async () => {
    vi.mocked(apiFetchJson).mockResolvedValue({ items: [] });
    await listPlatformRoleCatalog();
    const call = vi.mocked(apiFetchJson).mock.calls[0];
    const query = call?.[1]?.query as Record<string, unknown>;
    expect(query).not.toHaveProperty("org_group_id");
    expect(query).not.toHaveProperty("org_unit_id");
  });
});
