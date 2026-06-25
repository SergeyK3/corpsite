import { describe, expect, it } from "vitest";

import { taskPeriodicityLabel } from "@/lib/taskPeriodicity";

describe("taskPeriodicityLabel", () => {
  it("returns Разовая for adhoc tasks regardless of schedule_type", () => {
    expect(taskPeriodicityLabel({ task_kind: "adhoc", schedule_type: "weekly" })).toBe("Разовая");
    expect(taskPeriodicityLabel({ task_kind: "adhoc" })).toBe("Разовая");
  });

  it("maps regular task schedule_type codes to human-readable labels", () => {
    expect(taskPeriodicityLabel({ task_kind: "regular", schedule_type: "daily" })).toBe("Ежедневно");
    expect(taskPeriodicityLabel({ task_kind: "regular", schedule_type: "weekly" })).toBe("Еженедельно");
    expect(taskPeriodicityLabel({ task_kind: "regular", schedule_type: "monthly" })).toBe("Ежемесячно");
    expect(taskPeriodicityLabel({ task_kind: "regular", schedule_type: "yearly" })).toBe("Ежегодно");
  });

  it("does not infer periodicity from title text", () => {
    expect(
      taskPeriodicityLabel({
        task_kind: "regular",
        schedule_type: null,
      }),
    ).toBe("—");
  });

  it("returns em dash when schedule_type is missing for regular tasks", () => {
    expect(taskPeriodicityLabel({ task_kind: "regular" })).toBe("—");
  });
});
