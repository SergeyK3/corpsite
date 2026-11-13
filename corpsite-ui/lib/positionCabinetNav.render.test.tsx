import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";

import PositionCabinetNav from "@/components/PositionCabinetNav";

vi.mock("next/navigation", () => ({ usePathname: () => "/tasks" }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: ComponentProps<"a">) => <a href={href} {...props}>{children}</a>,
}));

describe("employee cabinet entry", () => {
  it("keeps tasks active and links to the existing card and personnel orders", () => {
    render(<PositionCabinetNav />);
    expect(screen.getByRole("tab", { name: "Мои задачи" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Личная карточка" })).toHaveAttribute("href", "/profile/personal-card");
    expect(screen.getByRole("tab", { name: "Кадровые приказы" })).toHaveAttribute("href", "/profile/orders");
  });
});
