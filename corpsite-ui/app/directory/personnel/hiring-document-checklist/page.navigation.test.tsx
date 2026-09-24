import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PersonnelLayout from "../layout";
import HiringDocumentChecklistPage from "./page";
import type { MeInfo } from "@/lib/types";

let currentUser: MeInfo | null = null;

vi.mock("next/navigation", () => ({
  usePathname: () => "/directory/personnel/hiring-document-checklist",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/currentUser", () => ({ useCurrentUser: () => currentUser }));
vi.mock("../_lib/hiringDocumentChecklistApi.client", () => ({
  getHiringDocumentChecklist: vi.fn().mockResolvedValue({
    title: "Краткий перечень документов при приёме на работу",
    items: ["Документ"],
    note: "Примечание",
    show_additional_notes: false,
    additional_notes_lines: 1,
    can_edit: false,
  }),
  updateHiringDocumentChecklist: vi.fn(),
}));

beforeEach(() => {
  currentUser = { user_id: 8, has_personnel_admin: true };
});

afterEach(cleanup);

describe("hiring document checklist navigation", () => {
  it("marks Miscellaneous and its checklist section active, and renders the new page title", async () => {
    render(
      <PersonnelLayout>
        <HiringDocumentChecklistPage />
      </PersonnelLayout>,
    );

    const miscellaneous = screen.getByRole("link", { name: "Разное" });
    expect(miscellaneous).toHaveAttribute("href", "/directory/personnel/hiring-document-checklist");
    expect(miscellaneous).toHaveAttribute("aria-current", "page");

    const checklist = screen.getByRole("link", { name: "Перечень документов при приеме на работу" });
    expect(checklist).toHaveAttribute("href", "/directory/personnel/hiring-document-checklist");
    expect(checklist).toHaveAttribute("aria-current", "page");
    expect(await screen.findByRole("heading", { name: "Перечень документов при приеме на работу" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Краткий перечень документов при приёме на работу" })).not.toBeInTheDocument();
  });
});
