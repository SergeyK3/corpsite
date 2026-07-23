import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import IntakeDraftFormEditor from "./IntakeDraftFormEditor";
import { emptyIntakeDraftPayload, formatIntakeStepHeaderTitle, INTAKE_STEPS } from "../_lib/intakeApi.client";

vi.mock("./IntakeDictionaryCombobox", () => ({
  default: ({ label, testId }: { label: string; testId?: string }) => (
    <input aria-label={label} data-testid={testId} readOnly />
  ),
}));

vi.mock("./IntakeMilitaryCombobox", () => ({
  default: ({ label, testId }: { label: string; testId?: string }) => (
    <input aria-label={label} data-testid={testId} readOnly />
  ),
}));

const personalStepIndex = INTAKE_STEPS.findIndex((step) => step.id === "personal");
const educationStepIndex = INTAKE_STEPS.findIndex((step) => step.id === "education");
const additionalStepIndex = INTAKE_STEPS.findIndex((step) => step.id === "additional");

function expandEducationRow(index = 0) {
  const desktop = screen.getByTestId("intake-education-desktop-view");
  fireEvent.click(within(desktop).getByTestId(`intake-education-actions-${index}`));
  fireEvent.click(within(desktop).getByTestId(`intake-education-row-edit-${index}`));
}

function renderEditor(
  payload = emptyIntakeDraftPayload(),
  stepIndex = personalStepIndex,
  onChange = vi.fn(),
) {
  return render(
    <IntakeDraftFormEditor
      payload={payload}
      onChange={onChange}
      stepIndex={stepIndex}
      onStepIndexChange={vi.fn()}
      compact
    />,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("IntakeDraftFormEditor step headers", () => {
  INTAKE_STEPS.forEach((step, index) => {
    it(`shows unified header for step ${index + 1} (${step.id})`, () => {
      renderEditor(emptyIntakeDraftPayload(), index);
      expect(
        screen.getByRole("heading", { name: formatIntakeStepHeaderTitle(index) }),
      ).toBeInTheDocument();
    });
  });
});

describe("IntakeDraftFormEditor date fields", () => {
  it("renders birth date with full-day birth editor on personal step", () => {
    const payload = emptyIntakeDraftPayload();
    payload.personal.birth_date = "1990-05-20";

    renderEditor(payload, personalStepIndex);

    const birthInput = screen.getByTestId("intake-birth-date");
    expect(birthInput).toHaveAttribute("placeholder", "ДД.ММ.ГГГГ");
    expect(birthInput).toHaveValue("20.05.1990");
  });

  it("stores edited birth date as canonical ISO", () => {
    const payload = emptyIntakeDraftPayload();
    const onChange = vi.fn();
    renderEditor(payload, personalStepIndex, onChange);

    fireEvent.change(screen.getByTestId("intake-birth-date"), {
      target: { value: "15.09.2018" },
    });

    expect(onChange).toHaveBeenCalled();
    const nextPayload = onChange.mock.calls.at(-1)?.[0];
    expect(nextPayload.personal.birth_date).toBe("2018-09-15");
  });

  it("renders period date fields with full-day period editor on education step", () => {
    const payload = emptyIntakeDraftPayload();
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНУ",
        year_from: "2014-09-01",
        year_to: "2018",
        specialty: "",
        qualification: "",
        document_type: "diploma",
        diploma_number: "",
      },
    ];

    renderEditor(payload, educationStepIndex);

    expandEducationRow(0);

    const desktop = screen.getByTestId("intake-education-desktop-view");
    const fromInput = within(desktop).getByTestId("intake-education-year-from-0");
    const toInput = within(desktop).getByTestId("intake-education-year-to-0");

    expect(fromInput).toHaveAttribute("placeholder", "ДД.ММ.ГГГГ");
    expect(fromInput).toHaveValue("01.09.2014");
    expect(toInput).toHaveValue("2018 (уточните дату)");
    expect(within(desktop).getByTestId("intake-education-year-to-0-hint")).toHaveTextContent(
      "Укажите полную дату в формате ДД.ММ.ГГГГ",
    );
  });

  it("stores edited period date as canonical ISO", () => {
    const payload = emptyIntakeDraftPayload();
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНУ",
        year_from: "",
        year_to: "",
        specialty: "",
        qualification: "",
        document_type: "diploma",
        diploma_number: "",
      },
    ];
    const onChange = vi.fn();
    renderEditor(payload, educationStepIndex, onChange);

    expandEducationRow(0);

    fireEvent.change(within(screen.getByTestId("intake-education-desktop-view")).getByTestId("intake-education-year-from-0"), {
      target: { value: "01.09.2014" },
    });

    expect(onChange).toHaveBeenCalled();
    const nextPayload = onChange.mock.calls.at(-1)?.[0];
    expect(nextPayload.education[0].year_from).toBe("2014-09-01");
  });

  it("renders additional step sections", () => {
    renderEditor(emptyIntakeDraftPayload(), additionalStepIndex);
    expect(screen.getByTestId("intake-additional-step")).toBeInTheDocument();
    expect(screen.getByTestId("intake-foreign-languages-section")).toBeInTheDocument();
    expect(screen.getByTestId("intake-awards-section")).toBeInTheDocument();
    expect(screen.getByTestId("intake-academic-degrees-section")).toBeInTheDocument();
  });
});
