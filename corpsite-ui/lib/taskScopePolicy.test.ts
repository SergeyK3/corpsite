import { describe, expect, it } from "vitest";

import type { MeInfo } from "./types";
import { canSeeTeamTasks, isTaskSystemAdmin } from "./taskScopePolicy";

describe("canSeeTeamTasks", () => {
  it("returns false for null me", () => {
    expect(canSeeTeamTasks(null)).toBe(false);
    expect(canSeeTeamTasks(undefined)).toBe(false);
  });

  it("returns true for system admin role_id=2", () => {
    expect(canSeeTeamTasks({ user_id: 1, role_id: 2 })).toBe(true);
  });

  it('returns true for role_name_ru "Руководитель ОВЭиПД"', () => {
    const me: MeInfo = { user_id: 1, role_id: 10, role_name_ru: "Руководитель ОВЭиПД" };
    expect(canSeeTeamTasks(me)).toBe(true);
  });

  it('returns false for role_name_ru "Госпитальный эксперт ОВЭиПД" without visibility', () => {
    const me: MeInfo = {
      user_id: 1,
      role_id: 11,
      role_name_ru: "Госпитальный эксперт ОВЭиПД",
    };
    expect(canSeeTeamTasks(me)).toBe(false);
  });

  it("returns true for role_code QM_HEAD", () => {
    const me: MeInfo = { user_id: 1, role_id: 10, role_code: "QM_HEAD" };
    expect(canSeeTeamTasks(me)).toBe(true);
  });

  it("returns true when personnel_visibility.can_view_tasks is true", () => {
    const me: MeInfo = {
      user_id: 1,
      role_id: 11,
      role_name_ru: "Госпитальный эксперт ОВЭиПД",
      personnel_visibility: { can_view_tasks: true },
    };
    expect(canSeeTeamTasks(me)).toBe(true);
  });

  it("returns true for director role_name_ru", () => {
    expect(canSeeTeamTasks({ user_id: 1, role_id: 3, role_name_ru: "Директор" })).toBe(true);
  });

  it("returns true for deputy role_name_ru via зам substring", () => {
    expect(
      canSeeTeamTasks({ user_id: 1, role_id: 4, role_name_ru: "Зам по лечебной работе" }),
    ).toBe(true);
  });

  it("returns false for plain executor without manager signals", () => {
    expect(
      canSeeTeamTasks({ user_id: 1, role_id: 99, role_name_ru: "Амбулаторный эксперт ОВЭиПД" }),
    ).toBe(false);
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
