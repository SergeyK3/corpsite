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
  });
});
