import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PersonnelApplicationIntakeOnBehalfDrawer from "./PersonnelApplicationIntakeOnBehalfDrawer";
import * as api from "../_lib/personnelApplicationsApi.client";
import { toApiError } from "@/lib/api";
import type { IntakeDraftPayload } from "@/app/intake/_lib/intakeApi.client";

vi.mock("../_lib/personnelApplicationsApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelApplicationsApi.client")>(
    "../_lib/personnelApplicationsApi.client",
  );
  return {
    ...actual,
    getIntakeOnBehalfEditSession: vi.fn(),
    saveIntakeOnBehalfDraft: vi.fn(),
    submitIntakeOnBehalfDraft: vi.fn(),
  };
});

const getIntakeOnBehalfEditSessionMock = vi.mocked(api.getIntakeOnBehalfEditSession);
const saveIntakeOnBehalfDraftMock = vi.mocked(api.saveIntakeOnBehalfDraft);
const submitIntakeOnBehalfDraftMock = vi.mocked(api.submitIntakeOnBehalfDraft);

function buildSessionPayload(): IntakeDraftPayload {
  return {
    personal: {
      last_name: "Иванов",
      first_name: "Иван",
      middle_name: "",
      birth_date: "1990-01-01",
      birth_place: "",
      gender: "",
      citizenship: "Республика Казахстан",
      nationality: "казах",
      personnel_number: "",
    },
    contacts: {
      mobile_phone: "+77001234567",
      email: "ivan@example.com",
      registration_address: "",
      residence_address: "",
    },
    education: [
      {
        education_type: "basic",
        institution: "КазНУ",
        year_from: "2018-09-01",
        year_to: "2022-06-30",
        specialty: "IT",
        qualification: "Бакалавр",
        diploma_number: "123",
      },
    ],
    training: [],
    relatives: [],
    employment_biography: [
      {
        organization: "Клиника А",
        position: "Медсестра",
        year_from: "2020-01-15",
        year_to: "2024-08-01",
        reason_for_leaving: "Переезд",
      },
    ],
    military: {
      status: "",
      rank: "",
      category: "",
      composition: "",
      specialty_code: "",
      specialty_name: "",
      fitness_category: "",
      commissariat: "",
      registration_group: "",
      registration_category: "",
    },
    additional: {
      foreign_languages: [],
      foreign_languages_none: false,
      awards: [],
      awards_none: false,
      academic_degrees: [],
      academic_degrees_none: false,
      academic_titles: [],
      academic_titles_none: false,
    },
    current_step: "review",
  };
}

function mockEditableSession(updatedAt = "2026-07-23T09:00:00Z", draftStatus = "editable") {
  getIntakeOnBehalfEditSessionMock.mockResolvedValue({
    application_id: 42,
    application_status: draftStatus === "editable" ? "intake_pending" : "intake_submitted",
    editable: draftStatus === "editable",
    blocked_reason: null,
    reason_code: null,
    draft: {
      application_id: 42,
      draft_id: 7,
      link_id: 3,
      status: draftStatus,
      read_only: draftStatus !== "editable",
      link_status: draftStatus === "editable" ? "opened" : "submitted",
      updated_at: updatedAt,
      submitted_at: draftStatus === "editable" ? null : "2026-07-23T10:00:00Z",
      payload: buildSessionPayload(),
    },
  });
}

function mockSubmittedViewSession(updatedAt = "2026-07-23T10:00:00Z") {
  getIntakeOnBehalfEditSessionMock.mockResolvedValue({
    application_id: 42,
    application_status: "intake_submitted",
    editable: false,
    blocked_reason: null,
    reason_code: null,
    draft: {
      application_id: 42,
      draft_id: 7,
      link_id: 3,
      status: "submitted",
      read_only: true,
      link_status: "submitted",
      updated_at: updatedAt,
      submitted_at: "2026-07-23T10:00:00Z",
      payload: buildSessionPayload(),
    },
  });
}

function mockFirstFillSession(updatedAt = "2026-07-23T09:00:00Z") {
  mockEditableSession(updatedAt, "editable");
}

function drawerScope() {
  return within(screen.getByTestId("intake-on-behalf-drawer"));
}

function expandEmploymentRow(index = 0) {
  const desktop = within(screen.getByTestId("intake-on-behalf-drawer")).getByTestId(
    "intake-employment-desktop-view",
  );
  fireEvent.click(within(desktop).getByTestId(`intake-employment-actions-${index}`));
  fireEvent.click(within(desktop).getByTestId(`intake-employment-row-edit-${index}`));
}

async function openReviewStep() {
  await waitFor(() => {
    expect(screen.queryByTestId("intake-on-behalf-loading")).not.toBeInTheDocument();
  });
  fireEvent.click(drawerScope().getByTestId("intake-nav-end"));
  await waitFor(() => {
    expect(screen.getByTestId("intake-review-summary")).toBeInTheDocument();
  });
}

function formButton(name: RegExp) {
  return drawerScope().getByRole("button", { name });
}

async function openPersonalStep() {
  await waitFor(() => {
    expect(screen.queryByTestId("intake-on-behalf-loading")).not.toBeInTheDocument();
    expect(screen.getByTestId("intake-citizenship")).toBeInTheDocument();
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("PersonnelApplicationIntakeOnBehalfDrawer", () => {
  it("shows citizenship and nationality dropdowns on personal step in on-behalf mode", async () => {
    mockEditableSession();

    render(
      <PersonnelApplicationIntakeOnBehalfDrawer
        applicationId={42}
        open
        onClose={vi.fn()}
      />,
    );

    await openPersonalStep();

    expect(screen.getByTestId("intake-citizenship-chevron")).toHaveTextContent("▼");
    expect(screen.getByTestId("intake-nationality-chevron")).toHaveTextContent("▼");

    fireEvent.click(screen.getByTestId("intake-citizenship"));
    const citizenshipOptions = screen.getAllByRole("option").map((node) => node.textContent);
    expect(citizenshipOptions).toContain("Россия");
    expect(citizenshipOptions.length).toBeGreaterThanOrEqual(10);
    expect(screen.getByTestId("intake-citizenship")).toHaveValue("Республика Казахстан");

    fireEvent.click(screen.getByTestId("intake-nationality"));
    expect(screen.getByTestId("intake-nationality-option-0")).toHaveTextContent("казахи");
  });

  it("opens on personal step with all sections available, not review summary", async () => {
    mockEditableSession();

    render(
      <PersonnelApplicationIntakeOnBehalfDrawer
        applicationId={42}
        open
        onClose={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.queryByTestId("intake-on-behalf-loading")).not.toBeInTheDocument();
    });

    expect(screen.queryByTestId("intake-review-summary")).not.toBeInTheDocument();
    expect(screen.queryByText(/шаг 9 из 9/i)).not.toBeInTheDocument();
    expect(screen.getByText(/шаг 1 из 9/i)).toBeInTheDocument();
    expect(screen.getByTestId("intake-citizenship")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /далее/i })).toBeInTheDocument();
    expect(screen.queryByTestId("intake-on-behalf-save-button")).not.toBeInTheDocument();
  });

  it("navigates through all nine intake steps in on-behalf mode", async () => {
    mockEditableSession();

    render(
      <PersonnelApplicationIntakeOnBehalfDrawer
        applicationId={42}
        open
        onClose={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.queryByTestId("intake-on-behalf-loading")).not.toBeInTheDocument();
    });

    expect(screen.getByText(/шаг 1 из 9/i)).toBeInTheDocument();

    for (let step = 1; step < 9; step += 1) {
      fireEvent.click(drawerScope().getByTestId("intake-nav-next"));
      await waitFor(() => {
        expect(screen.getByText(new RegExp(`шаг ${step + 1} из 9`, "i"))).toBeInTheDocument();
      });
    }

    expect(screen.getByTestId("intake-review-summary")).toBeInTheDocument();
  });

  it("shows saved button state after successful PATCH", async () => {
    mockEditableSession();
    saveIntakeOnBehalfDraftMock.mockResolvedValue({
      application_id: 42,
      draft_id: 7,
      status: "submitted",
      saved_at: "2026-07-23T10:00:00Z",
      draft_updated_at: "2026-07-23T10:00:00Z",
      changed_fields: ["employment_biography[0].organization", "military.status"],
    });

    render(
      <PersonnelApplicationIntakeOnBehalfDrawer
        applicationId={42}
        open
        onClose={vi.fn()}
      />,
    );

    await openReviewStep();

    const saveButton = screen.getByTestId("intake-on-behalf-save-button");
    expect(saveButton).toHaveTextContent("Сохранить от имени претендента");
    expect(screen.getByTestId("intake-on-behalf-submit-button")).toHaveTextContent("Отправить анкету");
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(saveIntakeOnBehalfDraftMock).toHaveBeenCalledTimes(1);
      expect(saveIntakeOnBehalfDraftMock).toHaveBeenCalledWith(
        42,
        expect.any(Object),
        "2026-07-23T09:00:00Z",
      );
    });

    expect(saveButton).toHaveTextContent("Данные сохранены");
    expect(saveButton).toBeDisabled();
    expect(screen.queryByTestId("intake-on-behalf-save-error")).not.toBeInTheDocument();
  });

  it("reactivates save button after post-save edits", async () => {
    mockEditableSession();
    saveIntakeOnBehalfDraftMock.mockResolvedValue({
      application_id: 42,
      draft_id: 7,
      status: "submitted",
      saved_at: "2026-07-23T10:00:00Z",
      draft_updated_at: "2026-07-23T10:00:00Z",
      changed_fields: ["employment_biography[0].organization"],
    });

    render(
      <PersonnelApplicationIntakeOnBehalfDrawer
        applicationId={42}
        open
        onClose={vi.fn()}
      />,
    );

    await openReviewStep();
    fireEvent.click(screen.getByTestId("intake-on-behalf-save-button"));

    await waitFor(() => {
      expect(screen.getByTestId("intake-on-behalf-save-button")).toHaveTextContent("Данные сохранены");
    });

    fireEvent.click(formButton(/назад/i));
    fireEvent.click(formButton(/назад/i));
    fireEvent.click(formButton(/назад/i));
    expandEmploymentRow(0);
    const organizationInput = within(
      within(screen.getByTestId("intake-on-behalf-drawer")).getByTestId("intake-employment-desktop-view"),
    ).getByTestId("intake-employment-organization-0");
    fireEvent.change(organizationInput, { target: { value: "Клиника Б" } });

    fireEvent.click(formButton(/далее/i));
    fireEvent.click(formButton(/далее/i));
    fireEvent.click(formButton(/далее/i));

    const saveButton = screen.getByTestId("intake-on-behalf-save-button");
    expect(saveButton).toHaveTextContent("Сохранить от имени претендента");
    expect(saveButton).toBeEnabled();
    expect(screen.getByTestId("intake-on-behalf-review-notice")).toHaveTextContent(
      /несохранённые изменения/i,
    );
  });

  it("blocks on-behalf save on review when legacy year-only dates remain", async () => {
    getIntakeOnBehalfEditSessionMock.mockResolvedValue({
      application_id: 42,
      application_status: "intake_pending",
      editable: true,
      blocked_reason: null,
      reason_code: null,
      draft: {
        application_id: 42,
        draft_id: 7,
        link_id: 3,
        status: "editable",
        read_only: false,
        link_status: "opened",
        updated_at: "2026-07-23T09:00:00Z",
        submitted_at: null,
        payload: {
          ...buildSessionPayload(),
          education: [
            {
              ...buildSessionPayload().education[0],
              year_from: "2018",
              year_to: "2022-06-30",
            },
          ],
        },
      },
    });

    render(
      <PersonnelApplicationIntakeOnBehalfDrawer
        applicationId={42}
        open
        onClose={vi.fn()}
      />,
    );

    await openReviewStep();

    const saveButton = screen.getByTestId("intake-on-behalf-save-button");
    expect(saveButton).toBeDisabled();
    expect(screen.getByTestId("intake-review-date-issues")).toBeInTheDocument();
  });

  it("shows PATCH error without saved button state", async () => {
    mockEditableSession();
    saveIntakeOnBehalfDraftMock.mockRejectedValue(new Error("save failed"));

    render(
      <PersonnelApplicationIntakeOnBehalfDrawer
        applicationId={42}
        open
        onClose={vi.fn()}
      />,
    );

    await openReviewStep();
    fireEvent.click(screen.getByTestId("intake-on-behalf-save-button"));

    await waitFor(() => {
      expect(screen.getByTestId("intake-on-behalf-save-error")).toBeInTheDocument();
    });

    const saveButton = screen.getByTestId("intake-on-behalf-save-button");
    expect(saveButton).toHaveTextContent("Сохранить от имени претендента");
    expect(saveButton).toBeEnabled();
  });

  it("shows version conflict when stale expected_updated_at is rejected", async () => {
    mockEditableSession();
    saveIntakeOnBehalfDraftMock.mockRejectedValue({
      status: 409,
      details: {
        detail: {
          code: "DRAFT_VERSION_CONFLICT",
          message: "Intake draft was changed by another session.",
        },
      },
    });

    render(
      <PersonnelApplicationIntakeOnBehalfDrawer
        applicationId={42}
        open
        onClose={vi.fn()}
      />,
    );

    await openReviewStep();
    fireEvent.click(screen.getByTestId("intake-on-behalf-save-button"));

    await waitFor(() => {
      expect(screen.getByTestId("intake-on-behalf-save-error")).toHaveTextContent(/другой вкладке/i);
    });
    expect(saveIntakeOnBehalfDraftMock).toHaveBeenCalledWith(
      42,
      expect.any(Object),
      "2026-07-23T09:00:00Z",
    );
    expect(screen.getByTestId("intake-on-behalf-save-button")).toHaveTextContent(
      "Сохранить от имени претендента",
    );
  });

  it("shows save and submit buttons on review for editable first-fill draft", async () => {
    mockFirstFillSession();

    render(
      <PersonnelApplicationIntakeOnBehalfDrawer
        applicationId={42}
        open
        onClose={vi.fn()}
      />,
    );

    await openReviewStep();

    expect(screen.getByTestId("intake-on-behalf-save-button")).toHaveTextContent(
      "Сохранить от имени претендента",
    );
    expect(screen.getByTestId("intake-on-behalf-submit-button")).toHaveTextContent("Отправить анкету");
  });

  it("submits editable draft and keeps submitted state in drawer after success", async () => {
    mockFirstFillSession();
    submitIntakeOnBehalfDraftMock.mockResolvedValue({
      application_id: 178,
      draft_id: 7,
      status: "submitted",
      submitted_at: "2026-07-24T15:50:18.458411Z",
      draft_updated_at: "2026-07-24T15:50:18.458411Z",
    });
    const onClose = vi.fn();
    const onSaved = vi.fn();

    render(
      <PersonnelApplicationIntakeOnBehalfDrawer
        applicationId={42}
        open
        onClose={onClose}
        onSaved={onSaved}
      />,
    );

    await openReviewStep();
    fireEvent.click(screen.getByTestId("intake-on-behalf-submit-button"));

    await waitFor(() => {
      expect(submitIntakeOnBehalfDraftMock).toHaveBeenCalledWith(
        42,
        expect.any(Object),
        "2026-07-23T09:00:00Z",
      );
      expect(onSaved).toHaveBeenCalled();
      expect(screen.getByTestId("intake-on-behalf-submit-button")).toHaveTextContent(
        "Анкета отправлена",
      );
      expect(screen.getByTestId("intake-on-behalf-submit-button")).toBeDisabled();
      expect(screen.getByTestId("intake-on-behalf-submitted-notice")).toBeInTheDocument();
    });
    expect(onClose).not.toHaveBeenCalled();
    expect(saveIntakeOnBehalfDraftMock).not.toHaveBeenCalled();
  });

  it("keeps drawer open when submit fails", async () => {
    mockFirstFillSession();
    submitIntakeOnBehalfDraftMock.mockRejectedValue(new Error("submit failed"));
    const onClose = vi.fn();

    render(
      <PersonnelApplicationIntakeOnBehalfDrawer
        applicationId={42}
        open
        onClose={onClose}
      />,
    );

    await openReviewStep();
    fireEvent.click(screen.getByTestId("intake-on-behalf-submit-button"));

    expect(await screen.findByTestId("intake-on-behalf-save-error")).toHaveTextContent(
      "submit failed",
    );
    expect(await screen.findByTestId("intake-on-behalf-submit-error")).toHaveTextContent(
      "submit failed",
    );
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByTestId("intake-on-behalf-submit-button")).toHaveTextContent("Отправить анкету");
    expect(screen.getByTestId("intake-on-behalf-submit-button")).toBeEnabled();
    expect(screen.getByTestId("intake-on-behalf-drawer")).toBeInTheDocument();
  });

  it("shows structured 422 submit error next to the submit button", async () => {
    mockFirstFillSession();
    submitIntakeOnBehalfDraftMock.mockRejectedValue(
      toApiError(422, {
        detail: {
          code: "VALIDATION_FAILED",
          message:
            "Intake dates must be full day precision (ДД.ММ.ГГГГ): training[2].year_from, training[2].year_to",
        },
      }),
    );

    render(
      <PersonnelApplicationIntakeOnBehalfDrawer
        applicationId={178}
        open
        onClose={vi.fn()}
      />,
    );

    await openReviewStep();
    fireEvent.click(screen.getByTestId("intake-on-behalf-submit-button"));

    expect(await screen.findByTestId("intake-on-behalf-submit-error")).toHaveTextContent(
      /training\[2\]\.year_from/i,
    );
    expect(screen.getByTestId("intake-on-behalf-submit-button")).toHaveTextContent("Отправить анкету");
    expect(screen.getByTestId("intake-on-behalf-submit-button")).toBeEnabled();
  });

  it("loads submitted draft in read-only view with disabled submit button", async () => {
    mockSubmittedViewSession();

    render(
      <PersonnelApplicationIntakeOnBehalfDrawer
        applicationId={42}
        open
        onClose={vi.fn()}
      />,
    );

    await openReviewStep();
    expect(screen.getByTestId("intake-on-behalf-submit-button")).toHaveTextContent("Анкета отправлена");
    expect(screen.getByTestId("intake-on-behalf-submit-button")).toBeDisabled();
    expect(screen.getByTestId("intake-on-behalf-save-button")).toBeDisabled();
    expect(submitIntakeOnBehalfDraftMock).not.toHaveBeenCalled();
  });

  it("does not resubmit when clicking disabled submitted button", async () => {
    mockSubmittedViewSession();

    render(
      <PersonnelApplicationIntakeOnBehalfDrawer
        applicationId={42}
        open
        onClose={vi.fn()}
      />,
    );

    await openReviewStep();
    fireEvent.click(screen.getByTestId("intake-on-behalf-submit-button"));
    expect(submitIntakeOnBehalfDraftMock).not.toHaveBeenCalled();
  });
});
