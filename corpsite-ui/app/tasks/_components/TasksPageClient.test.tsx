// FILE: corpsite-ui/app/tasks/_components/TasksPageClient.test.tsx
import { describe, expect, it, vi } from "vitest";

import {
  parseTaskIdFromSearchParams,
  resolveTaskDrawerCloseTarget,
  RETURN_TO_QUERY_PARAM,
  TASK_ID_QUERY_PARAM,
} from "@/lib/taskNav";

describe("TasksPageClient drawer close navigation", () => {
  it("returns to journal when return_to is present", () => {
    const replace = vi.fn();
    const sp = new URLSearchParams(
      `${TASK_ID_QUERY_PARAM}=9001&${RETURN_TO_QUERY_PARAM}=%2Fregular-task-runs%3Frun_id%3D39`,
    );

    replace(resolveTaskDrawerCloseTarget(sp));

    expect(replace).toHaveBeenCalledWith("/regular-task-runs?run_id=39");
  });

  it("clears task_id and stays on /tasks when return_to is absent", () => {
    const replace = vi.fn();
    const sp = new URLSearchParams(`${TASK_ID_QUERY_PARAM}=9001&org_unit_id=5`);

    replace(resolveTaskDrawerCloseTarget(sp));

    expect(replace).toHaveBeenCalledWith("/tasks?org_unit_id=5");

    const after = new URL(String(replace.mock.calls[0]?.[0]), "http://localhost");
    expect(parseTaskIdFromSearchParams(after.searchParams)).toBeNull();
  });

  it("does not leave deep-link task_id after close without return_to", () => {
    const sp = new URLSearchParams(`${TASK_ID_QUERY_PARAM}=123`);
    const target = resolveTaskDrawerCloseTarget(sp);
    const after = new URL(target, "http://localhost");

    expect(parseTaskIdFromSearchParams(after.searchParams)).toBeNull();
    expect(target).toBe("/tasks");
  });
});
