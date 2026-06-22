// FILE: corpsite-ui/lib/api.regularTaskRunItems.test.ts
import { describe, expect, it } from "vitest";

import {
  normalizeRegularTaskRunItemsList,
  parseRegularTaskRunItemsResponse,
  type RegularTaskRunItem,
} from "./api";

describe("parseRegularTaskRunItemsResponse", () => {
  const sampleItem: RegularTaskRunItem = {
    item_id: 1,
    run_id: 41,
    regular_task_id: 17,
    status: "ok",
    started_at: "2026-06-24T08:15:03+05:00",
    is_due: true,
    created_tasks: 1,
  };

  it("supports legacy array response", () => {
    const parsed = parseRegularTaskRunItemsResponse([sampleItem]);
    expect(parsed.items).toHaveLength(1);
    expect(parsed.outcome).toBeNull();
    expect(normalizeRegularTaskRunItemsList([sampleItem])).toEqual([sampleItem]);
  });

  it("supports envelope response with outcome", () => {
    const body = {
      run_id: 41,
      items: [
        {
          ...sampleItem,
          task: {
            task_id: 9001,
            resolved: true,
            status_code: "DONE",
            status_name_ru: "Выполнено",
            due_date: "2026-06-23",
            is_overdue: false,
            lifecycle: "done",
          },
        },
      ],
      outcome: {
        run_id: 41,
        period_label: "2026-06-17–2026-06-23",
        counts: {
          linked: 2,
          done: 1,
          in_progress: 1,
          overdue: 0,
          archived: 0,
          unlinked: 0,
          other: 0,
        },
      },
    };

    const parsed = parseRegularTaskRunItemsResponse(body);
    expect(parsed.items).toHaveLength(1);
    expect(parsed.outcome?.counts.done).toBe(1);
    expect(normalizeRegularTaskRunItemsList(body)).toHaveLength(1);
  });
});
