import { describe, expect, it } from "vitest";

import {
  MAX_PLATFORM_USER_LOGIN_LENGTH,
  suggestPlatformUserLogin,
  transliterateCyrillic,
} from "./platformUserLoginSuggestion";

describe("suggestPlatformUserLogin", () => {
  it("builds login from three-part FIO (surname.first+patronymic initials)", () => {
    expect(suggestPlatformUserLogin("Козгамбаева Ляззат Таласпаевна")).toBe(
      "kozgambaeva.lt",
    );
    expect(suggestPlatformUserLogin("Нурбеков Багдат Байтлевич")).toBe(
      "nurbekov.bb",
    );
  });

  it("builds login from two-part FIO (surname.first initial only)", () => {
    expect(suggestPlatformUserLogin("Иванова Мария")).toBe("ivanova.m");
  });

  it("transliterates Cyrillic to Latin", () => {
    expect(suggestPlatformUserLogin("Щербакова Юлия")).toBe("scherbakova.yu");
    expect(transliterateCyrillic("Жуков")).toBe("zhukov");
  });

  it("trims extra whitespace and ignores empty tokens", () => {
    expect(suggestPlatformUserLogin("  Козгамбаева   Ляззат   Таласпаевна  ")).toBe(
      "kozgambaeva.lt",
    );
  });

  it("strips disallowed characters from name parts", () => {
    expect(suggestPlatformUserLogin("Иванова-Петрова, Мария (test)")).toBe(
      "ivanova-petrova.m",
    );
  });

  it("returns empty string for empty or whitespace-only FIO", () => {
    expect(suggestPlatformUserLogin("")).toBe("");
    expect(suggestPlatformUserLogin("   ")).toBe("");
  });

  it("supports Latin FIO unchanged", () => {
    expect(suggestPlatformUserLogin("Kim Sergey Viktorovich")).toBe("kim.sv");
  });

  it("uses surname only when no given name token is present", () => {
    expect(suggestPlatformUserLogin("Козгамбаева")).toBe("kozgambaeva");
  });

  it("does not use the old last-token-as-surname algorithm", () => {
    expect(suggestPlatformUserLogin("Козгамбаева Ляззат Таласпаевна")).not.toBe(
      "talaspaevnak",
    );
  });

  it("truncates to max login length", () => {
    const longSurname = "а".repeat(80);
    expect(suggestPlatformUserLogin(`${longSurname} Иван`)).toHaveLength(
      MAX_PLATFORM_USER_LOGIN_LENGTH,
    );
  });
});
