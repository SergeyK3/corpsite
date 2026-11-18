import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MeInfo } from "@/lib/types";
import PersonnelSubNav from "./PersonnelSubNav";

let pathname = "/directory/personnel/journal";
let currentUser: MeInfo | null = null;

vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
vi.mock("@/lib/currentUser", () => ({ useCurrentUser: () => currentUser }));

afterEach(cleanup);

describe("Personnel file review navigation", () => {
  it("shows an active blue tab for an authorized reviewer on the review page", () => {
    pathname = "/directory/personnel/file-review";
    currentUser = { role_code: "HR_HEAD", has_personnel_admin: true, has_personnel_files_review: true };

    render(<PersonnelSubNav />);

    const tab = screen.getByRole("link", { name: "Проверка файлов" });
    expect(tab).toHaveAttribute("href", pathname);
    expect(tab).toHaveAttribute("aria-current", "page");
    expect(tab).toHaveClass("bg-blue-600", "text-white");
  });

  it("hides the tab without file review permission, even for other HR users", () => {
    pathname = "/directory/personnel/journal";
    currentUser = { role_code: "HR_HEAD", has_personnel_admin: true, has_personnel_files_review: false };

    render(<PersonnelSubNav />);

    expect(screen.queryByRole("link", { name: "Проверка файлов" })).toBeNull();
  });

  it("shows only the review tab for a reviewer without the broader HR contour", () => {
    pathname = "/directory/personnel/file-review";
    currentUser = { has_personnel_files_review: true };

    render(<PersonnelSubNav />);

    expect(screen.getAllByRole("link").map((link) => link.textContent)).toEqual(["Проверка файлов"]);
  });
});
