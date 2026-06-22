// FILE: corpsite-ui/lib/taskNav.test.ts
import { describe, expect, it } from "vitest";

import {
  buildTaskPageHref,
  parseReturnToFromSearchParams,
  parseTaskIdFromSearchParams,
  removeTaskIdFromSearchParams,
  resolveTaskDrawerCloseTarget,
  RETURN_TO_QUERY_PARAM,
  TASK_ID_QUERY_PARAM,
} from "./taskNav";

describe("taskNav", () => {
  it("builds task page href from task_id", () => {
    expect(buildTaskPageHref(9001)).toBe(`/tasks?${TASK_ID_QUERY_PARAM}=9001`);
    expect(buildTaskPageHref(0)).toBeNull();
    expect(buildTaskPageHref(NaN)).toBeNull();
  });

  it("builds task page href with encoded return_to", () => {
    const href = buildTaskPageHref(9001, { returnTo: "/regular-task-runs?run_id=39" });
    expect(href).toBe(
      `/tasks?${TASK_ID_QUERY_PARAM}=9001&${RETURN_TO_QUERY_PARAM}=%2Fregular-task-runs%3Frun_id%3D39`,
    );

    const params = new URLSearchParams(href!.split("?")[1] ?? "");
    expect(parseTaskIdFromSearchParams(params)).toBe(9001);
    expect(parseReturnToFromSearchParams(params)).toBe("/regular-task-runs?run_id=39");
  });

  it("parses task_id from search params", () => {
    const sp = new URLSearchParams("task_id=42");
    expect(parseTaskIdFromSearchParams(sp)).toBe(42);
    expect(parseTaskIdFromSearchParams(new URLSearchParams())).toBeNull();
  });

  it("parses return_to from search params", () => {
    const sp = new URLSearchParams(
      `task_id=42&${RETURN_TO_QUERY_PARAM}=%2Fregular-task-runs%3Frun_id%3D39`,
    );
    expect(parseReturnToFromSearchParams(sp)).toBe("/regular-task-runs?run_id=39");
    expect(parseReturnToFromSearchParams(new URLSearchParams("return_to=https://evil.test"))).toBeNull();
  });

  it("removes task_id and return_to while preserving other query params", () => {
    const sp = new URLSearchParams("task_id=123&return_to=%2Fregular-task-runs%3Frun_id%3D39&org_unit_id=5");
    expect(removeTaskIdFromSearchParams(sp)).toBe("/tasks?org_unit_id=5");

    const after = new URL(removeTaskIdFromSearchParams(sp), "http://localhost");
    expect(parseTaskIdFromSearchParams(after.searchParams)).toBeNull();
    expect(parseReturnToFromSearchParams(after.searchParams)).toBeNull();
  });

  it("resolveTaskDrawerCloseTarget returns return_to when present", () => {
    const sp = new URLSearchParams(
      `task_id=9001&${RETURN_TO_QUERY_PARAM}=%2Fregular-task-runs%3Frun_id%3D39`,
    );
    expect(resolveTaskDrawerCloseTarget(sp)).toBe("/regular-task-runs?run_id=39");
  });

  it("resolveTaskDrawerCloseTarget clears deep-link params when return_to is absent", () => {
    const sp = new URLSearchParams("task_id=9001&org_unit_id=7");
    expect(resolveTaskDrawerCloseTarget(sp)).toBe("/tasks?org_unit_id=7");

    const after = new URL(resolveTaskDrawerCloseTarget(sp), "http://localhost");
    expect(parseTaskIdFromSearchParams(after.searchParams)).toBeNull();
  });
});
