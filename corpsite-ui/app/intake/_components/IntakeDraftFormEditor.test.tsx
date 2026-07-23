import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import IntakeDraftFormEditor from "./IntakeDraftFormEditor";
import { emptyIntakeDraftPayload, INTAKE_STEPS } from "../_lib/intakeApi.client";

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
        diploma_number: "",
      },
    ];

    renderEditor(payload, educationStepIndex);

    const fromInput = screen.getByTestId("intake-education-year-from-0");
    const toInput = screen.getByTestId("intake-education-year-to-0");

    expect(fromInput).toHaveAttribute("placeholder", "ДД.ММ.ГГГГ");
    expect(fromInput).toHaveValue("01.09.2014");
    expect(toInput).toHaveValue("2018 (уточните дату)");
    expect(screen.getByTestId("intake-education-year-to-0-hint")).toHaveTextContent(
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
        diploma_number: "",
      },
    ];
    const onChange = vi.fn();
    renderEditor(payload, educationStepIndex, onChange);

    fireEvent.change(screen.getByTestId("intake-education-year-from-0"), {
      target: { value: "01.09.2014" },
    });

    expect(onChange).toHaveBeenCalled();
    const nextPayload = onChange.mock.calls.at(-1)?.[0];
    expect(nextPayload.education[0].year_from).toBe("2014-09-01");
  });
});
