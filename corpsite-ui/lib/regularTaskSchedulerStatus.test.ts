// FILE: corpsite-ui/lib/regularTaskSchedulerStatus.test.ts
import { describe, expect, it } from "vitest";

import {
  buildSchedulerStatusView,
  isAutomaticLiveRun,
  resolveAutomaticRunResultTone,
  SCHEDULER_OBSERVATION_WINDOW_DAYS,
} from "./regularTaskSchedulerStatus";
import type { RegularTaskRunRow } from "./regularTaskRunJournal";

const NOW = new Date("2026-06-25T12:00:00+05:00");

function automaticRun(
  runId: number,
  startedAt: string,
  status: string,
  overrides: Partial<NonNullable<RegularTaskRunRow["stats"]>> = {},
): RegularTaskRunRow {
  return {
    run_id: runId,
    started_at: startedAt,
    status,
    stats: {
      run_kind: "automatic",
      dry_run: false,
      errors: 0,
      ...overrides,
    },
  };
}

describe("isAutomaticLiveRun", () => {
  it("includes automatic live runs", () => {
    expect(isAutomaticLiveRun(automaticRun(1, "2026-06-25T10:00:00+05:00", "ok"))).toBe(true);
    expect(
      isAutomaticLiveRun(
        automaticRun(1, "2026-06-25T10:00:00+05:00", "ok", {
          trigger_source: "automatic",
        }),
      ),
    ).toBe(true);
  });

  it("excludes non-automatic trigger_source values", () => {
    expect(
      isAutomaticLiveRun(
        automaticRun(2, "2026-06-25T10:00:00+05:00", "ok", { trigger_source: "manual" }),
      ),
    ).toBe(false);
    expect(
      isAutomaticLiveRun(
        automaticRun(3, "2026-06-25T10:00:00+05:00", "ok", { trigger_source: "test" }),
      ),
    ).toBe(false);
  });

  it("excludes catch_up runs", () => {
    const run: RegularTaskRunRow = {
      run_id: 2,
      started_at: "2026-06-25T10:00:00+05:00",
      status: "ok",
      stats: {
        run_kind: "catch_up",
        dry_run: false,
        catch_up: { preset: "past_week" },
      },
    };
    expect(isAutomaticLiveRun(run)).toBe(false);
  });

  it("excludes dry_run runs", () => {
    expect(
      isAutomaticLiveRun(
        automaticRun(3, "2026-06-25T10:00:00+05:00", "ok", { dry_run: true }),
      ),
    ).toBe(false);
  });

  it("excludes preview runs", () => {
    expect(
      isAutomaticLiveRun(
        automaticRun(4, "2026-06-25T10:00:00+05:00", "ok", { run_kind: "preview" }),
      ),
    ).toBe(false);
  });

  it("treats legacy runs without run_kind as automatic live", () => {
    const run: RegularTaskRunRow = {
      run_id: 5,
      started_at: "2026-06-25T10:00:00+05:00",
      status: "ok",
      stats: { created: 1, deduped: 0, errors: 0 },
    };
    expect(isAutomaticLiveRun(run)).toBe(true);
  });
});

describe("buildSchedulerStatusView", () => {
  it("returns no_data when there are no automatic live runs", () => {
    const view = buildSchedulerStatusView(
      [
        {
          run_id: 10,
          started_at: "2026-06-25T10:00:00+05:00",
          status: "ok",
          stats: {
            run_kind: "catch_up",
            dry_run: false,
            catch_up: { preset: "past_week" },
          },
        },
      ],
      { now: NOW },
    );
    expect(view.status).toBe("no_data");
    expect(view.status_label).toBe("Нет данных");
  });

  it("returns working for a recent successful automatic live run", () => {
    const view = buildSchedulerStatusView(
      [automaticRun(11, "2026-06-25T10:00:00+05:00", "ok")],
      { now: NOW },
    );
    expect(view.status).toBe("working");
    expect(view.status_label).toBe("Работает");
    expect(view.last_result_label).toBe("Успешно");
  });

  it("returns needs_attention when the latest automatic run is partial", () => {
    const view = buildSchedulerStatusView(
      [
        automaticRun(12, "2026-06-25T10:00:00+05:00", "partial", { errors: 0 }),
        automaticRun(11, "2026-06-24T10:00:00+05:00", "ok"),
      ],
      { now: NOW },
    );
    expect(view.status).toBe("needs_attention");
    expect(view.last_result_label).toBe("Частично");
  });

  it("returns needs_attention when the latest automatic run has errors", () => {
    const view = buildSchedulerStatusView(
      [automaticRun(13, "2026-06-25T10:00:00+05:00", "ok", { errors: 2 })],
      { now: NOW },
    );
    expect(view.status).toBe("needs_attention");
    expect(view.last_result_label).toBe("С ошибками");
  });

  it("ignores successful catch-up when computing status", () => {
    const view = buildSchedulerStatusView(
      [
        {
          run_id: 20,
          started_at: "2026-06-25T10:00:00+05:00",
          status: "ok",
          stats: {
            run_kind: "catch_up",
            dry_run: false,
            errors: 0,
            catch_up: { preset: "past_week" },
          },
        },
      ],
      { now: NOW },
    );
    expect(view.status).toBe("no_data");
  });

  it("returns needs_attention when the last success is outside the observation window", () => {
    const staleStartedAt = new Date(NOW);
    staleStartedAt.setDate(staleStartedAt.getDate() - (SCHEDULER_OBSERVATION_WINDOW_DAYS + 1));

    const view = buildSchedulerStatusView(
      [automaticRun(14, staleStartedAt.toISOString(), "ok")],
      { now: NOW },
    );
    expect(view.status).toBe("needs_attention");
  });

  it("does not use dry_run automatic runs for status", () => {
    const view = buildSchedulerStatusView(
      [automaticRun(15, "2026-06-25T10:00:00+05:00", "ok", { dry_run: true })],
      { now: NOW },
    );
    expect(view.status).toBe("no_data");
  });

  it("uses the newest automatic live run for last run labels", () => {
    const view = buildSchedulerStatusView(
      [
        automaticRun(17, "2026-06-25T10:00:00+05:00", "ok"),
        automaticRun(16, "2026-06-24T10:00:00+05:00", "partial", { errors: 1 }),
      ],
      { now: NOW },
    );
    expect(view.last_result_label).toBe("Успешно");
    expect(view.last_result_tone).toBe("success");
    expect(view.last_successful_run_at_label).not.toBe("—");
  });

  it("prefers a newer global automatic run over an older org-scoped subset", () => {
    const view = buildSchedulerStatusView(
      [
        automaticRun(30, "2026-06-25T10:00:00+05:00", "ok"),
        automaticRun(20, "2026-06-22T10:00:00+05:00", "ok"),
      ],
      { now: NOW },
    );
    expect(view.last_run_at_label).toContain("25.06.2026");
    expect(view.status).toBe("working");
  });
});

describe("resolveAutomaticRunResultTone", () => {
  it("maps run outcomes to badge tones", () => {
    expect(resolveAutomaticRunResultTone(automaticRun(1, "2026-06-25T10:00:00+05:00", "ok"))).toBe(
      "success",
    );
    expect(
      resolveAutomaticRunResultTone(
        automaticRun(2, "2026-06-25T10:00:00+05:00", "partial", { errors: 0 }),
      ),
    ).toBe("warning");
    expect(
      resolveAutomaticRunResultTone(
        automaticRun(3, "2026-06-25T10:00:00+05:00", "ok", { errors: 2 }),
      ),
    ).toBe("error");
  });
});
