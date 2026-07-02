import { describe, expect, it } from "vitest";

import type { MeInfo } from "./types";
import {
  resolveCabinetTitle,
  resolveEmployeePositionTitle,
  resolvePlatformRoleLabel,
} from "./userCabinetTitle";

describe("userCabinetTitle", () => {
  const withBoth: MeInfo = {
    user_id: 1,
    role_id: 10,
    role_name_ru: "Заместитель директора по административным вопросам",
    position_name: "Заместитель директора по диспансерной и внутренней экспертизе",
  };

  it("prefers employee position for cabinet title", () => {
    expect(resolveCabinetTitle(withBoth)).toBe(
      "Заместитель директора по диспансерной и внутренней экспертизе",
    );
  });

  it("falls back to Platform Role when position is missing", () => {
    const me: MeInfo = {
      user_id: 2,
      role_name_ru: "Заместитель директора по административным вопросам",
    };
    expect(resolveCabinetTitle(me)).toBe("Заместитель директора по административным вопросам");
  });

  it("falls back to Сотрудник when neither position nor role is set", () => {
    expect(resolveCabinetTitle({ user_id: 3 })).toBe("Сотрудник");
  });

  it("extracts platform role and employee position separately", () => {
    expect(resolveEmployeePositionTitle(withBoth)).toBe(
      "Заместитель директора по диспансерной и внутренней экспертизе",
    );
    expect(resolvePlatformRoleLabel(withBoth)).toBe(
      "Заместитель директора по административным вопросам",
    );
  });
});
