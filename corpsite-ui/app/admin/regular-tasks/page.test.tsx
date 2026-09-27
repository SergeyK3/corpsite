import { describe, expect, it, vi } from "vitest";

const { redirect } = vi.hoisted(() => ({ redirect: vi.fn() }));

vi.mock("next/navigation", () => ({ redirect }));

import RegularTasksAdminPage from "./page";

describe("legacy regular task templates route", () => {
  it("redirects to the task templates section and preserves query parameters", async () => {
    await RegularTasksAdminPage({
      searchParams: Promise.resolve({ q: "monthly", owner: "12" }),
    });

    expect(redirect).toHaveBeenCalledWith("/admin/templates?q=monthly&owner=12&section=tasks");
  });
});
