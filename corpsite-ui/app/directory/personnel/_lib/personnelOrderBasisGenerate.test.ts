import { describe, expect, it } from "vitest";

import { generatePersonnelOrderBasisText } from "./personnelOrderBasisGenerate";
import {
  effectiveEditorialText,
  isEditorialManuallyEdited,
  isEditorialStale,
  type PersonnelOrderEditorialTextCell,
} from "./personnelOrderEditorialTypes";

describe("generatePersonnelOrderBasisText", () => {
  it("generates PERSONAL_APPLICATION for ru/kk with nominative fallback", () => {
    const fact = {
      basisType: "PERSONAL_APPLICATION" as const,
      subjectEmployeeId: 1,
      subjectEmployeeName: "Бауыржан Куандыкович Еркатов",
    };
    expect(generatePersonnelOrderBasisText(fact, "ru")).toBe(
      "Основание: личное заявление Бауыржан Куандыкович Еркатов.",
    );
    expect(generatePersonnelOrderBasisText(fact, "kk")).toBe(
      "Негіз: Бауыржан Куандыкович Еркатовтың жеке өтініші.",
    );
  });

  it("uses provided morphological forms when present", () => {
    const fact = {
      basisType: "PERSONAL_APPLICATION" as const,
      subjectEmployeeId: 1,
      subjectEmployeeName: "Бауыржан Куандыкович Еркатов",
      subjectEmployeeNameGenitiveRu: "Бауыржана Куандыковича Еркатова",
      subjectEmployeeNamePossessiveKk: "Бауыржан Куандыкович Еркатовтың",
    };
    expect(generatePersonnelOrderBasisText(fact, "ru")).toBe(
      "Основание: личное заявление Бауыржана Куандыковича Еркатова.",
    );
    expect(generatePersonnelOrderBasisText(fact, "kk")).toBe(
      "Негіз: Бауыржан Куандыкович Еркатовтың жеке өтініші.",
    );
  });

  it("supports memo and other types", () => {
    expect(
      generatePersonnelOrderBasisText(
        {
          basisType: "MEMO",
          subjectEmployeeId: null,
          subjectEmployeeName: "Иванов",
        },
        "ru",
      ),
    ).toBe("Основание: служебная записка (Иванов).");
    expect(
      generatePersonnelOrderBasisText(
        {
          basisType: "OTHER",
          subjectEmployeeId: null,
          subjectEmployeeName: null,
          freeText: "Основание: акт проверки.",
        },
        "ru",
      ),
    ).toBe("Основание: акт проверки.");
  });
});

describe("editorial effective text helpers", () => {
  const base: PersonnelOrderEditorialTextCell = {
    generated: "авто",
    override: null,
    sourceFingerprint: "fp1",
    generatedAt: null,
    editedAt: null,
    editedBy: null,
  };

  it("prefers override over generated", () => {
    expect(effectiveEditorialText(base)).toBe("авто");
    expect(effectiveEditorialText({ ...base, override: "ручная" })).toBe("ручная");
    expect(isEditorialManuallyEdited({ ...base, override: "ручная" })).toBe(true);
  });

  it("detects stale only when manually edited and fingerprint differs", () => {
    expect(isEditorialStale(base, "fp2")).toBe(false);
    expect(isEditorialStale({ ...base, override: "x" }, "fp1")).toBe(false);
    expect(isEditorialStale({ ...base, override: "x" }, "fp2")).toBe(true);
  });
});
