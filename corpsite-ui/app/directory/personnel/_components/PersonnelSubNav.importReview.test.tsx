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

const mockSearchParams = new URLSearchParams("mode=declaration");

vi.mock("next/navigation", () => ({
  usePathname: () => "/directory/personnel/import/148/review",
  useSearchParams: () => mockSearchParams,
}));

vi.mock("../_lib/importApi.client", () => ({
  listImportBatches: vi.fn(async () => ({ items: [{ batch_id: 148 }] })),
}));

afterEach(() => {
  cleanup();
});

describe("PersonnelSubNav import review tabs", () => {
  it("keeps active import sections and removes obsolete sections", async () => {
    render(<PersonnelSubNav />);

    expect(await screen.findByRole("link", { name: "Импорт" })).toHaveAttribute(
      "href",
      "/directory/personnel/import",
    );
    expect(screen.queryByRole("link", { name: "Baseline" })).not.toBeInTheDocument();

    const medicalLink = screen.getByRole("link", { name: "Мед. категории" });
    expect(medicalLink).toHaveAttribute("href", "/directory/personnel/import/148/review?mode=personnel");
    expect(medicalLink.className).toContain("bg-blue-600");
    expect(screen.queryByRole("link", { name: "Декларации" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Технические" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Обучение" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Аналитика" })).toBeInTheDocument();
    expect(screen.queryByTestId("import-review-mode-tabs")).not.toBeInTheDocument();
  });
});
