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
  it("renders import tab label and review mode tabs before Обучение", async () => {
    render(<PersonnelSubNav />);

    expect(await screen.findByRole("link", { name: "Импорт" })).toHaveAttribute(
      "href",
      "/directory/personnel/import",
    );
    expect(screen.queryByRole("link", { name: "Baseline" })).not.toBeInTheDocument();

    const medicalLink = screen.getByRole("link", { name: "Мед. категории" });
    const declarationsLink = screen.getByRole("link", { name: "Декларации" });
    const technicalLink = screen.getByRole("link", { name: "Технические" });
    const trainingLink = screen.getByRole("link", { name: "Обучение" });

    expect(medicalLink).toHaveAttribute("href", "/directory/personnel/import/148/review?mode=personnel");
    expect(declarationsLink).toHaveAttribute(
      "href",
      "/directory/personnel/import/148/review?mode=declaration",
    );
    expect(technicalLink).toHaveAttribute("href", "/directory/personnel/import/148/review?mode=technical");
    expect(trainingLink).toHaveAttribute("href", "/directory/personnel/import/148/training");

    expect(declarationsLink.className).toContain("bg-blue-600");
    expect(medicalLink.className).not.toContain("bg-blue-600");
    expect(screen.queryByTestId("import-review-mode-tabs")).not.toBeInTheDocument();
  });
});
