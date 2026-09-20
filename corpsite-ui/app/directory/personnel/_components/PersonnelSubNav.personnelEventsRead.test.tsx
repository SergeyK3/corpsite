import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelSubNav from "./PersonnelSubNav";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>,
}));
vi.mock("next/navigation", () => ({ usePathname: () => "/directory/personnel/journal" }));
vi.mock("@/lib/currentUser", () => ({
  useCurrentUser: () => ({
    has_personnel_events_read: true,
    has_personnel_admin: false,
    has_personnel_visibility: false,
  }),
}));

afterEach(cleanup);

describe("PersonnelSubNav narrow personnel events reader", () => {
  it("shows the journal without exposing adjacent HR process sections", () => {
    render(<PersonnelSubNav />);
    expect(screen.getByRole("link", { name: "Кадровый журнал" })).toHaveAttribute("href", "/directory/personnel/journal");
    expect(screen.queryByRole("link", { name: "Личные карточки" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Контрольный список" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Приказы" })).not.toBeInTheDocument();
  });
});
