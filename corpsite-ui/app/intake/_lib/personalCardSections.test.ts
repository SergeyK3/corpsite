import { describe, expect, it } from "vitest";

import {
  PERSONAL_CARD_PDF_SECTIONS,
  PERSONAL_CARD_SECTIONS,
  PERSONAL_CARD_UI_SECTIONS,
} from "./personalCardSections";

describe("personal-card section registry", () => {
  it("keeps one ordered UI/PDF registry and excludes only tenure calculation from PDF", () => {
    expect(PERSONAL_CARD_UI_SECTIONS.map((section) => section.key)).toEqual([
      "general", "education", "training", "qualification_category",
      "employment_biography", "current_organization", "tenure_calculation",
      "military", "relatives", "foreign_languages", "note", "additional",
    ]);
    expect(PERSONAL_CARD_PDF_SECTIONS.map((section) => section.key)).toEqual([
      "general", "education", "training", "qualification_category",
      "employment_biography", "current_organization", "military", "relatives",
      "foreign_languages", "note", "additional",
    ]);
    expect(PERSONAL_CARD_SECTIONS.find((section) => section.key === "tenure_calculation")).toMatchObject({
      showInUi: true,
      showInPdf: false,
    });
  });
});
