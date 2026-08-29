import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelSubNav from "./PersonnelSubNav";

const navigation = vi.hoisted(() => ({ pathname: "/directory/personnel/import" }));

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
}));

afterEach(() => {
  cleanup();
  navigation.pathname = "/directory/personnel/import";
});

describe("PersonnelSubNav control list parent", () => {
  it("renders one control-list parent and keeps former child sections out of the top level", () => {
    render(<PersonnelSubNav />);

    expect(screen.getByRole("link", { name: "Контрольный список" })).toHaveAttribute(
      "href",
      "/directory/personnel/import",
    );
    for (const title of ["Аналитика", "Проверка записей", "Изменения реестра", "Миграция", "Мед. категории"]) {
      expect(screen.queryByRole("link", { name: title })).not.toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: "Отчёты" })).toHaveAttribute(
      "href",
      "/directory/personnel/reports",
    );
  });

  it.each([
    "/directory/personnel/import",
    "/directory/personnel/import/148",
    "/directory/personnel/import/review",
    "/directory/personnel/import/148/review",
    "/directory/personnel/hr-change-events",
    "/directory/personnel/migration/employment/42",
    "/directory/personnel/baselines",
    "/directory/personnel/monthly-references/17",
  ])("marks the parent active on %s", (pathname) => {
    navigation.pathname = pathname;
    render(<PersonnelSubNav />);
    expect(screen.getByRole("link", { name: "Контрольный список" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("does not mark the parent active on reports", () => {
    navigation.pathname = "/directory/personnel/reports";
    render(<PersonnelSubNav />);
    expect(screen.getByRole("link", { name: "Контрольный список" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("link", { name: "Отчёты" })).toHaveAttribute("aria-current", "page");
  });
});
