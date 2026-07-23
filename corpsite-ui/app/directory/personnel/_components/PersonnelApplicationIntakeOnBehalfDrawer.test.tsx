import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PersonnelApplicationIntakeOnBehalfDrawer from "./PersonnelApplicationIntakeOnBehalfDrawer";
import * as api from "../_lib/personnelApplicationsApi.client";
import type { IntakeDraftPayload } from "@/app/intake/_lib/intakeApi.client";

vi.mock("../_lib/personnelApplicationsApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelApplicationsApi.client")>(
    "../_lib/personnelApplicationsApi.client",
  );
  return {
    ...actual,
    getIntakeOnBehalfEditSession: vi.fn(),
    saveIntakeOnBehalfDraft: vi.fn(),
  };
});

const getIntakeOnBehalfEditSessionMock = vi.mocked(api.getIntakeOnBehalfEditSession);
const saveIntakeOnBehalfDraftMock = vi.mocked(api.saveIntakeOnBehalfDraft);

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
    current_step: "review",
  };
}

function mockEditableSession(updatedAt = "2026-07-23T09:00:00Z") {
  getIntakeOnBehalfEditSessionMock.mockResolvedValue({
    application_id: 42,
    editable: true,
    blocked_reason: null,
    reason_code: null,
    draft: {
      application_id: 42,
      draft_id: 7,
      link_id: 3,
      status: "submitted",
      read_only: false,
      link_status: "submitted",
      updated_at: updatedAt,
      payload: buildSessionPayload(),
    },
  });
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
  fireEvent.click(drawerScope().getByRole("button", { name: /далее/i }));
  fireEvent.click(drawerScope().getByRole("button", { name: /далее/i }));
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
  });
  for (let step = 0; step < 5; step += 1) {
    fireEvent.click(formButton(/назад/i));
  }
  await waitFor(() => {
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

  it("opens on employment biography step with existing data, not review summary", async () => {
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
    expect(screen.queryByText(/шаг 8 из 8/i)).not.toBeInTheDocument();
    expect(screen.getByText(/шаг 6 из 8/i)).toBeInTheDocument();
    const drawer = within(screen.getByTestId("intake-on-behalf-drawer"));
    expect(drawer.getByTestId("intake-employment-biography-table")).toBeInTheDocument();
    expect(
      within(drawer.getByTestId("intake-employment-desktop-view")).getByTestId("intake-employment-row-0"),
    ).toHaveTextContent("Клиника А");
    expect(
      within(drawer.getByTestId("intake-employment-desktop-view")).getByTestId("intake-employment-row-0"),
    ).toHaveTextContent("Медсестра");
    expect(screen.getByRole("button", { name: /далее/i })).toBeInTheDocument();
    expect(screen.queryByTestId("intake-on-behalf-save-button")).not.toBeInTheDocument();
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
    expandEmploymentRow(0);
    const organizationInput = within(
      within(screen.getByTestId("intake-on-behalf-drawer")).getByTestId("intake-employment-desktop-view"),
    ).getByTestId("intake-employment-organization-0");
    fireEvent.change(organizationInput, { target: { value: "Клиника Б" } });

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
      editable: true,
      blocked_reason: null,
      reason_code: null,
      draft: {
        application_id: 42,
        draft_id: 7,
        link_id: 3,
        status: "submitted",
        read_only: false,
        link_status: "submitted",
        updated_at: "2026-07-23T09:00:00Z",
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
});
