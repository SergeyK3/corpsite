import { describe, expect, it } from "vitest";

import type { EmployeeEventDTO } from "../../employees/_lib/types";
import {
  correctionDomainLabel,
  describeCorrectionEvent,
} from "./correctionHistory";

const maps = {
  orgUnits: new Map<number, string>([[10, "Стационар"], [20, "Амбулатория"]]),
  positions: new Map<number, string>([[501, "Врач-терапевт"], [502, "Медсестра"]]),
};

describe("correctionHistory", () => {
  it("describes general correction metadata", () => {
    const event: EmployeeEventDTO = {
      event_id: 1,
      event_type: "CORRECTION",
      effective_date: "2026-07-01",
      from_org_unit_id: 10,
      to_org_unit_id: 10,
      from_position_id: 501,
      to_position_id: 501,
      from_rate: 1,
      to_rate: 1,
      order_ref: null,
      comment: "Исправлено по паспорту",
      created_by: 1,
      created_at: "2026-07-01T10:00:00.000Z",
      metadata: {
        domain: "general",
        reason: "Опечатка в ФИО",
        changes: {
          full_name: { from: "Иванов И.", to: "Иванов Иван" },
        },
      },
    };

    expect(correctionDomainLabel(event)).toBe("Исправление общих сведений");
    expect(describeCorrectionEvent(event, maps)).toEqual([
      "ФИО: Иванов И. → Иванов Иван",
      "Причина: Опечатка в ФИО",
      "Комментарий: Исправлено по паспорту",
    ]);
  });

  it("describes assignment correction metadata with labels", () => {
    const event: EmployeeEventDTO = {
      event_id: 2,
      event_type: "CORRECTION",
      effective_date: "2026-07-01",
      from_org_unit_id: 10,
      to_org_unit_id: 20,
      from_position_id: 501,
      to_position_id: 502,
      from_rate: 1,
      to_rate: 0.5,
      order_ref: null,
      comment: "Сверка с приказом",
      created_by: 1,
      created_at: "2026-07-01T10:00:00.000Z",
      metadata: {
        domain: "assignment",
        reason: "Ошибка импорта",
        changes: {
          org_unit_id: { from: 10, to: 20 },
          position_id: { from: 501, to: 502 },
          employment_rate: { from: 1, to: 0.5 },
          date_from: { from: "2024-01-15", to: null },
        },
      },
    };

    expect(correctionDomainLabel(event)).toBe("Исправление назначения");
    const lines = describeCorrectionEvent(event, maps);
    expect(lines[0]).toBe("Подразделение: Стационар → Амбулатория");
    expect(lines[1]).toBe("Должность: Врач-терапевт → Медсестра");
    expect(lines[2]).toBe("Ставка: 1 → 0.5");
    expect(lines.some((line) => line.startsWith("Дата начала:"))).toBe(true);
    expect(lines).toContain("Причина: Ошибка импорта");
    expect(lines).toContain("Комментарий: Сверка с приказом");
  });
});
