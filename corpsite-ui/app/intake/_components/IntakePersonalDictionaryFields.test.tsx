import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import IntakeDraftFormEditor from "./IntakeDraftFormEditor";
import IntakeDictionaryCombobox from "./IntakeDictionaryCombobox";
import { emptyIntakeDraftPayload, INTAKE_STEPS } from "../_lib/intakeApi.client";
import {
  INTAKE_CITIZENSHIP_CATALOG,
  INTAKE_CITIZENSHIP_POPULAR,
} from "../_lib/intakePersonalDictionary";

const personalStepIndex = INTAKE_STEPS.findIndex((step) => step.id === "personal");

function readCitizenshipOptions(scope: ReturnType<typeof within>) {
  fireEvent.click(scope.getByTestId("intake-citizenship"));
  return scope.getAllByRole("option").map((node) => node.textContent);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Intake personal dictionary fields across modes", () => {
  it("shows the same citizenship options for empty and legacy saved values", () => {
    render(
      <IntakeDictionaryCombobox
        label="Гражданство"
        value=""
        onChange={vi.fn()}
        popular={INTAKE_CITIZENSHIP_POPULAR}
        catalog={INTAKE_CITIZENSHIP_CATALOG}
        testId="intake-citizenship"
      />,
    );

    fireEvent.click(screen.getByTestId("intake-citizenship"));
    const emptyValueOptions = screen.getAllByRole("option").map((node) => node.textContent);

    cleanup();

    render(
      <IntakeDictionaryCombobox
        label="Гражданство"
        value="Республика Казахстан"
        onChange={vi.fn()}
        popular={INTAKE_CITIZENSHIP_POPULAR}
        catalog={INTAKE_CITIZENSHIP_CATALOG}
        testId="intake-citizenship"
      />,
    );

    expect(screen.getByTestId("intake-citizenship")).toHaveValue("Республика Казахстан");
    fireEvent.click(screen.getByTestId("intake-citizenship"));
    const legacyValueOptions = screen.getAllByRole("option").map((node) => node.textContent);

    expect(legacyValueOptions).toEqual(emptyValueOptions);
    expect(legacyValueOptions).toContain("Россия");
    expect(legacyValueOptions.length).toBeGreaterThanOrEqual(10);
  });

  it("shows identical citizenship dropdown options in public and on-behalf editors", () => {
    const payload = emptyIntakeDraftPayload();
    payload.personal.citizenship = "Республика Казахстан";

    const { unmount: unmountPublic } = render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={vi.fn()}
        stepIndex={personalStepIndex}
        onStepIndexChange={vi.fn()}
        mode="public"
        compact
      />,
    );

    const publicOptions = readCitizenshipOptions(within(document.body));
    unmountPublic();

    render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={vi.fn()}
        stepIndex={personalStepIndex}
        onStepIndexChange={vi.fn()}
        mode="hr-on-behalf"
        compact
      />,
    );

    const onBehalfOptions = readCitizenshipOptions(within(document.body));

    expect(onBehalfOptions).toEqual(publicOptions);
    expect(onBehalfOptions).toContain("Россия");
    expect(screen.getByTestId("intake-citizenship")).toHaveValue("Республика Казахстан");
  });

  it("shows gender select with male and female options in public and on-behalf editors", () => {
    const payload = emptyIntakeDraftPayload();
    const expectedOptions = ["Выберите…", "Мужской", "Женский"];

    const { unmount: unmountPublic } = render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={vi.fn()}
        stepIndex={personalStepIndex}
        onStepIndexChange={vi.fn()}
        mode="public"
        compact
      />,
    );

    const publicSelect = screen.getByTestId("intake-gender");
    expect(within(publicSelect).getAllByRole("option").map((node) => node.textContent)).toEqual(
      expectedOptions,
    );
    unmountPublic();

    render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={vi.fn()}
        stepIndex={personalStepIndex}
        onStepIndexChange={vi.fn()}
        mode="hr-on-behalf"
        compact
      />,
    );

    const onBehalfSelect = screen.getByTestId("intake-gender");
    expect(within(onBehalfSelect).getAllByRole("option").map((node) => node.textContent)).toEqual(
      expectedOptions,
    );
  });
});
