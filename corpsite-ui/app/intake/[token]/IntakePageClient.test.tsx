import { describe, expect, it, vi, beforeEach } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import IntakePageClient from "./IntakePageClient";
import * as intakeApi from "../_lib/intakeApi.client";

vi.mock("next/navigation", () => ({
  useParams: () => ({ token: "test-token-abc" }),
}));

describe("IntakePageClient", () => {
  beforeEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads session and autosaves on field change", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    vi.spyOn(intakeApi, "openIntakeSession").mockResolvedValue({
      application_id: 1,
      draft_id: 1,
      link_id: 1,
      status: "editable",
      payload,
      read_only: false,
      link_status: "opened",
    });
    const autosave = vi.spyOn(intakeApi, "autosaveIntakeDraft").mockResolvedValue({
      draft_id: 1,
      status: "editable",
      payload,
      saved_at: new Date().toISOString(),
    });

    render(<IntakePageClient />);

    await waitFor(() => {
      expect(screen.getByText(/Анкета нового сотрудника/i)).toBeInTheDocument();
    });

    const lastName = screen.getByLabelText(/Фамилия/i);
    fireEvent.change(lastName, { target: { value: "Петров" } });

    await waitFor(
      () => {
        expect(autosave).toHaveBeenCalled();
      },
      { timeout: 2000 },
    );
  });

  it("shows success screen after submit", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.personal.last_name = "Сидоров";
    payload.personal.first_name = "Сидор";
    payload.contacts.mobile_phone = "+77001112233";
    payload.current_step = "review";
    payload.education = [
      {
        institution: "ВУЗ",
        year_from: "2020",
        year_to: "2024",
        specialty: "X",
        qualification: "Y",
        diploma_number: "1",
      },
    ];

    vi.spyOn(intakeApi, "openIntakeSession").mockResolvedValue({
      application_id: 1,
      draft_id: 1,
      link_id: 1,
      status: "editable",
      payload,
      read_only: false,
      link_status: "opened",
    });
    vi.spyOn(intakeApi, "submitIntakeDraft").mockResolvedValue({
      application_id: 1,
      draft_id: 1,
      status: "submitted",
      submitted_at: new Date().toISOString(),
    });

    render(<IntakePageClient />);

    const submit = await screen.findByTestId("intake-submit-button");
    fireEvent.click(submit);

    await waitFor(() => {
      expect(screen.getByText(/Анкета отправлена/i)).toBeInTheDocument();
    });
  });
});
