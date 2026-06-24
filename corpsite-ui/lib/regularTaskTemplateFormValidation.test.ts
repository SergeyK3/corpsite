import { describe, expect, it } from "vitest";

import { validateTemplateFormValues } from "./regularTaskTemplateFormValidation";

const validMonthlyValues = {
  title: "Monthly template",
  owner_unit_id: "10",
  schedule_type: "monthly",
  schedule_params: '{"bymonthday":[1],"time":"10:00"}',
};

describe("validateTemplateFormValues", () => {
  it("accepts valid monthly schedule_params", () => {
    expect(validateTemplateFormValues(validMonthlyValues)).toBeNull();
  });

  it("accepts legacy time values with seconds", () => {
    expect(
      validateTemplateFormValues({
        ...validMonthlyValues,
        schedule_params: '{"bymonthday":[1],"time":"10:00:00"}',
      }),
    ).toBeNull();
  });

  it("rejects monthly schedule_params without bymonthday", () => {
    expect(
      validateTemplateFormValues({
        ...validMonthlyValues,
        schedule_params: '{"time":"10:00"}',
      }),
    ).toBe("Для ежемесячного расписания обязателен параметр bymonthday.");
  });
});
