// FILE: corpsite-ui/lib/taskNav.test.ts
import { describe, expect, it } from "vitest";

import { buildTaskPageHref, parseTaskIdFromSearchParams, TASK_ID_QUERY_PARAM } from "./taskNav";

describe("taskNav", () => {
  it("builds task page href from task_id", () => {
    expect(buildTaskPageHref(9001)).toBe(`/tasks?${TASK_ID_QUERY_PARAM}=9001`);
    expect(buildTaskPageHref(0)).toBeNull();
    expect(buildTaskPageHref(NaN)).toBeNull();
  });

  it("parses task_id from search params", () => {
    const sp = new URLSearchParams("task_id=42");
    expect(parseTaskIdFromSearchParams(sp)).toBe(42);
    expect(parseTaskIdFromSearchParams(new URLSearchParams())).toBeNull();
  });
});
