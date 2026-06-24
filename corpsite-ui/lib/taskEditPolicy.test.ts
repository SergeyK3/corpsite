import { describe, expect, it } from "vitest";

import { canEditTask, editButtonTitle, isTaskRowEditable, resolveTaskStatusCode } from "./taskEditPolicy";

describe("resolveTaskStatusCode", () => {
  it("falls back to status_name_ru for waiting approval", () => {
    expect(
      resolveTaskStatusCode({
        status_code: null,
        status_name_ru: "Ожидает согласование",
      }),
    ).toBe("WAITING_APPROVAL");
  });
});

describe("taskEditPolicy", () => {
  it("blocks edit while task is waiting for approval", () => {
    const task = { task_kind: "regular", status_code: "WAITING_APPROVAL" };
    expect(canEditTask(task)).toBe(false);
    expect(editButtonTitle(task)).toContain("согласовании");
  });

  it("blocks edit when only status_name_ru indicates waiting approval", () => {
    const task = {
      task_kind: "regular",
      status_name_ru: "Ожидает согласование",
    };
    expect(canEditTask(task)).toBe(false);
  });

  it("allows edit for in-progress regular tasks", () => {
    const task = { task_kind: "regular", status_code: "WAITING_REPORT" };
    expect(canEditTask(task)).toBe(true);
  });
});

describe("isTaskRowEditable", () => {
  const waitingApprovalTask = {
    task_kind: "regular",
    status_code: "WAITING_APPROVAL",
  };

  it("hides edit in team/all-tasks mode for non-admin", () => {
    expect(isTaskRowEditable(waitingApprovalTask, { readOnlyTeamMode: true })).toBe(false);
  });

  it("hides edit in mine-tasks mode for WAITING_APPROVAL", () => {
    expect(isTaskRowEditable(waitingApprovalTask, { readOnlyTeamMode: false })).toBe(false);
  });

  it("allows edit in mine-tasks mode for in-progress regular task", () => {
    expect(
      isTaskRowEditable(
        { task_kind: "regular", status_code: "WAITING_REPORT" },
        { readOnlyTeamMode: false },
      ),
    ).toBe(true);
  });
});
