import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import * as React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import IntakeDraftFormEditor from "./IntakeDraftFormEditor";
import IntakeEducationTable from "./IntakeEducationTable";
import { emptyIntakeDraftPayload, INTAKE_STEPS } from "../_lib/intakeApi.client";
import { emptyIntakeEducationEntry } from "../_lib/intakeEducation";

const educationStepIndex = INTAKE_STEPS.findIndex((step) => step.id === "education");

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function expandEducationRow(index = 0) {
  const desktop = screen.getByTestId("intake-education-desktop-view");
  fireEvent.click(within(desktop).getByTestId(`intake-education-actions-${index}`));
  fireEvent.click(within(desktop).getByTestId(`intake-education-row-edit-${index}`));
}

describe("IntakeEducationTable", () => {
  it("shows compact table row and expands editor on demand", () => {
    render(
      <IntakeEducationTable
        items={[
          {
            education_type: "basic",
            institution: "КазНУ",
            year_from: "2014-09-01",
            year_to: "2018-06-30",
            specialty: "Медицина",
            qualification: "Врач",
            diploma_number: "AB-123456",
            document_type: "diploma",
          },
        ]}
        onChange={vi.fn()}
      />,
    );

    const desktop = screen.getByTestId("intake-education-desktop-view");
    expect(within(desktop).getByTestId("intake-education-row-0")).toHaveTextContent("КазНУ");
    expect(within(desktop).getByTestId("intake-education-row-0")).toHaveTextContent(
      "01.09.2014 — 30.06.2018",
    );
    expect(within(desktop).getByTestId("intake-education-row-0")).toHaveTextContent(
      "Медицина / Врач",
    );
    expect(within(desktop).getByTestId("intake-education-row-0")).toHaveTextContent("Диплом");
    expect(within(desktop).getByTestId("intake-education-row-0")).toHaveTextContent("AB-123456");
    expect(screen.queryByTestId("intake-education-editor-0")).not.toBeInTheDocument();

    expandEducationRow(0);
    expect(within(desktop).getByTestId("intake-education-editor-0")).toBeInTheDocument();
    expect(within(desktop).getByTestId("intake-education-institution-0")).toHaveValue("КазНУ");
  });

  it("adds a new expanded row from the add button", () => {
    const onChange = vi.fn();
    render(<IntakeEducationTable items={[]} onChange={onChange} />);

    fireEvent.click(screen.getByTestId("intake-education-add-button"));
    expect(onChange).toHaveBeenCalledWith([emptyIntakeEducationEntry()]);
  });

  it("deletes a row after confirmation", () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const onChange = vi.fn();
    render(
      <IntakeEducationTable
        items={[
          {
            education_type: "basic",
            institution: "КазНУ",
            year_from: "2014-09-01",
            year_to: "2018-06-30",
            specialty: "",
            qualification: "",
            diploma_number: "",
          },
        ]}
        onChange={onChange}
      />,
    );

    fireEvent.click(
      within(screen.getByTestId("intake-education-desktop-view")).getByTestId(
        "intake-education-actions-0",
      ),
    );
    fireEvent.click(
      within(screen.getByTestId("intake-education-desktop-view")).getByTestId(
        "intake-education-row-delete-0",
      ),
    );

    expect(confirmSpy).toHaveBeenCalled();
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("saves edited values through onChange", () => {
    const onChange = vi.fn();
    render(
      <IntakeEducationTable
        items={[
          {
            education_type: "basic",
            institution: "КазНУ",
            year_from: "",
            year_to: "",
            specialty: "",
            qualification: "",
            diploma_number: "",
          },
        ]}
        onChange={onChange}
      />,
    );

    expandEducationRow(0);
    fireEvent.change(
      within(screen.getByTestId("intake-education-desktop-view")).getByTestId(
        "intake-education-year-from-0",
      ),
      { target: { value: "01.09.2014" } },
    );

    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ year_from: "2014-09-01" }),
    ]);
  });

  it("saves document type and number through onChange", () => {
    function StatefulEducationTable() {
      const [items, setItems] = React.useState([
        {
          education_type: "basic" as const,
          institution: "КазНУ",
          year_from: "",
          year_to: "",
          specialty: "",
          qualification: "",
          document_type: "diploma" as const,
          diploma_number: "",
        },
      ]);
      return <IntakeEducationTable items={items} onChange={setItems} />;
    }

    render(<StatefulEducationTable />);

    expandEducationRow(0);
    const desktop = screen.getByTestId("intake-education-desktop-view");
    fireEvent.change(within(desktop).getByTestId("intake-education-document-type-0"), {
      target: { value: "certificate" },
    });
    fireEvent.change(within(desktop).getByTestId("intake-education-diploma-number-0"), {
      target: { value: "СЕР-001" },
    });

    expect(within(desktop).getByTestId("intake-education-document-type-0")).toHaveValue("certificate");
    expect(within(desktop).getByTestId("intake-education-diploma-number-0")).toHaveValue("СЕР-001");
  });

  it("auto-expands row when focusTestId targets its date field", () => {
    render(
      <IntakeEducationTable
        items={[
          {
            education_type: "basic",
            institution: "КазНМУ",
            year_from: "2014",
            year_to: "2018-06-30",
            specialty: "",
            qualification: "",
            diploma_number: "",
          },
        ]}
        onChange={vi.fn()}
        focusTestId="intake-education-year-from-0"
      />,
    );

    expect(within(screen.getByTestId("intake-education-desktop-view")).getByTestId("intake-education-editor-0")).toBeInTheDocument();
  });
});

describe("IntakeEducationTable across editor modes", () => {
  it("renders the same education table in public and on-behalf editors", () => {
    const payload = emptyIntakeDraftPayload();
    payload.education = [
      {
        education_type: "basic",
        institution: "КазНУ",
        year_from: "2014-09-01",
        year_to: "2018-06-30",
        specialty: "Медицина",
        qualification: "Врач",
        diploma_number: "AB-123456",
        document_type: "diploma",
      },
    ];

    const { unmount } = render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={vi.fn()}
        stepIndex={educationStepIndex}
        onStepIndexChange={vi.fn()}
        mode="public"
        compact
      />,
    );

    const publicTable = screen.getByTestId("intake-education-table");
    expect(within(publicTable).getByTestId("intake-education-row-0")).toHaveTextContent("КазНУ");
    unmount();

    render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={vi.fn()}
        stepIndex={educationStepIndex}
        onStepIndexChange={vi.fn()}
        mode="hr-on-behalf"
        compact
      />,
    );

    const onBehalfTable = screen.getByTestId("intake-education-table");
    expect(within(onBehalfTable).getByTestId("intake-education-row-0")).toHaveTextContent("КазНУ");
  });
});
