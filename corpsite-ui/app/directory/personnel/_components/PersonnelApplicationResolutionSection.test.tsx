import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import PersonnelApplicationResolutionSection from "./PersonnelApplicationResolutionSection";
import * as api from "../_lib/personnelApplicationsApi.client";

const baseDetail: api.PersonnelApplicationDetail = {
  application_id: 55,
  person_id: 9,
  status: "review_completed",
  application_received_at: "2026-07-17",
  application_source: "paper",
  vacancy_check_status: "confirmed_visually",
  intended_org_unit_id: 1,
  intended_position_id: 2,
  intended_employment_rate: 1,
  registered_at: "2026-07-17T10:00:00Z",
  registered_by_user_id: 1,
  created_at: "2026-07-17T10:00:00Z",
  updated_at: "2026-07-17T10:00:00Z",
};

describe("PersonnelApplicationResolutionSection", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "getDirectorResolutionAudit").mockResolvedValue([]);
  });

  it("opens resolution from review_completed", async () => {
    vi.spyOn(api, "openDirectorResolution").mockResolvedValue({});
    const onRefresh = vi.fn();

    render(<PersonnelApplicationResolutionSection detail={baseDetail} onRefresh={onRefresh} />);

    fireEvent.click(screen.getByTestId("resolution-open-button"));

    await waitFor(() => {
      expect(api.openDirectorResolution).toHaveBeenCalledWith(55);
      expect(onRefresh).toHaveBeenCalled();
    });
  });

  it("records rejected resolution with required comment", async () => {
    vi.spyOn(api, "recordDirectorResolution").mockResolvedValue({});
    const onRefresh = vi.fn();

    render(
      <PersonnelApplicationResolutionSection
        detail={{ ...baseDetail, status: "resolution_pending" }}
        onRefresh={onRefresh}
      />,
    );

    fireEvent.click(screen.getByTestId("resolution-record-rejected"));
    fireEvent.change(screen.getByTestId("resolution-comment-input"), {
      target: { value: "Не подходит" },
    });
    fireEvent.click(screen.getByTestId("resolution-confirm-button"));

    await waitFor(() => {
      expect(api.recordDirectorResolution).toHaveBeenCalledWith(55, "rejected", "Не подходит");
      expect(onRefresh).toHaveBeenCalled();
    });
  });

  it("creates hire order draft after approval", async () => {
    vi.spyOn(api, "createHireOrderDraft").mockResolvedValue({
      application_id: 55,
      personnel_order_id: 901,
      idempotent_replay: false,
      application_status: "order_draft_created",
    });
    const onRefresh = vi.fn();

    render(
      <PersonnelApplicationResolutionSection
        detail={{ ...baseDetail, status: "approved" }}
        onRefresh={onRefresh}
      />,
    );

    fireEvent.click(screen.getByTestId("hire-order-draft-button"));

    await waitFor(() => {
      expect(api.createHireOrderDraft).toHaveBeenCalledWith(55);
      expect(onRefresh).toHaveBeenCalled();
    });
  });
});
