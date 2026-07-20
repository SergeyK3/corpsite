import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ApplicantIntakeLinkTableCell from "./ApplicantIntakeLinkTableCell";
import * as workflow from "../_lib/personnelApplicantWorkflow";

describe("ApplicantIntakeLinkTableCell", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("shows dash when link was not issued", () => {
    render(
      <ApplicantIntakeLinkTableCell
        applicationId={10}
        displayState="not_issued"
        intakeUrlPath={null}
      />,
    );
    expect(screen.getByTestId("applicant-intake-link-empty-10")).toHaveTextContent("—");
  });

  it("shows reissue hint for legacy hash-only links", () => {
    render(
      <ApplicantIntakeLinkTableCell
        applicationId={10}
        displayState="reissue_required"
        intakeUrlPath={null}
      />,
    );
    expect(screen.getByTestId("applicant-intake-link-status-10")).toHaveTextContent("Требует перевыпуска");
  });

  it("shows compact url with copy and open actions for active server link", () => {
    vi.spyOn(workflow, "buildIntakePublicUrl").mockReturnValue("http://localhost/intake/abc123");
    vi.spyOn(workflow, "formatApplicantIntakeUrlDisplay").mockReturnValue("http://localhost/intake/abc123");
    vi.spyOn(workflow, "copyTextToClipboard").mockResolvedValue(true);

    render(
      <ApplicantIntakeLinkTableCell
        applicationId={10}
        displayState="active"
        intakeUrlPath="/intake/abc123"
      />,
    );

    expect(screen.getByTestId("applicant-intake-link-url-10")).toHaveTextContent(
      "http://localhost/intake/abc123",
    );
    expect(screen.getByTestId("applicant-intake-link-copy-10")).toBeInTheDocument();
    expect(screen.getByTestId("applicant-intake-link-open-10")).toBeInTheDocument();
  });

  it("copies full public url", async () => {
    vi.spyOn(workflow, "buildIntakePublicUrl").mockReturnValue("http://localhost/intake/abc123");
    vi.spyOn(workflow, "formatApplicantIntakeUrlDisplay").mockReturnValue("http://localhost/intake/abc123");
    vi.spyOn(workflow, "copyTextToClipboard").mockResolvedValue(true);

    render(
      <ApplicantIntakeLinkTableCell
        applicationId={10}
        displayState="active"
        intakeUrlPath="/intake/abc123"
      />,
    );
    fireEvent.click(screen.getByTestId("applicant-intake-link-copy-10"));

    expect(workflow.copyTextToClipboard).toHaveBeenCalledWith("http://localhost/intake/abc123");
    expect(await screen.findByText("Скопировано")).toBeInTheDocument();
  });
});
