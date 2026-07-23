import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import * as React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import IntakeDraftFormEditor from "./IntakeDraftFormEditor";
import IntakeTrainingTable from "./IntakeTrainingTable";
import { emptyIntakeDraftPayload, INTAKE_STEPS } from "../_lib/intakeApi.client";
import { emptyIntakeTrainingEntry, normalizeIntakeTrainingEntry } from "../_lib/intakeTraining";

const trainingStepIndex = INTAKE_STEPS.findIndex((step) => step.id === "training");

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function expandTrainingRow(index = 0) {
  const desktop = screen.getByTestId("intake-training-desktop-view");
  fireEvent.click(within(desktop).getByTestId(`intake-training-actions-${index}`));
  fireEvent.click(within(desktop).getByTestId(`intake-training-row-edit-${index}`));
}

const sampleTraining = normalizeIntakeTrainingEntry({
  course_name: "Охрана труда",
  institution: "Учебный центр",
  year_from: "2021-03-10",
  year_to: "2021-03-12",
  document_type: "certificate",
  document_number: "СТ-001",
  hours: "72",
  hours_is_manual: true,
});

describe("IntakeTrainingTable", () => {
  it("shows compact table row and expands editor on demand", () => {
    render(<IntakeTrainingTable items={[sampleTraining]} onChange={vi.fn()} />);

    const desktop = screen.getByTestId("intake-training-desktop-view");
    expect(within(desktop).getByTestId("intake-training-row-0")).toHaveTextContent("Охрана труда");
    expect(within(desktop).getByTestId("intake-training-row-0")).toHaveTextContent("Учебный центр");
    expect(within(desktop).getByTestId("intake-training-row-0")).toHaveTextContent("10.03.2021 — 12.03.2021");
    expect(within(desktop).getByTestId("intake-training-row-0")).toHaveTextContent("72");
    expect(within(desktop).getByTestId("intake-training-row-0")).toHaveTextContent("Сертификат");
    expect(within(desktop).getByTestId("intake-training-row-0")).toHaveTextContent("СТ-001");
    expect(screen.queryByTestId("intake-training-editor-0")).not.toBeInTheDocument();

    expandTrainingRow(0);
    expect(within(desktop).getByTestId("intake-training-editor-0")).toBeInTheDocument();
    expect(within(desktop).getByTestId("intake-training-document-type-0")).toHaveValue("certificate");
  });

  it("adds a new expanded row from the add button", () => {
    const onChange = vi.fn();
    render(<IntakeTrainingTable items={[]} onChange={onChange} />);

    fireEvent.click(screen.getByTestId("intake-training-add-button"));
    expect(onChange).toHaveBeenCalledWith([emptyIntakeTrainingEntry()]);
  });

  it("saves manual hours and document number through onChange", () => {
    function StatefulTrainingTable() {
      const [items, setItems] = React.useState([
        normalizeIntakeTrainingEntry({
          course_name: "Охрана труда",
          institution: "Учебный центр",
          year_from: "2021-03-10",
          year_to: "2021-03-12",
          hours: "",
          hours_is_manual: false,
        }),
      ]);
      return <IntakeTrainingTable items={items} onChange={setItems} />;
    }

    render(<StatefulTrainingTable />);

    expandTrainingRow(0);
    const desktop = screen.getByTestId("intake-training-desktop-view");
    fireEvent.change(within(desktop).getByTestId("intake-training-hours-0"), {
      target: { value: "36" },
    });
    fireEvent.change(within(desktop).getByTestId("intake-training-document-number-0"), {
      target: { value: "СТ-002" },
    });

    expect(within(desktop).getByTestId("intake-training-hours-0")).toHaveValue("36");
    expect(within(desktop).getByTestId("intake-training-document-number-0")).toHaveValue("СТ-002");
    expect(within(desktop).getByTestId("intake-training-hours-note-0")).toHaveTextContent("По документу");
  });

  it("recalculates hours and note when dates change without manual hours", () => {
    const onChange = vi.fn();
    render(
      <IntakeTrainingTable
        items={[
          normalizeIntakeTrainingEntry({
            course_name: "Охрана труда",
            year_from: "2021-03-10",
            year_to: "2021-03-10",
            hours: "8",
            hours_is_manual: false,
          }),
        ]}
        onChange={onChange}
      />,
    );

    expandTrainingRow(0);
    fireEvent.change(
      within(screen.getByTestId("intake-training-desktop-view")).getByTestId("intake-training-year-to-0"),
      { target: { value: "12.03.2021" } },
    );

    expect(onChange.mock.calls.at(-1)?.[0]).toEqual([
      expect.objectContaining({ year_to: "2021-03-12", hours: "24", hours_is_manual: false }),
    ]);
  });

  it("shows period validation instead of calculated hours for incomplete dates", () => {
    render(
      <IntakeTrainingTable
        items={[
          normalizeIntakeTrainingEntry({
            course_name: "Охрана труда",
            year_from: "2021",
            year_to: "2021-03-12",
            hours: "",
            hours_is_manual: false,
          }),
        ]}
        onChange={vi.fn()}
      />,
    );

    expandTrainingRow(0);
    expect(
      within(screen.getByTestId("intake-training-desktop-view")).getByTestId("intake-training-period-error-0"),
    ).toHaveTextContent("полные даты");
  });
});

describe("IntakeTrainingTable across editor modes", () => {
  it("renders the same training table in public and on-behalf editors", () => {
    const payload = emptyIntakeDraftPayload();
    payload.training = [sampleTraining];

    const { unmount } = render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={vi.fn()}
        stepIndex={trainingStepIndex}
        onStepIndexChange={vi.fn()}
        mode="public"
        compact
      />,
    );

    expect(screen.getByTestId("intake-training-table")).toBeInTheDocument();
    unmount();

    render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={vi.fn()}
        stepIndex={trainingStepIndex}
        onStepIndexChange={vi.fn()}
        mode="hr-on-behalf"
        compact
      />,
    );

    expect(screen.getByTestId("intake-training-table")).toBeInTheDocument();
  });
});
