import { describe, expect, it, vi } from "vitest";

const redirectMock = vi.fn();
vi.mock("next/navigation", () => ({ redirect: (path: string) => redirectMock(path) }));

import EducationPage from "./page";

describe("EducationPage compatibility route", () => {
  it("redirects the legacy education route to the personal card", () => {
    EducationPage();
    expect(redirectMock).toHaveBeenCalledWith("/profile/personal-card");
  });
});
