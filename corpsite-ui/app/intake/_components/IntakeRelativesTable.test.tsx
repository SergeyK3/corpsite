import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import IntakeDraftFormEditor from "./IntakeDraftFormEditor";
import IntakeRelativesTable from "./IntakeRelativesTable";
import { emptyIntakeDraftPayload, INTAKE_STEPS } from "../_lib/intakeApi.client";
import { emptyIntakeRelativeEntry } from "../_lib/intakeRelatives";

const relativesStepIndex = INTAKE_STEPS.findIndex((step) => step.id === "relatives");

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function expandRelativeRow(index = 0) {
  const desktop = screen.getByTestId("intake-relatives-desktop-view");
  fireEvent.click(within(desktop).getByTestId(`intake-relative-actions-${index}`));
  fireEvent.click(within(desktop).getByTestId(`intake-relative-row-edit-${index}`));
}

describe("IntakeRelativesTable", () => {
  it("shows compact table row and expands editor on demand", () => {
    render(
      <IntakeRelativesTable
        items={[
          {
            relationship: "Супруг(а)",
            full_name: "Петрова Анна Сергеевна",
            birth_year: "1992-04-12",
            work_place: "Городская больница №1",
          },
        ]}
        onChange={vi.fn()}
      />,
    );

    const desktop = screen.getByTestId("intake-relatives-desktop-view");
    expect(within(desktop).getByTestId("intake-relative-row-0")).toHaveTextContent("Супруг(а)");
    expect(within(desktop).getByTestId("intake-relative-row-0")).toHaveTextContent(
      "Петрова Анна Сергеевна",
    );
    expect(within(desktop).getByTestId("intake-relative-row-0")).toHaveTextContent("12.04.1992");
    expect(within(desktop).getByTestId("intake-relative-row-0")).toHaveTextContent(
      "Городская больница №1",
    );
    expect(screen.queryByTestId("intake-relative-editor-0")).not.toBeInTheDocument();

    expandRelativeRow(0);
    expect(within(desktop).getByTestId("intake-relative-editor-0")).toBeInTheDocument();
    expect(within(desktop).getByTestId("intake-relative-full-name-0")).toHaveValue(
      "Петрова Анна Сергеевна",
    );
  });

  it("adds a new expanded row from the add button", () => {
    const onChange = vi.fn();
    render(<IntakeRelativesTable items={[]} onChange={onChange} />);

    fireEvent.click(screen.getByTestId("intake-relatives-add-button"));
    expect(onChange).toHaveBeenCalledWith([emptyIntakeRelativeEntry()]);
  });

  it("stores a selected relationship from the predefined list", () => {
    const onChange = vi.fn();
    render(
      <IntakeRelativesTable
        items={[{ relationship: "", full_name: "Иванов Иван", birth_year: "", work_place: "" }]}
        onChange={onChange}
      />,
    );

    expandRelativeRow(0);
    fireEvent.change(
      within(screen.getByTestId("intake-relatives-desktop-view")).getByTestId("intake-relative-relationship-0"),
      { target: { value: "мать" } },
    );

    expect(onChange).toHaveBeenCalledWith([expect.objectContaining({ relationship: "мать" })]);
  });

  it("shows a required custom field for another relationship and preserves a legacy value", () => {
    const onChange = vi.fn();
    render(
      <IntakeRelativesTable
        items={[{ relationship: "бабушка", full_name: "Иванова Анна", birth_year: "", work_place: "" }]}
        onChange={onChange}
      />,
    );

    expandRelativeRow(0);
    const desktop = within(screen.getByTestId("intake-relatives-desktop-view"));
    expect(desktop.getByTestId("intake-relative-relationship-0")).toHaveValue("__other__");
    const customRelationship = desktop.getByTestId("intake-relative-relationship-other-0");
    expect(customRelationship).toHaveValue("бабушка");
    expect(customRelationship).toBeRequired();

    fireEvent.change(customRelationship, { target: { value: "опекун" } });
    expect(onChange).toHaveBeenCalledWith([expect.objectContaining({ relationship: "опекун" })]);
  });

  it("clears a preset value when switching to another relationship", () => {
    const onChange = vi.fn();
    render(
      <IntakeRelativesTable
        items={[{ relationship: "мать", full_name: "Иванова Анна", birth_year: "", work_place: "" }]}
        onChange={onChange}
      />,
    );

    expandRelativeRow(0);
    fireEvent.change(
      within(screen.getByTestId("intake-relatives-desktop-view")).getByTestId("intake-relative-relationship-0"),
      { target: { value: "__other__" } },
    );

    expect(onChange).toHaveBeenCalledWith([expect.objectContaining({ relationship: "" })]);
  });

  it("deletes a row after confirmation", () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const onChange = vi.fn();
    render(
      <IntakeRelativesTable
        items={[
          {
            relationship: "Супруг(а)",
            full_name: "Петрова Анна Сергеевна",
            birth_year: "1992-04-12",
            work_place: "Городская больница №1",
          },
        ]}
        onChange={onChange}
      />,
    );

    fireEvent.click(
      within(screen.getByTestId("intake-relatives-desktop-view")).getByTestId("intake-relative-actions-0"),
    );
    fireEvent.click(
      within(screen.getByTestId("intake-relatives-desktop-view")).getByTestId("intake-relative-row-delete-0"),
    );

    expect(confirmSpy).toHaveBeenCalled();
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("saves edited work place through onChange", () => {
    const onChange = vi.fn();
    render(
      <IntakeRelativesTable
        items={[
          {
            relationship: "Супруг(а)",
            full_name: "Петрова Анна Сергеевна",
            birth_year: "",
            work_place: "",
          },
        ]}
        onChange={onChange}
      />,
    );

    expandRelativeRow(0);
    fireEvent.change(
      within(screen.getByTestId("intake-relatives-desktop-view")).getByTestId(
        "intake-relative-work-place-0",
      ),
      { target: { value: "Школа №12" } },
    );

    expect(onChange).toHaveBeenCalledWith([expect.objectContaining({ work_place: "Школа №12" })]);
  });
});

describe("IntakeRelativesTable across editor modes", () => {
  it("renders the same relatives table in public and on-behalf editors", () => {
    const payload = emptyIntakeDraftPayload();
    payload.relatives = [
      {
        relationship: "Супруг(а)",
        full_name: "Петрова Анна Сергеевна",
        birth_year: "1992-04-12",
        work_place: "Городская больница №1",
      },
    ];

    const { unmount } = render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={vi.fn()}
        stepIndex={relativesStepIndex}
        onStepIndexChange={vi.fn()}
        mode="public"
        compact
      />,
    );

    expect(screen.getByTestId("intake-relatives-table")).toBeInTheDocument();
    unmount();

    render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={vi.fn()}
        stepIndex={relativesStepIndex}
        onStepIndexChange={vi.fn()}
        mode="hr-on-behalf"
        compact
      />,
    );

    expect(screen.getByTestId("intake-relatives-table")).toBeInTheDocument();
  });
});
