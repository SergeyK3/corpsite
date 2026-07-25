import { describe, expect, it } from "vitest";

import {
  formatIntakeStepHeaderTitle,
  INTAKE_STEPS,
  resolveIntakeOnBehalfInitialStepIndex,
} from "./intakeApi.client";

describe("formatIntakeStepHeaderTitle", () => {
  it("formats all step headers from INTAKE_STEPS", () => {
    INTAKE_STEPS.forEach((step, index) => {
      expect(formatIntakeStepHeaderTitle(index)).toBe(
        `Анкета претендента · шаг ${index + 1} из ${INTAKE_STEPS.length} — ${step.title}`,
      );
    });
  });
});

describe("resolveIntakeOnBehalfInitialStepIndex", () => {
  it("opens HR on-behalf editing on the personal step", () => {
    expect(resolveIntakeOnBehalfInitialStepIndex()).toBe(0);
    expect(INTAKE_STEPS[resolveIntakeOnBehalfInitialStepIndex()].id).toBe("personal");
  });
});
