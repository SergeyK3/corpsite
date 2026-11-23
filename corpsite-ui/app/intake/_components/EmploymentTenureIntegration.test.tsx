import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import IntakeDraftFormEditor from "./IntakeDraftFormEditor";
import IntakeEmploymentBiographyTable from "./IntakeEmploymentBiographyTable";
import { emptyIntakeDraftPayload, INTAKE_STEPS } from "../_lib/intakeApi.client";

const employmentStepIndex = INTAKE_STEPS.findIndex((step) => step.id === "employment_biography");

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function buildTenureResponse(records: Array<{
  record_id: string;
  label: string;
  days: number;
  overlaps_other?: boolean;
}>) {
  const arithmetic = records.reduce((sum, row) => sum + row.days, 0);
  return {
    calculation_date: "2026-07-23",
    arithmetic_sum_days: arithmetic,
    overlap_excluded_days: 0,
    total_days: arithmetic,
    total_decimal_years: Number((arithmetic / 365.25).toFixed(2)),
    total_ymd: { years: 0, months: 0, days: 0 },
    records: records.map((row, index) => ({
      record_id: row.record_id,
      index,
      label: row.label,
      days: row.days,
      included: true,
      is_open_ended: false,
      overlaps_other: row.overlaps_other ?? false,
      warning: null,
    })),
  };
}

describe("employment tenure integration", () => {
  it("calculates non-zero tenure for dd.mm.yyyy rows with overlap and open period", async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body ?? "{}")) as {
        records: Array<{ record_id: string; year_from: string | null; year_to: string | null }>;
      };
      expect(body.records).toEqual([
        expect.objectContaining({
          record_id: "row-1",
          year_from: "1993-09-01",
          year_to: "1994-07-25",
        }),
        expect.objectContaining({
          record_id: "row-2",
          year_from: "1994-01-01",
          year_to: "1995-06-30",
        }),
        expect.objectContaining({
          record_id: "row-3",
          year_from: "2020-01-01",
          year_to: null,
        }),
      ]);

      return new Response(
        JSON.stringify(
          buildTenureResponse([
            { record_id: "row-1", label: "Больница 1", days: 327 },
            { record_id: "row-2", label: "Больница 2", days: 546, overlaps_other: true },
            { record_id: "row-3", label: "Текущая", days: 900 },
          ]),
        ),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <IntakeEmploymentBiographyTable
        items={[
          {
            record_id: "row-1",
            organization: "Больница 1",
            position: "Врач",
            year_from: "01.09.1993",
            year_to: "25.07.1994",
            reason_for_leaving: "",
          },
          {
            record_id: "row-2",
            organization: "Больница 2",
            position: "Терапевт",
            year_from: "01.01.1994",
            year_to: "30.06.1995",
            reason_for_leaving: "",
          },
          {
            record_id: "row-3",
            organization: "Текущая",
            position: "Главврач",
            year_from: "01.01.2020",
            year_to: "",
            reason_for_leaving: "",
          },
        ]}
        onChange={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("intake-employment-total-tenure")).toHaveTextContent("(1 773 дней)");
    });

    const desktop = screen.getByTestId("intake-employment-desktop-view");
    expect(within(desktop).getByTestId("intake-employment-tenure-row-1")).toHaveTextContent("0,90 года");
    expect(within(desktop).getByTestId("intake-employment-tenure-row-2")).toHaveTextContent("1,49 года");
    expect(within(desktop).getByTestId("intake-employment-tenure-row-3")).toHaveTextContent("2,46 года");
    expect(screen.queryByTestId("intake-employment-tenure-excluded-toggle")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("works in public and hr-on-behalf editors with the same normalized payload", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify(
          buildTenureResponse([{ record_id: "row-1", label: "Больница 1", days: 327 }]),
        ),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const payload = emptyIntakeDraftPayload();
    payload.employment_biography = [
      {
        record_id: "row-1",
        organization: "Больница 1",
        position: "Врач",
        year_from: "01.09.1993",
        year_to: "25.07.1994",
        reason_for_leaving: "",
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

    await waitFor(() => {
      expect(screen.getByTestId("intake-employment-total-tenure")).toHaveTextContent("0,90 года");
    });
    unmount();
    vi.clearAllMocks();
    vi.stubGlobal("fetch", fetchMock);

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

    await waitFor(() => {
      expect(screen.getByTestId("intake-employment-total-tenure")).toHaveTextContent("0,90 года");
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
