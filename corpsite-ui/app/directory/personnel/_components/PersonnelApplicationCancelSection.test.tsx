import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelApplicationCancelSection from "./PersonnelApplicationCancelSection";
import type { PersonnelApplicationDetail } from "../_lib/personnelApplicationsApi.client";

const cancelPersonnelApplicationMock = vi.fn();

vi.mock("../_lib/personnelApplicationsApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelApplicationsApi.client")>(
    "../_lib/personnelApplicationsApi.client",
  );
  return {
    ...actual,
    cancelPersonnelApplication: (...args: unknown[]) => cancelPersonnelApplicationMock(...args),
  };
});

const activeDetail: PersonnelApplicationDetail = {
  application_id: 10,
  person_id: 5,
  status: "registered",
  application_received_at: "2026-07-01",
  application_source: "paper",
  vacancy_check_status: "confirmed_visually",
  registered_at: "2026-07-02T10:00:00Z",
  registered_by_user_id: 7,
  created_at: "2026-07-02T10:00:00Z",
  updated_at: "2026-07-02T10:00:00Z",
  is_read_only: false,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelApplicationCancelSection", () => {
  it("submits cancel with reason", async () => {
    cancelPersonnelApplicationMock.mockResolvedValue({
      application_id: 10,
      status: "cancelled",
      closed_at: "2026-07-03T10:00:00Z",
      audit: { action: "cancelled" },
    });
    const onCancelled = vi.fn();

    render(<PersonnelApplicationCancelSection detail={activeDetail} onCancelled={onCancelled} />);

    fireEvent.click(screen.getByTestId("personnel-application-cancel-open"));
    fireEvent.change(screen.getByTestId("personnel-application-cancel-reason"), {
      target: { value: "Претендент отказался" },
    });
    fireEvent.click(screen.getByTestId("personnel-application-cancel-submit"));

    await waitFor(() => {
      expect(cancelPersonnelApplicationMock).toHaveBeenCalledWith(10, "Претендент отказался");
    });
    expect(onCancelled).toHaveBeenCalled();
  });

  it("hides cancel for read-only archive detail", () => {
    render(
      <PersonnelApplicationCancelSection
        detail={{ ...activeDetail, status: "cancelled", is_read_only: true }}
        onCancelled={vi.fn()}
      />,
    );

    expect(screen.queryByTestId("personnel-application-cancel-section")).not.toBeInTheDocument();
  });
});
