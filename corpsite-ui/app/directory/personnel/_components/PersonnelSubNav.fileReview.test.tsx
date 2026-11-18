import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MeInfo } from "@/lib/types";
import PersonnelLkSubNav from "./PersonnelLkSubNav";
import PersonnelSubNav from "./PersonnelSubNav";

let pathname = "/directory/personnel/journal";
let currentUser: MeInfo | null = null;

vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
vi.mock("@/lib/currentUser", () => ({ useCurrentUser: () => currentUser }));

afterEach(cleanup);

describe("Personnel file review navigation", () => {
  it("shows blue parent and nested review tabs in the required order", () => {
    pathname = "/directory/personnel/file-review";
    currentUser = { role_code: "HR_HEAD", has_personnel_admin: true, has_personnel_files_review: true };

    render(<><PersonnelSubNav /><PersonnelLkSubNav activeTab="review" /></>);

    const parent = screen.getByRole("navigation", { name: "Навигация кадровых процессов" }).getByRole("link", { name: "Личные карточки" });
    expect(parent).toHaveAttribute("aria-current", "page");
    expect(parent).toHaveClass("bg-blue-600", "text-white");
    const nested = screen.getByRole("navigation", { name: "Личные карточки" });
    expect(nested.querySelectorAll("a")).toHaveLength(3);
    expect(Array.from(nested.querySelectorAll("a"), (link) => link.textContent)).toEqual(["Список карточек", "Проверка карточек", "Отчёты"]);
    const review = screen.getByRole("link", { name: "Проверка карточек" });
    expect(review).toHaveAttribute("href", pathname);
    expect(review).toHaveAttribute("aria-current", "page");
    expect(review).toHaveClass("bg-blue-600", "text-white");
    expect(screen.queryByRole("link", { name: "Проверка файлов" })).toBeNull();
  });

  it("hides the tab without file review permission, even for other HR users", () => {
    pathname = "/directory/personnel/journal";
    currentUser = { role_code: "HR_HEAD", has_personnel_admin: true, has_personnel_files_review: false };

    render(<><PersonnelSubNav /><PersonnelLkSubNav activeTab="list" /></>);

    expect(screen.queryByRole("link", { name: "Проверка карточек" })).toBeNull();
  });

  it("keeps the reviewer-only parent linked to the permitted review route", () => {
    pathname = "/directory/personnel/file-review";
    currentUser = { has_personnel_files_review: true };

    render(<><PersonnelSubNav /><PersonnelLkSubNav activeTab="review" /></>);

    expect(screen.getByRole("navigation", { name: "Навигация кадровых процессов" }).getByRole("link", { name: "Личные карточки" })).toHaveAttribute("href", pathname);
    expect(screen.getByRole("navigation", { name: "Личные карточки" }).querySelectorAll("a")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Проверка карточек" })).toHaveAttribute("aria-current", "page");
  });
});
