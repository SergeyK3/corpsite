import { describe, expect, it } from "vitest";

import {
  HR_CHANGE_EVENT_TYPES,
  HR_CHANGE_EVENT_TYPE_LABELS,
  hrChangeEventTypeLabel,
  isHrChangeEventType,
} from "./hrChangeEventLabels";

describe("hrChangeEventLabels", () => {
  it("covers all event types with Russian labels", () => {
    expect(HR_CHANGE_EVENT_TYPES).toEqual([
      "NEW",
      "REMOVED",
      "POSITION_CHANGED",
      "DEPARTMENT_CHANGED",
      "EDUCATION_CHANGED",
      "CERTIFICATE_CHANGED",
    ]);
    expect(HR_CHANGE_EVENT_TYPE_LABELS.NEW).toBe("Новый сотрудник");
    expect(HR_CHANGE_EVENT_TYPE_LABELS.REMOVED).toContain("уволен");
    expect(HR_CHANGE_EVENT_TYPE_LABELS.POSITION_CHANGED).toBe("Изменилась должность");
  });

  it("validates event type guard", () => {
    expect(isHrChangeEventType("NEW")).toBe(true);
    expect(isHrChangeEventType("HIRE")).toBe(false);
    expect(hrChangeEventTypeLabel("DEPARTMENT_CHANGED")).toBe("Изменилось отделение");
  });
});
