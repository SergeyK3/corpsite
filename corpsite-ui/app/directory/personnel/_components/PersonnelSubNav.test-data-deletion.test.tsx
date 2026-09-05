import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelSubNav from "./PersonnelSubNav";
import type { MeInfo } from "@/lib/types";

let currentUser: MeInfo | null = null;

vi.mock("@/lib/currentUser", () => ({ useCurrentUser: () => currentUser }));
vi.mock("next/link", () => ({
  default: ({ children, href, className }: {
    children: React.ReactNode;
    href: string;
    className?: string;
  }) => <a href={href} className={className}>{children}</a>,
}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/directory/personnel/test-data-deletion-approvals",
}));

afterEach(cleanup);

describe("PersonnelSubNav test-data deletion approval tab", () => {
  it("shows the active horizontal tab only with approval capability", () => {
    currentUser = { user_id: 2, can_approve_test_personnel_deletion: true };
    render(<PersonnelSubNav />);
    const link = screen.getByRole("link", { name: "Согласование удаления тестовых данных" });
    expect(link).toHaveAttribute("href", "/directory/personnel/test-data-deletion-approvals");
    expect(link.className).toContain("bg-blue-600");
  });

  it("does not expose the horizontal tab without approval capability", () => {
    currentUser = { user_id: 1, can_request_test_personnel_deletion: true };
    render(<PersonnelSubNav />);
    expect(screen.queryByRole("link", { name: "Согласование удаления тестовых данных" }))
      .not.toBeInTheDocument();
  });
});
