import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import MigrationWorkflowStepper from "./MigrationWorkflowStepper";

describe("MigrationWorkflowStepper", () => {
  afterEach(() => {
    cleanup();
  });

  it("marks review step as disabled when records step is active", () => {
    render(<MigrationWorkflowStepper activeStepId="records" disabledStepIds={["review"]} />);

    expect(screen.getByText(/2\. Записи/)).toBeInTheDocument();
    expect(screen.getByText(/3\. Проверка/)).toHaveTextContent("(позже)");
  });

  it("shows Готово as the final step title", () => {
    render(<MigrationWorkflowStepper activeStepId="commit" />);

    expect(screen.getByText(/4\. Готово/)).toBeInTheDocument();
  });
});
