import { describe, expect, it } from "vitest";

import type { MeInfo } from "./types";
import {
  platformRoleDefinesCabinetIdentity,
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

  it("HR_HEAD cabinet title follows platform role when employee position is stale", () => {
    expect(
      resolveCabinetTitle({
        user_id: 361,
        role_code: "HR_HEAD",
        role_name_ru: "Руководитель отдела кадров",
        position_name: "Руководитель ОВЭиПД",
      }),
    ).toBe("Руководитель отдела кадров");
  });

  it("QM_HEAD cabinet title still follows employee position", () => {
    expect(
      resolveCabinetTitle({
        user_id: 1,
        role_code: "QM_HEAD",
        role_name_ru: "Руководитель ОВЭиПД",
        position_name: "Руководитель ОВЭиПД",
      }),
    ).toBe("Руководитель ОВЭиПД");
    expect(platformRoleDefinesCabinetIdentity("QM_HEAD")).toBe(false);
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
