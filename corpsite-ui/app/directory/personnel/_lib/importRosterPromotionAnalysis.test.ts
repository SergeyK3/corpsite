import { describe, expect, it } from "vitest";

import type { RosterPromotionItem } from "./importApi.client";
import {
  buildReasonSummary,
  buildReasonTypeSummary,
  buildRosterPromotionOverview,
  collectDepartmentOptions,
  filterRosterPromotionItems,
  getDepartmentLabel,
  getReasonFilterKey,
  getReasonTypeKey,
  normalizeReasonLabel,
  REASON_TYPE_INVALID_IIN,
  REASON_TYPE_UNMATCHED_DEPARTMENT,
} from "./importRosterPromotionAnalysis";

function makeItem(overrides: Partial<RosterPromotionItem> & Pick<RosterPromotionItem, "row_id">): RosterPromotionItem {
  return {
    outcome: "blocked",
    full_name: "Тестов Тест",
    iin: "123456789012",
    ...overrides,
  };
}

function makeLargeBatch(): RosterPromotionItem[] {
  return Array.from({ length: 1200 }, (_, index) => {
    const rowId = index + 1;
    if (rowId <= 182) {
      return makeItem({
        row_id: rowId,
        full_name: `Сотрудник ${rowId}`,
        iin: `${String(rowId).padStart(12, "0")}`,
        reason: "Отделение не сопоставлено: ОБЩЕБОЛЬНИЧНЫЙ ПЕРСОНАЛ",
      });
    }
    if (rowId <= 243) {
      return makeItem({
        row_id: rowId,
        full_name: `Сотрудник ${rowId}`,
        iin: `${String(rowId).padStart(12, "0")}`,
        reason: "Отделение не сопоставлено: КАБИНЕТ ТРАНСФУЗИОЛОГИИ",
      });
    }
    if (rowId <= 252) {
      return makeItem({
        row_id: rowId,
        full_name: `Ошибка ИИН ${rowId}`,
        iin: "123",
        reason: "ИИН отсутствует или не содержит 12 цифр",
      });
    }
    return makeItem({
      row_id: rowId,
      outcome: "would_create",
      full_name: `Новый ${rowId}`,
      iin: `${String(rowId).padStart(12, "0")}`,
      org_unit_name: "Терапия",
      reason: null,
    });
  });
}

describe("importRosterPromotionAnalysis", () => {
  it("normalizes department and IIN reasons for summary", () => {
    expect(normalizeReasonLabel("Отделение не сопоставлено: ОБЩЕБОЛЬНИЧНЫЙ ПЕРСОНАЛ")).toBe(
      "Не сопоставлено подразделение: ОБЩЕБОЛЬНИЧНЫЙ ПЕРСОНАЛ"
    );
    expect(normalizeReasonLabel("Отделение не сопоставлено с org_unit: КАБИНЕТ ТРАНСФУЗИОЛОГИИ")).toBe(
      "Не сопоставлено подразделение: КАБИНЕТ ТРАНСФУЗИОЛОГИИ"
    );
    expect(normalizeReasonLabel("ИИН отсутствует или не содержит 12 цифр")).toBe("Некорректный ИИН");
    expect(normalizeReasonLabel(null)).toBeNull();
  });

  it("builds two-level reason summary and child counts match parent total", () => {
    const items = [
      makeItem({
        row_id: 1,
        reason: "Отделение не сопоставлено: ОБЩЕБОЛЬНИЧНЫЙ ПЕРСОНАЛ",
      }),
      makeItem({
        row_id: 2,
        reason: "Отделение не сопоставлено с org_unit: ОБЩЕБОЛЬНИЧНЫЙ ПЕРСОНАЛ",
      }),
      makeItem({
        row_id: 3,
        reason: "Отделение не сопоставлено: КАБИНЕТ ТРАНСФУЗИОЛОГИИ",
      }),
      makeItem({ row_id: 4, reason: "ИИН отсутствует или не содержит 12 цифр" }),
      makeItem({ row_id: 5, outcome: "would_create", reason: null }),
    ];

    const typeSummary = buildReasonTypeSummary(items);
    expect(typeSummary).toEqual([
      {
        typeKey: REASON_TYPE_UNMATCHED_DEPARTMENT,
        typeLabel: "Не сопоставлено подразделение",
        count: 3,
        details: [
          {
            detailKey: "Не сопоставлено подразделение: ОБЩЕБОЛЬНИЧНЫЙ ПЕРСОНАЛ",
            detailLabel: "ОБЩЕБОЛЬНИЧНЫЙ ПЕРСОНАЛ",
            reasonKey: "Не сопоставлено подразделение: ОБЩЕБОЛЬНИЧНЫЙ ПЕРСОНАЛ",
            count: 2,
          },
          {
            detailKey: "Не сопоставлено подразделение: КАБИНЕТ ТРАНСФУЗИОЛОГИИ",
            detailLabel: "КАБИНЕТ ТРАНСФУЗИОЛОГИИ",
            reasonKey: "Не сопоставлено подразделение: КАБИНЕТ ТРАНСФУЗИОЛОГИИ",
            count: 1,
          },
        ],
      },
      {
        typeKey: REASON_TYPE_INVALID_IIN,
        typeLabel: "Некорректный ИИН",
        count: 1,
        details: [
          {
            detailKey: REASON_TYPE_INVALID_IIN,
            detailLabel: "Некорректный ИИН",
            reasonKey: "Некорректный ИИН",
            count: 1,
          },
        ],
      },
    ]);

    for (const typeRow of typeSummary) {
      expect(typeRow.details.reduce((sum, detail) => sum + detail.count, 0)).toBe(typeRow.count);
    }

    expect(buildReasonSummary(items).find((row) => row.label.includes("ОБЩЕБОЛЬНИЧНЫЙ"))?.count).toBe(2);
  });

  it("builds overview card metrics for large batch", () => {
    const items = makeLargeBatch();
    const overview = buildRosterPromotionOverview(items, {
      would_create: 948,
      would_update: 0,
      already_linked: 0,
      exists: 0,
      conflict: 0,
      blocked: 252,
    });

    expect(items).toHaveLength(1200);
    expect(overview.total).toBe(1200);
    expect(overview.wouldCreate).toBe(948);
    expect(overview.errors).toBe(252);
    expect(overview.topProblem).toEqual({
      label: "Не сопоставлено подразделение",
      count: 243,
    });
  });

  it("filters large batches by reason type, specific reason, status, department, name and IIN", () => {
    const items = makeLargeBatch();

    const byType = filterRosterPromotionItems(items, {
      outcome: "",
      reasonTypeKey: REASON_TYPE_UNMATCHED_DEPARTMENT,
      reasonKey: "",
      department: "",
      qName: "",
      qIin: "",
    });
    expect(byType).toHaveLength(243);

    const byReason = filterRosterPromotionItems(items, {
      outcome: "",
      reasonTypeKey: "",
      reasonKey: getReasonFilterKey("Отделение не сопоставлено: КАБИНЕТ ТРАНСФУЗИОЛОГИИ"),
      department: "",
      qName: "",
      qIin: "",
    });
    expect(byReason).toHaveLength(61);

    const byInvalidIinType = filterRosterPromotionItems(items, {
      outcome: "",
      reasonTypeKey: REASON_TYPE_INVALID_IIN,
      reasonKey: "",
      department: "",
      qName: "",
      qIin: "",
    });
    expect(byInvalidIinType).toHaveLength(9);
    expect(getReasonTypeKey("ИИН отсутствует или не содержит 12 цифр")).toBe(REASON_TYPE_INVALID_IIN);

    const byDepartment = filterRosterPromotionItems(items, {
      outcome: "",
      reasonTypeKey: "",
      reasonKey: "",
      department: "Терапия",
      qName: "",
      qIin: "",
    });
    expect(byDepartment).toHaveLength(948);

    const byStatus = filterRosterPromotionItems(items, {
      outcome: "would_create",
      reasonTypeKey: "",
      reasonKey: "",
      department: "",
      qName: "",
      qIin: "",
    });
    expect(byStatus).toHaveLength(948);

    const byName = filterRosterPromotionItems(items, {
      outcome: "",
      reasonTypeKey: "",
      reasonKey: "",
      department: "",
      qName: "ошибка иин",
      qIin: "",
    });
    expect(byName).toHaveLength(9);

    expect(getDepartmentLabel(makeItem({ row_id: 1, org_unit_name: "Терапия" }))).toBe("Терапия");
    expect(
      getDepartmentLabel(
        makeItem({ row_id: 2, reason: "Отделение не сопоставлено: КАБИНЕТ ТРАНСФУЗИОЛОГИИ" })
      )
    ).toBe("КАБИНЕТ ТРАНСФУЗИОЛОГИИ");
    expect(collectDepartmentOptions(items)).toContain("Терапия");
    expect(collectDepartmentOptions(items)).toContain("КАБИНЕТ ТРАНСФУЗИОЛОГИИ");
  });
});
