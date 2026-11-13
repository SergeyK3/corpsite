import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelSubNav from "./PersonnelSubNav";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    className,
  }: {
    children: React.ReactNode;
    href: string;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/directory/personnel/lk",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/lib/currentUser", () => ({
  useCurrentUser: () => ({
    has_ppr_migration_status_read: true,
    can_approve_test_personnel_deletion: true,
  }),
}));

vi.mock("../_lib/importApi.client", () => ({
  listImportBatches: vi.fn(async () => ({ items: [] })),
}));

afterEach(() => {
  cleanup();
});

describe("PersonnelSubNav", () => {
  it("includes Личные карточки navigation item", () => {
    render(<PersonnelSubNav />);

    const lkLink = screen.getByRole("link", { name: "Личные карточки" });
    expect(lkLink).toHaveAttribute("href", "/directory/personnel/lk");
    expect(lkLink.className).toContain("bg-blue-600");
    expect(screen.queryByRole("link", { name: "Претенденты" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Кадровые обращения" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Отчёты" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Проверка биографии" })).not.toBeInTheDocument();
    const topLinks = screen.getByRole("navigation", { name: "Навигация кадровых процессов" }).querySelectorAll("a");
    const titles = Array.from(topLinks, (link) => link.textContent);
    expect(titles[titles.indexOf("Личные карточки") + 1]).toBe("Квалиф. категории");
  });

  it("keeps the report inside Личные карточки without a top-level Сводка", () => {
    render(<PersonnelSubNav />);
    expect(screen.getByRole("link", { name: "Личные карточки" })).toHaveAttribute("href", "/directory/personnel/lk");
    expect(screen.queryByRole("link", { name: "Сводка" })).not.toBeInTheDocument();
  });

  it("keeps the test-personnel approval route while using its shorter title", () => {
    render(<PersonnelSubNav />);

    const deletion = screen.getByRole("link", { name: "Удаление тестовых данных" });
    expect(deletion).toHaveAttribute("href", "/directory/personnel/test-data-deletion-approvals");
    expect(
      screen.queryByRole("link", { name: "Согласование удаления тестовых данных" }),
    ).not.toBeInTheDocument();
  });
});
