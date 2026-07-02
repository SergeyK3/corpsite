import { describe, expect, it } from "vitest";

import type { MeInfo } from "./types";
import { canSeeTeamTasks, defaultTaskScope, isTaskSystemAdmin } from "./taskScopePolicy";

describe("canSeeTeamTasks", () => {
  it("returns false for null me", () => {
    expect(canSeeTeamTasks(null)).toBe(false);
    expect(canSeeTeamTasks(undefined)).toBe(false);
  });

  it("returns false when can_view_all_tasks is absent or false", () => {
    expect(canSeeTeamTasks({ user_id: 1, role_id: 11 })).toBe(false);
    expect(canSeeTeamTasks({ user_id: 1, role_id: 11, can_view_all_tasks: false })).toBe(false);
  });

  it('returns false for госпитальный эксперт without can_view_all_tasks even with can_view_tasks visibility', () => {
    const me: MeInfo = {
      user_id: 1,
      role_id: 11,
      role_name_ru: "Госпитальный эксперт ОВЭиПД",
      personnel_visibility: { can_view_tasks: true },
      can_view_all_tasks: false,
    };
    expect(canSeeTeamTasks(me)).toBe(false);
  });

  it("returns true only when backend sets can_view_all_tasks", () => {
    expect(canSeeTeamTasks({ user_id: 1, role_id: 2, can_view_all_tasks: true })).toBe(true);
    expect(
      canSeeTeamTasks({
        user_id: 1,
        role_id: 10,
        role_name_ru: "Руководитель ОВЭиПД",
        can_view_all_tasks: true,
      }),
    ).toBe(true);
  });

  it("ignores frontend role heuristics when can_view_all_tasks is false", () => {
    expect(
      canSeeTeamTasks({
        user_id: 1,
        role_id: 3,
        role_name_ru: "Директор",
        role_code: "DIRECTOR",
        can_view_all_tasks: false,
      }),
    ).toBe(false);
  });
});

describe("defaultTaskScope", () => {
  it("defaults to mine for plain executor", () => {
    expect(defaultTaskScope({ user_id: 1, role_id: 99, can_view_all_tasks: false })).toBe("mine");
  });

  it("defaults to team when can_view_all_tasks is true", () => {
    expect(defaultTaskScope({ user_id: 1, role_id: 2, can_view_all_tasks: true })).toBe("team");
  });

  it("defaults to mine before auth/me (no me)", () => {
    expect(defaultTaskScope(null)).toBe("mine");
  });
});

describe("isTaskSystemAdmin", () => {
  it("returns true for role_id=2", () => {
    expect(isTaskSystemAdmin({ user_id: 1, role_id: 2 })).toBe(true);
  });

  it("returns false for manager role without admin id", () => {
    expect(isTaskSystemAdmin({ user_id: 1, role_id: 10, role_name_ru: "Руководитель ОВЭиПД" })).toBe(
      false,
    );
  });
});
