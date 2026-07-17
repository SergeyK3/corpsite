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
  usePathname: () => "/directory/personnel/applicants",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("../_lib/importApi.client", () => ({
  listImportBatches: vi.fn(async () => ({ items: [] })),
}));

afterEach(() => {
  cleanup();
});

describe("PersonnelSubNav", () => {
  it("includes both Кадровые обращения and Претенденты navigation items", () => {
    render(<PersonnelSubNav />);

    const applicationsLink = screen.getByRole("link", { name: "Кадровые обращения" });
    expect(applicationsLink).toHaveAttribute("href", "/directory/personnel-applications");

    const applicantsLink = screen.getByRole("link", { name: "Претенденты" });
    expect(applicantsLink).toHaveAttribute("href", "/directory/personnel/applicants");
    expect(applicantsLink.className).toContain("bg-blue-600");
  });
});
