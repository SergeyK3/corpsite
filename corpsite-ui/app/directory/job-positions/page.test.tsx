import { expect, it, vi } from "vitest";
import { redirect } from "next/navigation";
import JobPositionsPage from "./page";

vi.mock("next/navigation", () => ({ redirect: vi.fn() }));

it("redirects the legacy job positions route to the current catalog", () => {
  JobPositionsPage();
  expect(redirect).toHaveBeenCalledWith("/directory/positions");
});
