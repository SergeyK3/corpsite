import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelControlListSubNav from "./PersonnelControlListSubNav";
import { listImportBatches } from "../_lib/importApi.client";

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

vi.mock("../_lib/importApi.client", () => ({
  listImportBatches: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  navigation.pathname = "/directory/personnel/import";
});

describe("PersonnelControlListSubNav", () => {
  it("renders all six preserved routes and marks upload active", async () => {
    vi.mocked(listImportBatches).mockResolvedValue({ items: [{ batch_id: 148 }] } as never);
    render(<PersonnelControlListSubNav />);

    expect(screen.getByRole("navigation", { name: "Разделы контрольного списка" })).toHaveClass(
      "flex-wrap",
    );
    expect(screen.getByRole("link", { name: "Загрузка" })).toHaveAttribute(
      "href",
      "/directory/personnel/import",
    );
    expect(screen.getByRole("link", { name: "Загрузка" })).toHaveAttribute("aria-current", "page");
    await waitFor(() => {
      expect(screen.getByRole("link", { name: "Аналитика" })).toHaveAttribute(
        "href",
        "/directory/personnel/import/148",
      );
    });
    expect(screen.getByRole("link", { name: "Проверка записей" })).toHaveAttribute(
      "href",
      "/directory/personnel/import/review",
    );
    expect(screen.getByRole("link", { name: "Изменения реестра" })).toHaveAttribute(
      "href",
      "/directory/personnel/hr-change-events",
    );
    expect(screen.getByRole("link", { name: "Миграция" })).toHaveAttribute(
      "href",
      "/directory/personnel/migration",
    );
    expect(screen.getByRole("link", { name: "Мед. категории" })).toHaveAttribute(
      "href",
      "/directory/personnel/import/148/review?mode=personnel",
    );
  });

  it.each([
    ["/directory/personnel/import/148/rows", "Аналитика"],
    ["/directory/personnel/import/review", "Проверка записей"],
    ["/directory/personnel/hr-change-events/17", "Изменения реестра"],
    ["/directory/personnel/migration/employment/42", "Миграция"],
    ["/directory/personnel/import/148/review/23", "Мед. категории"],
    ["/directory/personnel/baselines", "Загрузка"],
  ])("marks %s as %s", (pathname, activeTitle) => {
    navigation.pathname = pathname;
    vi.mocked(listImportBatches).mockResolvedValue({ items: [{ batch_id: 148 }] } as never);
    render(<PersonnelControlListSubNav />);
    expect(screen.getByText(activeTitle).closest("a")).toHaveAttribute("aria-current", "page");
  });

  it("renders no wrapper and makes no request on unrelated personnel pages", () => {
    navigation.pathname = "/directory/personnel/reports";
    const { container } = render(<PersonnelControlListSubNav />);
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByRole("navigation", { name: "Разделы контрольного списка" })).not.toBeInTheDocument();
    expect(listImportBatches).not.toHaveBeenCalled();
  });
});
