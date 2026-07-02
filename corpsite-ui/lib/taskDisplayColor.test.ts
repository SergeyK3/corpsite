import { describe, expect, it } from "vitest";

import {
  getTaskDisplayColor,
  resolveTaskDueDateRaw,
  taskDisplayColorDeadlineClass,
  taskDisplayColorTitleClass,
} from "./taskDisplayColor";

const deadline = "2026-06-10";

function onDay(offset: number): Date {
  const base = new Date(2026, 5, 10);
  base.setDate(base.getDate() + offset);
  return base;
}

describe("resolveTaskDueDateRaw", () => {
  it("prefers due_at over legacy deadline aliases", () => {
    expect(
      resolveTaskDueDateRaw({
        due_at: "2026-06-01",
        due_date: "2026-06-02",
        deadline: "2026-06-03",
      }),
    ).toBe("2026-06-01");
  });
});

describe("getTaskDisplayColor", () => {
  it("uses default color before deadline", () => {
    expect(
      getTaskDisplayColor(
        { due_date: deadline, status_code: "IN_PROGRESS" },
        onDay(-1),
      ),
    ).toBe("default");
  });

  it("uses default color on deadline day", () => {
    expect(
      getTaskDisplayColor(
        { due_date: deadline, status_code: "IN_PROGRESS" },
        onDay(0),
      ),
    ).toBe("default");
  });

  it("uses green for on-time manager acceptance within 7 days after deadline", () => {
    expect(
      getTaskDisplayColor(
        {
          due_date: deadline,
          report_approved_at: "2026-06-10T18:00:00+05:00",
          status_code: "DONE",
        },
        onDay(3),
      ),
    ).toBe("green");
  });

  it("reverts green to default after 7 days past deadline", () => {
    expect(
      getTaskDisplayColor(
        {
          due_date: deadline,
          report_approved_at: "2026-06-09T12:00:00+05:00",
          status_code: "DONE",
        },
        onDay(8),
      ),
    ).toBe("default");
  });

  it("uses orange for open overdue tasks within 7 days after deadline", () => {
    expect(
      getTaskDisplayColor(
        { due_date: deadline, status_code: "WAITING_APPROVAL" },
        onDay(4),
      ),
    ).toBe("orange");
  });

  it("uses red for open overdue tasks after 7 days past deadline", () => {
    expect(
      getTaskDisplayColor(
        { due_date: deadline, status_code: "IN_PROGRESS" },
        onDay(8),
      ),
    ).toBe("red");
  });

  it("uses default for late acceptance even shortly after deadline", () => {
    expect(
      getTaskDisplayColor(
        {
          due_date: deadline,
          report_approved_at: "2026-06-12T10:00:00+05:00",
          status_code: "DONE",
        },
        onDay(2),
      ),
    ).toBe("default");
  });

  it("uses default for completed tasks without manager acceptance", () => {
    expect(
      getTaskDisplayColor(
        { due_date: deadline, status_code: "DONE" },
        onDay(10),
      ),
    ).toBe("default");
  });

  it("uses default when deadline is missing", () => {
    expect(getTaskDisplayColor({ status_code: "IN_PROGRESS" }, onDay(5))).toBe("default");
  });
});

describe("taskDisplayColor classes", () => {
  it("maps semantic colors to existing theme classes", () => {
    expect(taskDisplayColorTitleClass("green")).toContain("emerald");
    expect(taskDisplayColorTitleClass("orange")).toContain("amber");
    expect(taskDisplayColorTitleClass("red")).toContain("red");
    expect(taskDisplayColorDeadlineClass("default")).toContain("zinc-600");
  });
});
