import { describe, expect, it } from "vitest";

import { statusMarkLinesForLanguage } from "./personnelOrderPrintLocale";
import { buildPersonnelOrderPrintViewModel } from "./personnelOrderPrintViewModel";
import type { PersonnelOrderDetailResponse } from "./personnelOrdersApi.client";

function sampleDetail(
  overrides?: Partial<PersonnelOrderDetailResponse["order"]>,
): PersonnelOrderDetailResponse {
  return {
    order: {
      order_id: 99,
      order_number: "99-К",
      order_date: "2026-07-12",
      order_type_code: "HIRE",
      order_class: "PERSONNEL",
      status: "DRAFT",
      source_mode: "PAPER",
      created_by: 1,
      ...overrides,
    },
    items: [],
    localized_texts: [],
  };
}

describe("personnelOrderPrint characterization", () => {
  it("builds bilingual title fields in a single view model", () => {
    const model = buildPersonnelOrderPrintViewModel(sampleDetail());
    expect(model.title.ru).toContain("при");
    expect(model.title.kk).toContain("туралы");
    expect(model.title.ru).not.toBe(model.title.kk);
  });

  it("maps voided status to cancelled print mark", () => {
    const model = buildPersonnelOrderPrintViewModel(sampleDetail({ status: "VOIDED" }));
    expect(model.statusMark).toBe("cancelled");
    expect(statusMarkLinesForLanguage("cancelled", "ru")[0]).toMatch(/АННУЛИРОВАН/i);
  });

  it("keeps archived voided document printable via cancelled mark", () => {
    const model = buildPersonnelOrderPrintViewModel(
      sampleDetail({ status: "VOIDED", is_archived: true }),
    );
    expect(model.statusMark).toBe("cancelled");
    expect(statusMarkLinesForLanguage("cancelled", "kk").length).toBeGreaterThan(0);
  });
});
