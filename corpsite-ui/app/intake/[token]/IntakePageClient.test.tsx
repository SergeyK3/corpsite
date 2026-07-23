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

  it("shows unified step header on the military step", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.current_step = "military";

    vi.spyOn(intakeApi, "openIntakeSession").mockResolvedValue({
      application_id: 1,
      draft_id: 1,
      link_id: 1,
      status: "editable",
      payload,
      read_only: false,
      link_status: "opened",
    });

    render(<IntakePageClient />);

    expect(
      await screen.findByRole("heading", {
        name: "Анкета сотрудника. Шаг 7 из 8 – Воинский учёт",
      }),
    ).toBeInTheDocument();
  });

  it("shows searchable composition options on the military step", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.current_step = "military";
    payload.military.composition = "soldiers";
    payload.military.rank = "Рядовой";

    vi.spyOn(intakeApi, "openIntakeSession").mockResolvedValue({
      application_id: 1,
      draft_id: 1,
      link_id: 1,
      status: "editable",
      payload,
      read_only: false,
      link_status: "opened",
    });

    render(<IntakePageClient />);

    const composition = await screen.findByTestId("intake-military-composition");
    expect(composition).toHaveValue("Рядовой состав");

    fireEvent.focus(composition);
    fireEvent.change(composition, { target: { value: "офиц" } });

    expect(await screen.findByTestId("intake-military-composition-list")).toBeInTheDocument();
    expect(screen.getByTestId("intake-military-composition-option-0")).toHaveTextContent("Офицерский состав");
  });

  it("filters rank options by composition and clears incompatible rank on change", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.current_step = "military";
    payload.military.composition = "officers";
    payload.military.rank = "Полковник";

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

    const rank = await screen.findByTestId("intake-military-rank");
    expect(rank).toHaveValue("Полковник");

    fireEvent.focus(rank);
    fireEvent.change(rank, { target: { value: "лейт" } });
    expect(screen.getByTestId("intake-military-rank-option-0")).toHaveTextContent("Лейтенант");

    const composition = screen.getByTestId("intake-military-composition");
    fireEvent.click(composition);
    fireEvent.change(composition, { target: { value: "Рядовой состав" } });
    fireEvent.click(await screen.findByTestId("intake-military-composition-option-0"));

    await waitFor(() => {
      expect(screen.getByTestId("intake-military-rank")).toHaveValue("");
    });

    await waitFor(
      () => {
        expect(autosave).toHaveBeenCalledWith(
          "test-token-abc",
          expect.objectContaining({
            military: expect.objectContaining({
              composition: "soldiers",
              rank: "",
            }),
          }),
        );
      },
      { timeout: 2000 },
    );
  });

  async function pickIntakeMilitaryOption(testId: string, optionLabel: string, query = "") {
    const input = await screen.findByTestId(testId);
    fireEvent.click(input);
    if (query) {
      fireEvent.change(input, { target: { value: query } });
    }
    const list = await screen.findByTestId(`${testId}-list`);
    const options = Array.from(list.querySelectorAll('[role="option"]'));
    const target = options.find((option) => option.textContent === optionLabel);
    if (!target) {
      throw new Error(`Combobox option not found: ${optionLabel}`);
    }
    fireEvent.click(target);
  }

  it("keeps composition after Tab and leaves rank dropdown closed on military step", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.current_step = "military";

    vi.spyOn(intakeApi, "openIntakeSession").mockResolvedValue({
      application_id: 1,
      draft_id: 1,
      link_id: 1,
      status: "editable",
      payload,
      read_only: false,
      link_status: "opened",
    });
    vi.spyOn(intakeApi, "autosaveIntakeDraft").mockResolvedValue({
      draft_id: 1,
      status: "editable",
      payload,
      saved_at: new Date().toISOString(),
    });

    render(<IntakePageClient />);

    await screen.findByTestId("intake-military-composition");
    await pickIntakeMilitaryOption("intake-military-composition", "Офицерский состав");
    expect(screen.getByTestId("intake-military-composition")).toHaveValue("Офицерский состав");

    fireEvent.keyDown(screen.getByTestId("intake-military-composition"), { key: "Tab" });
    fireEvent.focus(screen.getByTestId("intake-military-rank"));

    await waitFor(() => {
      expect(screen.getByTestId("intake-military-composition")).toHaveValue("Офицерский состав");
    });
    expect(screen.queryByTestId("intake-military-rank-list")).not.toBeInTheDocument();
  });

  it("keeps composition when rank changes from Капитан to Старший лейтенант on military step", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.current_step = "military";

    vi.spyOn(intakeApi, "openIntakeSession").mockResolvedValue({
      application_id: 1,
      draft_id: 1,
      link_id: 1,
      status: "editable",
      payload,
      read_only: false,
      link_status: "opened",
    });
    vi.spyOn(intakeApi, "autosaveIntakeDraft").mockResolvedValue({
      draft_id: 1,
      status: "editable",
      payload,
      saved_at: new Date().toISOString(),
    });

    render(<IntakePageClient />);

    await screen.findByTestId("intake-military-composition");
    await pickIntakeMilitaryOption("intake-military-composition", "Офицерский состав");
    await pickIntakeMilitaryOption("intake-military-rank", "Капитан");
    await pickIntakeMilitaryOption("intake-military-rank", "Старший лейтенант");

    expect(screen.getByTestId("intake-military-composition")).toHaveValue("Офицерский состав");
    expect(screen.getByTestId("intake-military-rank")).toHaveValue("Старший лейтенант");
  });

  it("does not clear confirmed composition or rank on blur on military step", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.current_step = "military";

    vi.spyOn(intakeApi, "openIntakeSession").mockResolvedValue({
      application_id: 1,
      draft_id: 1,
      link_id: 1,
      status: "editable",
      payload,
      read_only: false,
      link_status: "opened",
    });
    vi.spyOn(intakeApi, "autosaveIntakeDraft").mockResolvedValue({
      draft_id: 1,
      status: "editable",
      payload,
      saved_at: new Date().toISOString(),
    });

    render(<IntakePageClient />);

    await screen.findByTestId("intake-military-composition");
    await pickIntakeMilitaryOption("intake-military-composition", "Офицерский состав");
    await pickIntakeMilitaryOption("intake-military-rank", "Капитан");

    fireEvent.blur(screen.getByTestId("intake-military-composition"));
    fireEvent.blur(screen.getByTestId("intake-military-rank"));

    await waitFor(() => {
      expect(screen.getByTestId("intake-military-composition")).toHaveValue("Офицерский состав");
      expect(screen.getByTestId("intake-military-rank")).toHaveValue("Капитан");
    });
  });

  it("autosaves military rank and VUS fields", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.current_step = "military";
    payload.military.composition = "soldiers";

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

    const rank = await screen.findByTestId("intake-military-rank");
    fireEvent.click(rank);
    fireEvent.change(rank, { target: { value: "Ефрейтор" } });
    fireEvent.click(await screen.findByTestId("intake-military-rank-option-0"));

    fireEvent.change(screen.getByTestId("intake-military-specialty-code"), {
      target: { value: "868123А" },
    });

    await waitFor(
      () => {
        expect(autosave).toHaveBeenCalledWith(
          "test-token-abc",
          expect.objectContaining({
            military: expect.objectContaining({
              rank: "Ефрейтор",
              specialty_code: "868123",
            }),
          }),
        );
      },
      { timeout: 2000 },
    );
    expect(screen.queryByTestId("intake-military-specialty-name")).not.toBeInTheDocument();
  });

  it("opens legacy rank-only draft with inferred composition", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.current_step = "military";
    payload.military.rank = "Майор";

    vi.spyOn(intakeApi, "openIntakeSession").mockResolvedValue({
      application_id: 1,
      draft_id: 1,
      link_id: 1,
      status: "editable",
      payload,
      read_only: false,
      link_status: "opened",
    });

    render(<IntakePageClient />);

    expect(await screen.findByTestId("intake-military-composition")).toHaveValue("Офицерский состав");
    expect(screen.getByTestId("intake-military-rank")).toHaveValue("Майор");
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
      expect(screen.getByText(/Анкета сотрудника\. Шаг 1 из/i)).toBeInTheDocument();
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

  it("shows popular citizenship and nationality options on focus", async () => {
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
    vi.spyOn(intakeApi, "autosaveIntakeDraft").mockResolvedValue({
      draft_id: 1,
      status: "editable",
      payload,
      saved_at: new Date().toISOString(),
    });

    render(<IntakePageClient />);

    const citizenship = await screen.findByTestId("intake-citizenship");
    fireEvent.focus(citizenship);

    expect(await screen.findByTestId("intake-citizenship-option-0")).toHaveTextContent("Казахстан");

    fireEvent.blur(citizenship);

    const nationality = screen.getByTestId("intake-nationality");
    fireEvent.focus(nationality);

    expect(await screen.findByTestId("intake-nationality-option-0")).toHaveTextContent("казахи");
  });

  it("stores selected dictionary values in draft payload via autosave", async () => {
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

    const citizenship = await screen.findByTestId("intake-citizenship");
    fireEvent.focus(citizenship);
    fireEvent.click(await screen.findByTestId("intake-citizenship-option-1"));

    await waitFor(
      () => {
        expect(autosave).toHaveBeenCalledWith(
          "test-token-abc",
          expect.objectContaining({
            personal: expect.objectContaining({ citizenship: "Россия" }),
          }),
        );
      },
      { timeout: 2000 },
    );
  });

  it("prefills personal and contact fields from draft payload on load", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.personal.last_name = "Петров";
    payload.personal.first_name = "Пётр";
    payload.personal.middle_name = "Петрович";
    payload.personal.birth_date = "1990-05-20";
    payload.contacts.mobile_phone = "+77005554433";
    payload.contacts.email = "petrov@example.test";

    vi.spyOn(intakeApi, "openIntakeSession").mockResolvedValue({
      application_id: 1,
      draft_id: 1,
      link_id: 1,
      status: "editable",
      payload,
      read_only: false,
      link_status: "opened",
    });

    render(<IntakePageClient />);

    expect(await screen.findByLabelText(/Фамилия/i)).toHaveValue("Петров");
    expect(screen.getByLabelText(/Имя/i)).toHaveValue("Пётр");
    expect(screen.getByLabelText(/Отчество/i)).toHaveValue("Петрович");
    expect(screen.getByLabelText(/Дата рождения/i)).toHaveValue("20.05.1990");
  });

  it("shows prefilled phone and email on contacts step without re-entry", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.personal.last_name = "Петров";
    payload.personal.first_name = "Пётр";
    payload.personal.birth_date = "1990-05-20";
    payload.contacts.mobile_phone = "+77005554433";
    payload.contacts.email = "petrov@example.test";
    payload.current_step = "contacts";

    vi.spyOn(intakeApi, "openIntakeSession").mockResolvedValue({
      application_id: 1,
      draft_id: 1,
      link_id: 1,
      status: "editable",
      payload,
      read_only: false,
      link_status: "opened",
    });

    render(<IntakePageClient />);

    expect(await screen.findByLabelText(/Мобильный телефон/i)).toHaveValue("+77005554433");
    expect(screen.getByLabelText(/Email/i)).toHaveValue("petrov@example.test");
  });

  it("autosaves edits to prefilled personal fields into the same draft payload", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.personal.last_name = "Петров";
    payload.personal.first_name = "Пётр";
    payload.personal.birth_date = "1990-05-20";

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

    const lastName = await screen.findByLabelText(/Фамилия/i);
    fireEvent.change(lastName, { target: { value: "Изменён" } });

    await waitFor(
      () => {
        expect(autosave).toHaveBeenCalledWith(
          "test-token-abc",
          expect.objectContaining({
            personal: expect.objectContaining({ last_name: "Изменён" }),
          }),
        );
      },
      { timeout: 2000 },
    );
  });

  it("restores saved citizenship and nationality values after draft load", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.personal.citizenship = "Республика Казахстан";
    payload.personal.nationality = "казах";

    vi.spyOn(intakeApi, "openIntakeSession").mockResolvedValue({
      application_id: 1,
      draft_id: 1,
      link_id: 1,
      status: "editable",
      payload,
      read_only: false,
      link_status: "opened",
    });

    render(<IntakePageClient />);

    expect(await screen.findByTestId("intake-citizenship")).toHaveValue("Республика Казахстан");
    expect(screen.getByTestId("intake-nationality")).toHaveValue("казах");
  });

  it("mirrors residence address from registration when checkbox is enabled", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.current_step = "contacts";

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

    const registration = await screen.findByLabelText(/Адрес регистрации/i);
    fireEvent.change(registration, { target: { value: "г. Алматы, ул. Абая 1" } });

    fireEvent.click(screen.getByTestId("intake-residence-mirror"));

    await waitFor(
      () => {
        expect(autosave).toHaveBeenCalledWith(
          "test-token-abc",
          expect.objectContaining({
            contacts: expect.objectContaining({
              registration_address: "г. Алматы, ул. Абая 1",
              residence_address: "г. Алматы, ул. Абая 1",
            }),
          }),
        );
      },
      { timeout: 2000 },
    );
    expect(screen.getByTestId("intake-residence-address")).toHaveValue("г. Алматы, ул. Абая 1");
  });

  it("shows review summary from existing payload without duplicate inputs", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.personal.last_name = "Петров";
    payload.personal.first_name = "Пётр";
    payload.personal.birth_date = "1990-05-20";
    payload.contacts.mobile_phone = "+77005554433";
    payload.contacts.email = "petrov@example.test";
    payload.current_step = "review";

    vi.spyOn(intakeApi, "openIntakeSession").mockResolvedValue({
      application_id: 1,
      draft_id: 1,
      link_id: 1,
      status: "editable",
      payload,
      read_only: false,
      link_status: "opened",
    });

    render(<IntakePageClient />);

    const summary = await screen.findByTestId("intake-review-summary");
    expect(summary).toHaveTextContent("Петров Пётр");
    expect(summary).toHaveTextContent("20.05.1990");
    expect(summary).toHaveTextContent("+77005554433");
    expect(summary).toHaveTextContent("petrov@example.test");
    expect(screen.queryByLabelText(/Фамилия/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Мобильный телефон/i)).not.toBeInTheDocument();
  });

  it("loads saved education dates in DD.MM.YYYY display format", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.current_step = "education";
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНУ",
        year_from: "2014-09-01",
        year_to: "2018-06-30",
        specialty: "",
        qualification: "",
        diploma_number: "",
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

    render(<IntakePageClient />);

    expect(await screen.findByTestId("intake-education-year-from-0")).toHaveValue("01.09.2014");
    expect(screen.getByTestId("intake-education-year-to-0")).toHaveValue("30.06.2018");
  });

  it("shows legacy year-only education values as needing clarification", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.current_step = "education";
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНУ",
        year_from: "2014",
        year_to: "2018",
        specialty: "",
        qualification: "",
        diploma_number: "",
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

    render(<IntakePageClient />);

    expect(await screen.findByTestId("intake-education-year-from-0")).toHaveValue("2014 (уточните дату)");
    expect(screen.getByTestId("intake-education-year-from-0-hint")).toHaveTextContent("ДД.ММ.ГГГГ");
  });

  it("autosaves edited education date as canonical ISO without day shift", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.current_step = "education";
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНУ",
        year_from: "2014-09-01",
        year_to: "2018-06-30",
        specialty: "",
        qualification: "",
        diploma_number: "",
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
    const autosave = vi.spyOn(intakeApi, "autosaveIntakeDraft").mockResolvedValue({
      draft_id: 1,
      status: "editable",
      payload,
      saved_at: new Date().toISOString(),
    });

    render(<IntakePageClient />);

    const yearTo = await screen.findByTestId("intake-education-year-to-0");
    fireEvent.focus(yearTo);
    fireEvent.change(yearTo, { target: { value: "15.09.2022" } });
    fireEvent.blur(yearTo);

    await waitFor(
      () => {
        expect(autosave).toHaveBeenCalledWith(
          "test-token-abc",
          expect.objectContaining({
            education: [
              expect.objectContaining({
                year_to: "2022-09-15",
              }),
            ],
          }),
        );
      },
      { timeout: 2000 },
    );
  });

  it("loads empty training year without Invalid Date", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.current_step = "training";
    payload.training = [{ institution: "Центр", year: "", course_name: "Охрана труда", hours: "" }];

    vi.spyOn(intakeApi, "openIntakeSession").mockResolvedValue({
      application_id: 1,
      draft_id: 1,
      link_id: 1,
      status: "editable",
      payload,
      read_only: false,
      link_status: "opened",
    });

    render(<IntakePageClient />);

    expect(await screen.findByTestId("intake-training-year-0")).toHaveValue("");
  });

  it("shows education and training periods on review step", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.personal.last_name = "Петров";
    payload.current_step = "review";
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНУ",
        year_from: "2014-09-01",
        year_to: "2018-06-30",
        specialty: "",
        qualification: "",
        diploma_number: "",
      },
    ];
    payload.training = [
      { institution: "Центр", year: "2021-03-10", course_name: "Охрана труда", hours: "" },
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

    render(<IntakePageClient />);

    expect(await screen.findByTestId("intake-review-education-0")).toHaveTextContent(
      "КазНУ: 01.09.2014 — 30.06.2018",
    );
    expect(screen.getByTestId("intake-review-training-0")).toHaveTextContent("Охрана труда (10.03.2021)");
  });

  it("blocks submit on review step when legacy year-only dates remain", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.personal.last_name = "Петров";
    payload.personal.first_name = "Пётр";
    payload.personal.birth_date = "1990-05-20";
    payload.contacts.mobile_phone = "+77005554433";
    payload.current_step = "review";
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНМУ",
        year_from: "2014",
        year_to: "2018-06-30",
        specialty: "",
        qualification: "",
        diploma_number: "",
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
    const submit = vi.spyOn(intakeApi, "submitIntakeDraft");

    render(<IntakePageClient />);

    expect(await screen.findByTestId("intake-review-date-issues")).toBeInTheDocument();
    expect(screen.getByText("Образование → КазНМУ → дата поступления")).toBeInTheDocument();

    const submitButton = screen.getByTestId("intake-submit-button");
    expect(submitButton).toBeDisabled();

    fireEvent.click(submitButton);
    expect(submit).not.toHaveBeenCalled();
  });

  it("navigates to the date field when a review issue is clicked", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.personal.last_name = "Петров";
    payload.personal.first_name = "Пётр";
    payload.personal.birth_date = "1990-05-20";
    payload.contacts.mobile_phone = "+77005554433";
    payload.current_step = "review";
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНМУ",
        year_from: "2014",
        year_to: "2018-06-30",
        specialty: "",
        qualification: "",
        diploma_number: "",
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

    render(<IntakePageClient />);

    fireEvent.click(await screen.findByText("Образование → КазНМУ → дата поступления"));

    expect(
      await screen.findByRole("heading", {
        name: "Анкета сотрудника. Шаг 3 из 8 – Образование",
      }),
    ).toBeInTheDocument();
    expect(await screen.findByTestId("intake-education-year-from-0")).toHaveFocus();
  });

  it("opens rework session on first incomplete date field", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.personal.last_name = "Петров";
    payload.personal.first_name = "Пётр";
    payload.personal.birth_date = "1990-05-20";
    payload.contacts.mobile_phone = "+77005554433";
    payload.current_step = "review";
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНМУ",
        year_from: "2014",
        year_to: "2018-06-30",
        specialty: "",
        qualification: "",
        diploma_number: "",
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
      submitted_at: "2026-07-01T10:00:00Z",
    });

    render(<IntakePageClient />);

    expect(
      await screen.findByRole("heading", {
        name: "Анкета сотрудника. Шаг 3 из 8 – Образование",
      }),
    ).toBeInTheDocument();
    expect(await screen.findByTestId("intake-education-year-from-0")).toHaveFocus();
  });

  it("opens editable form after rework instead of submitted screen", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.personal.last_name = "Петров";
    payload.personal.first_name = "Пётр";
    payload.personal.birth_date = "1990-05-20";
    payload.contacts.mobile_phone = "+77005554433";
    payload.current_step = "review";
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНМУ",
        year_from: "2014-09-01",
        year_to: "2018-06-30",
        specialty: "",
        qualification: "",
        diploma_number: "",
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

    render(<IntakePageClient />);

    expect(await screen.findByTestId("intake-submit-button")).toBeInTheDocument();
    expect(screen.queryByText(/Анкета отправлена/i)).not.toBeInTheDocument();
  });

  it("shows success screen after submit", async () => {
    const payload = intakeApi.emptyIntakeDraftPayload();
    payload.personal.last_name = "Сидоров";
    payload.personal.first_name = "Сидор";
    payload.personal.birth_date = "1990-05-20";
    payload.contacts.mobile_phone = "+77001112233";
    payload.current_step = "review";
    payload.education = [
      {
        education_type: "basic",
        institution: "ВУЗ",
        year_from: "2020-09-01",
        year_to: "2024-06-30",
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
