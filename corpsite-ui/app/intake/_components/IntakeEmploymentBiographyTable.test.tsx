import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import IntakeDraftFormEditor from "./IntakeDraftFormEditor";
import IntakeEmploymentBiographyTable from "./IntakeEmploymentBiographyTable";
import { emptyIntakeDraftPayload, INTAKE_STEPS } from "../_lib/intakeApi.client";
import { emptyIntakeEmploymentBiographyEntry } from "../_lib/intakeEmploymentBiography";

vi.mock("../_lib/employmentTenureApi.client", () => ({
  calculateEmploymentTenure: vi.fn(),
}));

import { calculateEmploymentTenure } from "../_lib/employmentTenureApi.client";

const mockedCalculate = vi.mocked(calculateEmploymentTenure);

const employmentStepIndex = INTAKE_STEPS.findIndex((step) => step.id === "employment_biography");

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function mockTenureCalculation() {
  mockedCalculate.mockResolvedValue({
    calculation_date: "2026-07-23",
    arithmetic_sum_days: 1383,
    overlap_excluded_days: 0,
    total_days: 1383,
    total_decimal_years: 3.79,
    total_ymd: { years: 3, months: 9, days: 14 },
    records: [
      {
        record_id: "legacy-0",
        index: 0,
        label: "Городская больница №1",
        days: 1383,
        included: true,
        is_open_ended: false,
        overlaps_other: false,
        warning: null,
      },
    ],
  });
}

function expandEmploymentRow(index = 0) {
  const desktop = screen.getByTestId("intake-employment-desktop-view");
  fireEvent.click(within(desktop).getByTestId(`intake-employment-actions-${index}`));
  fireEvent.click(within(desktop).getByTestId(`intake-employment-row-edit-${index}`));
}

describe("IntakeEmploymentBiographyTable", () => {
  it("shows compact table row and expands editor on demand", async () => {
    mockTenureCalculation();
    render(
      <IntakeEmploymentBiographyTable
        items={[
          {
            organization: "Городская больница №1",
            position: "Врач-терапевт",
            year_from: "2018-09-01",
            year_to: "2022-06-15",
            reason_for_leaving: "По собственному желанию",
          },
        ]}
        onChange={vi.fn()}
      />,
    );

    const desktop = screen.getByTestId("intake-employment-desktop-view");
    expect(within(desktop).getByTestId("intake-employment-row-0")).toHaveTextContent("Городская больница №1");
    expect(within(desktop).getByTestId("intake-employment-row-0")).toHaveTextContent("01.09.2018 — 15.06.2022");
    expect(screen.queryByTestId("intake-employment-editor-0")).not.toBeInTheDocument();

    expandEmploymentRow(0);
    expect(within(desktop).getByTestId("intake-employment-editor-0")).toBeInTheDocument();
    expect(within(desktop).getByTestId("intake-employment-organization-0")).toHaveValue(
      "Городская больница №1",
    );

    await waitFor(() => {
      expect(screen.getByTestId("intake-employment-total-tenure")).toHaveTextContent("3,79 года");
    });
    expect(within(desktop).getByTestId("intake-employment-tenure-legacy-0")).toHaveTextContent("3,79 года");
  });

  it("adds a new expanded row from the add button", () => {
    mockTenureCalculation();
    const onChange = vi.fn();
    render(<IntakeEmploymentBiographyTable items={[]} onChange={onChange} />);

    fireEvent.click(screen.getByTestId("intake-employment-add-button"));
    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({
        organization: "",
        position: "",
        year_from: "",
        year_to: "",
        reason_for_leaving: "",
        record_id: expect.any(String),
      }),
    ]);
  });

  it("deletes a row after confirmation", () => {
    mockTenureCalculation();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const onChange = vi.fn();
    render(
      <IntakeEmploymentBiographyTable
        items={[
          {
            organization: "Клиника А",
            position: "Медсестра",
            year_from: "2020-01-15",
            year_to: "2024-08-01",
            reason_for_leaving: "Переезд",
          },
        ]}
        onChange={onChange}
      />,
    );

    fireEvent.click(within(screen.getByTestId("intake-employment-desktop-view")).getByTestId("intake-employment-actions-0"));
    fireEvent.click(within(screen.getByTestId("intake-employment-desktop-view")).getByTestId("intake-employment-row-delete-0"));

    expect(confirmSpy).toHaveBeenCalled();
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("clears end date when current employment is checked", () => {
    mockTenureCalculation();
    const onChange = vi.fn();
    render(
      <IntakeEmploymentBiographyTable
        items={[
          {
            organization: "Клиника А",
            position: "Медсестра",
            year_from: "2020-01-15",
            year_to: "2024-08-01",
            reason_for_leaving: "",
          },
        ]}
        onChange={onChange}
      />,
    );

    expandEmploymentRow(0);
    fireEvent.click(within(screen.getByTestId("intake-employment-desktop-view")).getByTestId("intake-employment-current-0"));

    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ year_to: "" }),
    ]);
  });
});

describe("IntakeEmploymentBiographyTable across editor modes", () => {
  it("renders the same employment table in public and on-behalf editors", async () => {
    mockTenureCalculation();
    const payload = emptyIntakeDraftPayload();
    payload.employment_biography = [
      {
        organization: "Городская больница №1",
        position: "Врач-терапевт",
        year_from: "2018-09-01",
        year_to: "2022-06-15",
        reason_for_leaving: "По собственному желанию",
      },
    ];

    const { unmount } = render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={vi.fn()}
        stepIndex={employmentStepIndex}
        onStepIndexChange={vi.fn()}
        mode="public"
        compact
      />,
    );

    const publicTable = screen.getByTestId("intake-employment-biography-table");
    expect(within(publicTable).getByTestId("intake-employment-row-0")).toHaveTextContent(
      "Городская больница №1",
    );
    unmount();

    render(
      <IntakeDraftFormEditor
        payload={payload}
        onChange={vi.fn()}
        stepIndex={employmentStepIndex}
        onStepIndexChange={vi.fn()}
        mode="hr-on-behalf"
        compact
      />,
    );

    const onBehalfTable = screen.getByTestId("intake-employment-biography-table");
    expect(within(onBehalfTable).getByTestId("intake-employment-row-0")).toHaveTextContent(
      "Городская больница №1",
    );
  });
});
