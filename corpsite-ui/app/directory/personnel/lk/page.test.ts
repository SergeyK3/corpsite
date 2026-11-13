import { afterEach, expect, it, vi } from "vitest";

import PersonnelLkWorkplacePage from "./page";

const redirectMock = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ redirect: redirectMock }));
vi.mock("../_components/PersonnelLkSectionPageClient", () => ({ default: () => null }));

afterEach(() => redirectMock.mockReset());

it("keeps the existing personal-card report URL", async () => {
  await PersonnelLkWorkplacePage({ searchParams: Promise.resolve({ view: "reports", report: "cards" }) });
  expect(redirectMock).not.toHaveBeenCalled();
});

it("redirects the previous category-report URL to the new section", async () => {
  await PersonnelLkWorkplacePage({ searchParams: Promise.resolve({ view: "reports", report: "categories" }) });
  expect(redirectMock).toHaveBeenCalledWith("/directory/personnel/qualification-categories");
});
