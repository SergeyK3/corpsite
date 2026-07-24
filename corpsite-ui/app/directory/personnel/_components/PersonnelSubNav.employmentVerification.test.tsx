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
  usePathname: () => "/directory/personnel/employment-verification",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("../_lib/importApi.client", () => ({
  listImportBatches: vi.fn(async () => ({ items: [] })),
}));

afterEach(() => {
  cleanup();
});

describe("PersonnelSubNav employment verification", () => {
  it("includes Проверка биографии tab and marks it active", () => {
    render(<PersonnelSubNav />);
    const link = screen.getByRole("link", { name: "Проверка биографии" });
    expect(link).toHaveAttribute(
      "href",
      "/directory/personnel/employment-verification",
    );
    expect(link.className).toContain("bg-blue-600");
  });
});
