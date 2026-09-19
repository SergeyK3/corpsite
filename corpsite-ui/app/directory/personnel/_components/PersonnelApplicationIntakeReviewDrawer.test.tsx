import { afterEach, describe, expect, it, vi, beforeEach } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import PersonnelApplicationIntakeReviewDrawer from "./PersonnelApplicationIntakeReviewDrawer";
import * as api from "../_lib/personnelApplicationsApi.client";

const reviewState: api.IntakeReviewState = {
  application_id: 42,
  draft: {
    application_id: 42,
    draft_id: 1,
    payload: {},
    status: "submitted",
    read_only: true,
  },
  sections: [
    {
      section_code: "personal",
      section_label: "Персональные данные",
      status: "accepted",
      rework_comment: null,
      reviewed_by_user_id: 1,
      reviewed_at: "2026-07-17T10:00:00Z",
      is_empty: false,
      payload: { last_name: "Иванов" },
    },
    {
      section_code: "contacts",
      section_label: "Контакты",
      status: "accepted",
      rework_comment: null,
      reviewed_by_user_id: 1,
      reviewed_at: "2026-07-17T10:00:00Z",
      is_empty: false,
      payload: { mobile_phone: "+77001234567" },
    },
    {
      section_code: "education",
      section_label: "Образование",
      status: "accepted",
      rework_comment: null,
      reviewed_by_user_id: 1,
      reviewed_at: "2026-07-17T10:00:00Z",
      is_empty: false,
      payload: [{ institution: "КазНУ" }],
    },
    {
      section_code: "training",
      section_label: "Обучение",
      status: "skipped",
      rework_comment: null,
      reviewed_by_user_id: 1,
      reviewed_at: "2026-07-17T10:00:00Z",
      is_empty: true,
      payload: [],
    },
    {
      section_code: "relatives",
      section_label: "Родственники",
      status: "skipped",
      rework_comment: null,
      reviewed_by_user_id: 1,
      reviewed_at: "2026-07-17T10:00:00Z",
      is_empty: true,
      payload: [],
    },
    {
      section_code: "employment_biography",
      section_label: "Трудовая биография",
      status: "skipped",
      rework_comment: null,
      reviewed_by_user_id: 1,
      reviewed_at: "2026-07-17T10:00:00Z",
      is_empty: true,
      payload: [],
    },
    {
      section_code: "military",
      section_label: "Воинский учёт",
      status: "skipped",
      rework_comment: null,
      reviewed_by_user_id: 1,
      reviewed_at: "2026-07-17T10:00:00Z",
      is_empty: true,
      payload: {},
    },
  ],
  transfer: null,
  can_transfer: true,
  transfer_blocked_reason: null,
};

describe("PersonnelApplicationIntakeReviewDrawer", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listIntakeReconciliationDecisions").mockResolvedValue({
      application_id: 42,
      section_code: "education",
      items: [],
      total: 0,
    });
  });

  it("loads review sections and shows transfer button", async () => {
    vi.spyOn(api, "getIntakeReviewState").mockResolvedValue(reviewState);

    render(
      <PersonnelApplicationIntakeReviewDrawer
        applicationId={42}
        open
        onClose={() => {}}
      />,
    );

    expect(await screen.findByTestId("intake-review-section-personal")).toBeInTheDocument();
    const drawer = screen.getAllByTestId("intake-review-drawer")[0];
    expect(within(drawer).getByTestId("intake-transfer-button")).toHaveTextContent("Перенести в PPR");
  });

  it("calls transfer API and shows audit after success", async () => {
    const completedState: api.IntakeReviewState = {
      ...reviewState,
      can_transfer: false,
      transfer_blocked_reason: "Transfer already completed.",
      transfer: {
        transfer_id: 9,
        application_id: 42,
        status: "completed",
        result: "success",
        transferred_by_user_id: 1,
        transferred_at: "2026-07-17T11:00:00Z",
        sections_transferred: ["general", "education"],
        command_ids: ["intake-transfer:42:general:0"],
        error_message: null,
      },
    };
    const getState = vi.spyOn(api, "getIntakeReviewState").mockResolvedValue(reviewState);
    vi.spyOn(api, "transferIntakeToPpr").mockImplementation(async () => {
      getState.mockResolvedValue(completedState);
      return {
        application_id: 42,
        idempotent_replay: false,
        transfer: completedState.transfer!,
      };
    });

    const onTransferred = vi.fn();
    render(
      <PersonnelApplicationIntakeReviewDrawer
        applicationId={42}
        open
        onClose={() => {}}
        onTransferred={onTransferred}
      />,
    );

    await waitFor(() => {
      expect(screen.getAllByTestId("intake-transfer-button").length).toBeGreaterThan(0);
    });
    fireEvent.click(screen.getAllByTestId("intake-transfer-button")[0]);

    await waitFor(() => {
      expect(api.transferIntakeToPpr).toHaveBeenCalledWith(42);
    });

    const drawer = screen.getAllByTestId("intake-review-drawer")[0];
    expect(await within(drawer).findByText("Журнал переноса")).toBeInTheDocument();
    expect(within(drawer).queryByTestId("intake-transfer-button")).not.toBeInTheDocument();
  });

  it("shows legacy empty military details as not provided while retaining skip and rework actions", async () => {
    vi.spyOn(api, "getIntakeReviewState").mockResolvedValue({
      ...reviewState,
      sections: reviewState.sections.map((section) => section.section_code === "military"
        ? { ...section, status: "pending", payload: { rank: "", category: "", commissariat: "" } }
        : section),
    });
    render(<PersonnelApplicationIntakeReviewDrawer applicationId={42} open onClose={() => {}} />);
    const military = await screen.findByTestId("intake-review-section-military");
    expect(within(military).getByTestId("intake-review-military-not-provided")).toHaveTextContent("Сведения о воинском учёте не предоставлены");
    expect(within(military).getByRole("button", { name: "Пропустить" })).toBeInTheDocument();
    expect(within(military).getByRole("button", { name: "Вернуть на доработку" })).toBeInTheDocument();
  });

  it("renders provided military data using field labels instead of raw JSON", async () => {
    vi.spyOn(api, "getIntakeReviewState").mockResolvedValue({
      ...reviewState,
      sections: reviewState.sections.map((section) => section.section_code === "military"
        ? { ...section, is_empty: false, payload: { status: "registered", rank: "капитан", commissariat: "Астана" } }
        : section),
    });
    render(<PersonnelApplicationIntakeReviewDrawer applicationId={42} open onClose={() => {}} />);
    const military = await screen.findByTestId("intake-review-section-military");
    expect(within(military).getByTestId("intake-review-military-details")).toHaveTextContent("Воинское звание");
    expect(within(military).getByTestId("intake-review-military-details")).toHaveTextContent("капитан");
    expect(within(military).queryByText(/\"rank\"/)).not.toBeInTheDocument();
  });
});
