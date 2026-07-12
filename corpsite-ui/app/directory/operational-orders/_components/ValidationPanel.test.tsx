import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import ValidationPanel from "./ValidationPanel";

afterEach(() => cleanup());

describe("ValidationPanel", () => {
  it("renders structured validation issues", () => {
    render(
      <ValidationPanel
        title="Intake Validation"
        validation={{
          is_valid: false,
          has_errors: true,
          has_warnings: false,
          issues: [{ code: "OI001", severity: "ERROR", message: "Missing title", field_path: "title" }],
        }}
      />,
    );
    expect(screen.getByTestId("validation-issues")).toBeTruthy();
    expect(screen.getByTestId("validation-summary").textContent).toContain("Требуется исправление");
    expect(screen.getByText(/OI001/)).toBeTruthy();
    expect(screen.getByText(/Missing title/)).toBeTruthy();
  });

  it("groups issues by severity with errors first", () => {
    render(
      <ValidationPanel
        title="Editorial Validation"
        validation={{
          is_valid: false,
          has_errors: true,
          has_warnings: true,
          issues: [
            { code: "W1", severity: "WARNING", message: "Warn", field_path: "a" },
            { code: "E1", severity: "ERROR", message: "Err", field_path: "b" },
          ],
        }}
      />,
    );
    const groups = screen.getAllByTestId(/^validation-group-/);
    expect(groups[0]?.getAttribute("data-testid")).toBe("validation-group-ERROR");
  });
});
