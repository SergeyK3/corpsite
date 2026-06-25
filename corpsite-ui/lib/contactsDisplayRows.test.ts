// FILE: corpsite-ui/lib/contactsDisplayRows.test.ts

import { describe, expect, it } from "vitest";

import {
  buildDisplayRows,
  type ContactItem,
  type PositionSlot,
  type WorkingExpertRow,
} from "./contactsDisplayRows";

const AKILTAEVA: ContactItem = {
  contact_id: 101,
  person_id: 508,
  full_name: "Акильтаева Бакыт Сагитовна",
  phone: "+77001234567",
  telegram_numeric_id: 7685102887,
};

const AKILTAEVA_EXPERT: WorkingExpertRow = {
  user_id: 42,
  full_name: "Акильтаева Бакыт Сагитовна",
  role_name_ru: "Амбулаторный эксперт",
  telegram_id: 7685102887,
};

describe("buildDisplayRows", () => {
  it("does not duplicate expert when contact shares full_name", () => {
    const rows = buildDisplayRows([AKILTAEVA], [], [AKILTAEVA_EXPERT]);
    expect(rows.filter((row) => row.kind === "contact")).toHaveLength(1);
    expect(rows.filter((row) => row.kind === "expert")).toHaveLength(0);
  });

  it("does not duplicate expert when only telegram_id matches", () => {
    const contact: ContactItem = {
      contact_id: 2,
      full_name: "Другой формат ФИО",
      telegram_numeric_id: 7685102887,
    };
    const expert: WorkingExpertRow = {
      user_id: 7,
      full_name: "Акильтаева Бакыт Сагитовна",
      role_name_ru: "Амбулаторный эксперт",
      telegram_id: 7685102887,
    };

    const rows = buildDisplayRows([contact], [], [expert]);
    expect(rows.filter((row) => row.kind === "expert")).toHaveLength(0);
  });

  it("does not duplicate expert when person_id matches", () => {
    const contact: ContactItem = {
      contact_id: 3,
      person_id: 9001,
      full_name: "Абдина А.",
      telegram_numeric_id: 111111111,
    };
    const expert: WorkingExpertRow = {
      user_id: 8,
      person_id: 9001,
      full_name: "Абдина Айгерим",
      role_name_ru: "Стационарный эксперт",
      telegram_id: 222222222,
    };

    const rows = buildDisplayRows([contact], [], [expert]);
    expect(rows.filter((row) => row.kind === "expert")).toHaveLength(0);
  });

  it("keeps expert row when no matching contact exists", () => {
    const expert: WorkingExpertRow = {
      user_id: 9,
      full_name: "Мусабеков Нурлан",
      role_name_ru: "Стационарный эксперт",
      telegram_id: 333333333,
    };

    const rows = buildDisplayRows([], [], [expert]);
    expect(rows.filter((row) => row.kind === "expert")).toHaveLength(1);
  });

  it("keeps empty position slots", () => {
    const positions: PositionSlot[] = [
      { position_id: 1, name: "Аналитик ЭРОБ" },
      { position_id: 2, name: "Архивариус" },
    ];

    const rows = buildDisplayRows([], positions, []);
    expect(rows.filter((row) => row.kind === "slot")).toHaveLength(2);
  });

  it("deduplicates several known experts while preserving slots", () => {
    const contacts: ContactItem[] = [
      AKILTAEVA,
      { contact_id: 102, full_name: "Абдина Айгерим К.", telegram_numeric_id: 1001 },
      { contact_id: 103, full_name: "Мусабеков Нурлан Б.", telegram_numeric_id: 1002 },
      { contact_id: 104, full_name: "Сапарбаева Гульмира Т.", telegram_numeric_id: 1003 },
      { contact_id: 105, full_name: "Сейтказина Айгуль М.", telegram_numeric_id: 1004 },
    ];
    const experts: WorkingExpertRow[] = [
      AKILTAEVA_EXPERT,
      { user_id: 43, full_name: "Абдина Айгерим К.", role_name_ru: "Эксперт", telegram_id: 1001 },
      { user_id: 44, full_name: "Мусабеков Нурлан Б.", role_name_ru: "Эксперт", telegram_id: 1002 },
      { user_id: 45, full_name: "Сапарбаева Гульмира Т.", role_name_ru: "Эксперт", telegram_id: 1003 },
      { user_id: 46, full_name: "Сейтказина Айгуль М.", role_name_ru: "Эксперт", telegram_id: 1004 },
    ];
    const positions: PositionSlot[] = [
      { position_id: 10, name: "Аналитик ЭРОБ" },
      { position_id: 11, name: "Архивариус" },
    ];

    const rows = buildDisplayRows(contacts, positions, experts);
    expect(rows.filter((row) => row.kind === "contact")).toHaveLength(5);
    expect(rows.filter((row) => row.kind === "expert")).toHaveLength(0);
    expect(rows.filter((row) => row.kind === "slot")).toHaveLength(2);
  });
});
