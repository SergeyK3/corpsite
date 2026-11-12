import { afterEach, expect, it, vi } from "vitest";

import MigrationStatusPage from "./page";

const redirectMock = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ redirect: redirectMock }));

afterEach(() => redirectMock.mockReset());

it("redirects a saved card summary link while keeping its filters", async () => {
  await MigrationStatusPage({ searchParams: Promise.resolve({ universe_id: "7", section: "category", q: "Иванова" }) });
  const href = redirectMock.mock.calls[0][0] as string;
  const url = new URL(href, "http://localhost");
  expect(url.pathname).toBe("/directory/personnel/lk");
  expect(url.searchParams.get("view")).toBe("reports");
  expect(url.searchParams.get("report")).toBe("cards");
  expect(url.searchParams.get("universe_id")).toBe("7");
  expect(url.searchParams.get("q")).toBe("Иванова");
});

it("redirects a category report link to the new top-level section", async () => {
  await MigrationStatusPage({ searchParams: Promise.resolve({ report: "categories" }) });
  expect(redirectMock).toHaveBeenCalledWith("/directory/personnel/qualification-categories");
});
