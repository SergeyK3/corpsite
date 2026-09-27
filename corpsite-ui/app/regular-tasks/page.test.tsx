import { describe, expect, it, vi } from "vitest";

const { redirect } = vi.hoisted(() => ({ redirect: vi.fn() }));

vi.mock("next/navigation", () => ({ redirect }));

import RegularTasksAdminPage from "./page";

describe("legacy regular tasks route", () => {
  it("redirects to task templates without losing query parameters", async () => {
    await RegularTasksAdminPage({
      searchParams: Promise.resolve({ q: "monthly", view: "runs" }),
    });

    expect(redirect).toHaveBeenCalledWith("/admin/templates?q=monthly&view=runs&section=tasks");
  });
});
