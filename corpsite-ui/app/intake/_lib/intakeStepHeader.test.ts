import { describe, expect, it } from "vitest";

import { formatIntakeStepHeaderTitle, INTAKE_STEPS } from "./intakeApi.client";

describe("formatIntakeStepHeaderTitle", () => {
  it("formats all step headers from INTAKE_STEPS", () => {
    INTAKE_STEPS.forEach((step, index) => {
      expect(formatIntakeStepHeaderTitle(index)).toBe(
        `Анкета претендента · шаг ${index + 1} из ${INTAKE_STEPS.length} — ${step.title}`,
      );
    });
  });
});
