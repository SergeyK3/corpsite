import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import PersonnelApplicationIntakeSection from "./PersonnelApplicationIntakeSection";
import * as api from "../_lib/personnelApplicationsApi.client";
import * as workflow from "../_lib/personnelApplicantWorkflow";

const baseDetail: api.PersonnelApplicationDetail = {
  application_id: 42,
  person_id: 7,
  status: "intake_pending",
  application_received_at: "2026-07-17",
  application_source: "paper",
  vacancy_check_status: "confirmed_visually",
  registered_at: "2026-07-17T10:00:00Z",
  registered_by_user_id: 1,
  created_at: "2026-07-17T10:00:00Z",
  updated_at: "2026-07-17T10:00:00Z",
};

beforeEach(() => {
  vi.spyOn(workflow, "readPersistedIntakeLinkPath").mockReturnValue(null);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("PersonnelApplicationIntakeSection", () => {
  it("issues intake link", async () => {
    vi.spyOn(api, "issueIntakeLink").mockResolvedValue({
      application_id: 42,
      link_id: 1,
      intake_url_path: "/intake/abc123",
      expires_at: "2026-08-01T00:00:00Z",
      status: "issued",
      reissued: false,
    });

    render(
      <PersonnelApplicationIntakeSection detail={baseDetail} onRefresh={() => {}} />,
    );

    fireEvent.click(screen.getByTestId("intake-issue-link-button"));

    expect(api.issueIntakeLink).toHaveBeenCalledWith(42);
    expect(await screen.findByText(/\/intake\/abc123/)).toBeInTheDocument();
  });

  it("shows on-behalf edit button for intake pending editable draft", () => {
    const onOpenOnBehalfEdit = vi.fn();
    render(
      <PersonnelApplicationIntakeSection
        detail={{
          ...baseDetail,
          status: "intake_pending",
          intake_link_status: "opened",
          intake_draft_status: "editable",
        }}
        onRefresh={() => {}}
        onOpenOnBehalfEdit={onOpenOnBehalfEdit}
      />,
    );

    const button = screen.getByTestId("intake-on-behalf-edit-button");
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(onOpenOnBehalfEdit).toHaveBeenCalledWith(42);
  });

  it("shows open review button when submitted", () => {
    const onOpenReview = vi.fn();
    render(
      <PersonnelApplicationIntakeSection
        detail={{
          ...baseDetail,
          status: "intake_submitted",
          intake_link_status: "submitted",
          intake_draft_status: "submitted",
        }}
        onRefresh={() => {}}
        onOpenReview={onOpenReview}
      />,
    );

    fireEvent.click(screen.getByTestId("intake-open-review-button"));
    expect(onOpenReview).toHaveBeenCalledWith(42);
  });

  it("copies issued intake link", async () => {
    vi.spyOn(api, "issueIntakeLink").mockResolvedValue({
      application_id: 42,
      link_id: 1,
      intake_url_path: "/intake/abc123",
      expires_at: "2026-08-01T00:00:00Z",
      status: "issued",
      reissued: false,
    });
    vi.spyOn(workflow, "copyTextToClipboard").mockResolvedValue(true);

    render(
      <PersonnelApplicationIntakeSection detail={baseDetail} onRefresh={() => {}} />,
    );

    fireEvent.click(screen.getByTestId("intake-issue-link-button"));
    expect(await screen.findByText(/\/intake\/abc123/)).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("intake-copy-link-button"));
    expect(workflow.copyTextToClipboard).toHaveBeenCalled();
    expect(await screen.findByTestId("intake-copy-notice")).toHaveTextContent("Ссылка скопирована");
  });
});
