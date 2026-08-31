import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelReportsPage from "./page";

const redirectMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  redirect: redirectMock,
}));

afterEach(() => {
  redirectMock.mockReset();
});

describe("legacy personnel reports route", () => {
  it("redirects the former default report to personnel", async () => {
    await PersonnelReportsPage({ searchParams: Promise.resolve({}) });
    expect(redirectMock).toHaveBeenCalledWith("/directory/staff?view=reports");
  });

  it.each([
    { section: "orders" },
    { report: "orders-summary" },
  ])("redirects an old orders selection to orders reports", async (searchParams) => {
    await PersonnelReportsPage({ searchParams: Promise.resolve(searchParams) });
    expect(redirectMock).toHaveBeenCalledWith("/directory/personnel/orders?view=reports");
  });
});
