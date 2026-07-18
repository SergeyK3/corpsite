import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PprCardApplicationsSection from "./PprCardApplicationsSection";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const getPersonApplicationsHistoryMock = vi.fn();

vi.mock("../_lib/personnelApplicationsApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelApplicationsApi.client")>(
    "../_lib/personnelApplicationsApi.client",
  );
  return {
    ...actual,
    getPersonApplicationsHistory: (...args: unknown[]) => getPersonApplicationsHistoryMock(...args),
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PprCardApplicationsSection", () => {
  it("loads and renders application history with open links", async () => {
    getPersonApplicationsHistoryMock.mockResolvedValue({
      person_id: 5,
      items: [
        {
          application_id: 10,
          person_id: 5,
          status: "registered",
          application_received_at: "2026-07-01",
          intended_org_unit_name: "Терапия",
          intended_position_name: "Медсестра",
          registered_at: "2026-07-02T10:00:00Z",
          registered_by_user_id: 7,
          registered_by_name: "HR User",
          application_source: "paper",
          vacancy_check_status: "confirmed_visually",
          created_at: "2026-07-02T10:00:00Z",
          updated_at: "2026-07-02T10:00:00Z",
        },
      ],
    });

    render(<PprCardApplicationsSection personId={5} />);

    await waitFor(() => {
      expect(screen.getByTestId("ppr-applications-section")).toBeInTheDocument();
    });

    expect(screen.getByTestId("ppr-application-row-10")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть" })).toHaveAttribute(
      "href",
      "/directory/personnel/applicants?application_id=10",
    );
  });

  it("shows empty state when no applications exist", async () => {
    getPersonApplicationsHistoryMock.mockResolvedValue({ person_id: 5, items: [] });

    render(<PprCardApplicationsSection personId={5} />);

    await waitFor(() => {
      expect(screen.getByTestId("ppr-applications-section-empty")).toBeInTheDocument();
    });
  });
});
