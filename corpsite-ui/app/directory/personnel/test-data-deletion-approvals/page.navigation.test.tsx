import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PersonnelLayout from "../layout";
import TestPersonnelDeletionApprovalsPage from "./page";
import type { MeInfo } from "@/lib/types";

let currentUser: MeInfo | null = null;

vi.mock("next/navigation", () => ({
  usePathname: () => "/directory/personnel/test-data-deletion-approvals",
}));
vi.mock("@/lib/currentUser", () => ({ useCurrentUser: () => currentUser }));
vi.mock("@/lib/testPersonnelDeletion", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/testPersonnelDeletion")>();
  return {
    ...actual,
    listTestPersonnelDeletionApprovals: vi.fn().mockResolvedValue([]),
  };
});

beforeEach(() => {
  currentUser = { user_id: 8, can_approve_test_personnel_deletion: true };
});

afterEach(cleanup);

describe("test-personnel approvals page navigation", () => {
  it("renders exactly one horizontal PersonnelSubNav in the full page tree", () => {
    render(
      <PersonnelLayout>
        <TestPersonnelDeletionApprovalsPage />
      </PersonnelLayout>,
    );

    expect(screen.getAllByRole("navigation", { name: "Навигация кадровых процессов" })).toHaveLength(1);
    expect(screen.getAllByRole("link", { name: "Согласование удаления тестовых данных" })).toHaveLength(1);
  });

  it("does not put the ADMIN test-data management link into Кадровые процессы", () => {
    currentUser = { user_id: 25, role_id: 2, can_request_test_personnel_deletion: true };

    render(
      <PersonnelLayout>
        <div>Кадровая страница</div>
      </PersonnelLayout>,
    );

    expect(screen.queryAllByRole("link", { name: /Управление тестовыми данными персонала/ })).toHaveLength(0);
  });
});
