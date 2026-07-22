import { describe, expect, it } from "vitest";

import {
  INTAKE_MILITARY_COMPOSITION_OPTIONS,
  INTAKE_MILITARY_OTHER_RANK_OPTION,
  applyIntakeMilitaryCompositionChange,
  applyPprMilitaryCompositionChange,
  filterIntakeMilitaryComboboxOptions,
  getIntakeMilitaryRankOptions,
  inferIntakeMilitaryCompositionFromRank,
  intakeMilitaryCompositionCatalog,
  intakeMilitaryCompositionLabel,
  isIntakeMilitaryRankCompatible,
  normalizeIntakeMilitaryComposition,
  reconcileIntakeMilitaryDraftOnLoad,
  reconcilePprMilitaryFormFields,
  resolveIntakeMilitaryComboboxSelection,
} from "./militaryDictionary";

const emptyMilitary = {
  status: "",
  rank: "",
  category: "",
  composition: "",
  specialty_code: "",
  specialty_name: "",
  fitness_category: "",
  commissariat: "",
  registration_group: "",
  registration_category: "",
};

describe("militaryDictionary", () => {
  it("exposes all five composition options without legacy labels", () => {
    expect(INTAKE_MILITARY_COMPOSITION_OPTIONS.map((option) => option.label)).toEqual([
      "Рядовой состав",
      "Сержантский состав",
      "Офицерский состав",
      "Командный состав",
      "Иной состав",
    ]);
    expect(intakeMilitaryCompositionCatalog()).toHaveLength(5);
    expect(intakeMilitaryCompositionCatalog().map((option) => option.label)).not.toContain(
      "Рядовой и сержантский состав",
    );
    expect(intakeMilitaryCompositionCatalog().map((option) => option.label)).toContain("Командный состав");
  });

  it("filters rank options by selected composition", () => {
    expect(getIntakeMilitaryRankOptions("soldiers").map((option) => option.label)).toEqual([
      "Рядовой",
      "Ефрейтор",
    ]);
    expect(getIntakeMilitaryRankOptions("sergeants").map((option) => option.label)).toContain("Мастер-сержант");
    expect(getIntakeMilitaryRankOptions("officers").map((option) => option.label)).toContain("Полковник");
    expect(getIntakeMilitaryRankOptions("senior_officers").map((option) => option.label)).toEqual([
      "Генерал-майор",
      "Генерал-лейтенант",
      "Генерал-полковник",
      "Генерал",
    ]);
    expect(getIntakeMilitaryRankOptions("other").map((option) => option.label)).toEqual([
      INTAKE_MILITARY_OTHER_RANK_OPTION,
    ]);
    expect(getIntakeMilitaryRankOptions("")).toEqual([]);
  });

  it("filters searchable rank options only within the available list", () => {
    const options = getIntakeMilitaryRankOptions("officers");
    expect(filterIntakeMilitaryComboboxOptions(options, "лейт").map((option) => option.label)).toEqual([
      "Лейтенант",
      "Старший лейтенант",
    ]);
    expect(filterIntakeMilitaryComboboxOptions(options, "генерал")).toEqual([]);
  });

  it("clears incompatible rank when composition changes", () => {
    expect(
      applyIntakeMilitaryCompositionChange("soldiers", "Полковник"),
    ).toEqual({ composition: "soldiers", rank: "" });
    expect(
      applyPprMilitaryCompositionChange("soldiers", "Полковник"),
    ).toEqual({ personnel_composition: "soldiers", military_rank: "" });
    expect(
      applyIntakeMilitaryCompositionChange("officers", "Полковник"),
    ).toEqual({ composition: "officers", rank: "Полковник" });
    expect(
      applyIntakeMilitaryCompositionChange("other", "Кадет"),
    ).toEqual({ composition: "other", rank: "Кадет" });
  });

  it("preserves compatible rank when composition changes", () => {
    expect(
      applyIntakeMilitaryCompositionChange("sergeants", "Сержант"),
    ).toEqual({ composition: "sergeants", rank: "Сержант" });
  });

  it("infers composition from legacy rank-only drafts on load", () => {
    expect(
      reconcileIntakeMilitaryDraftOnLoad({
        ...emptyMilitary,
        rank: "Ефрейтор",
      }),
    ).toMatchObject({
      composition: "soldiers",
      rank: "Ефрейтор",
    });

    expect(
      reconcilePprMilitaryFormFields({
        personnel_composition: "",
        military_rank: "Ефрейтор",
      }),
    ).toEqual({
      personnel_composition: "soldiers",
      military_rank: "Ефрейтор",
    });
  });

  it("preserves both composition and rank from legacy drafts when both are saved", () => {
    expect(
      reconcileIntakeMilitaryDraftOnLoad({
        ...emptyMilitary,
        composition: "command",
        rank: "Генерал-майор",
      }),
    ).toMatchObject({
      composition: "senior_officers",
      rank: "Генерал-майор",
    });

    expect(
      reconcilePprMilitaryFormFields({
        personnel_composition: "command",
        military_rank: "Генерал-майор",
      }),
    ).toEqual({
      personnel_composition: "senior_officers",
      military_rank: "Генерал-майор",
    });
  });

  it("maps legacy composition labels and codes to canonical values", () => {
    expect(normalizeIntakeMilitaryComposition("command")).toBe("senior_officers");
    expect(normalizeIntakeMilitaryComposition("Командный состав")).toBe("senior_officers");
    expect(normalizeIntakeMilitaryComposition("Рядовой и сержантский состав")).toBe("soldiers");
    expect(intakeMilitaryCompositionLabel("senior_officers")).toBe("Командный состав");
    expect(intakeMilitaryCompositionLabel("soldiers")).toBe("Рядовой состав");
  });

  it("resolves combobox selection by label or canonical code", () => {
    const options = intakeMilitaryCompositionCatalog();
    expect(resolveIntakeMilitaryComboboxSelection("Офицерский состав", options)).toBe("officers");
    expect(resolveIntakeMilitaryComboboxSelection("officers", options)).toBe("officers");
  });

  it("checks rank compatibility for structured compositions only", () => {
    expect(isIntakeMilitaryRankCompatible("soldiers", "Рядовой")).toBe(true);
    expect(isIntakeMilitaryRankCompatible("soldiers", "Капитан")).toBe(false);
    expect(isIntakeMilitaryRankCompatible("other", "Кадет")).toBe(true);
    expect(inferIntakeMilitaryCompositionFromRank("Капитан")).toBe("officers");
  });
});
