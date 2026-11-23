import { describe, expect, it } from "vitest";

import type {
  PersonnelOrderEditorialBlock,
  PersonnelOrderEditorialState,
  PersonnelOrderItem,
} from "./personnelOrdersApi.client";
import {
  PERSONNEL_ORDER_EDITORIAL_UI_LOCALE,
  PERSONNEL_ORDER_EDITORIAL_UI_LOCALES,
  PERSONNEL_ORDER_EDITORIAL_UI_STATUS_LABELS,
  buildEditorialDocumentSections,
  displayPersonnelOrderEditorialBlockText,
  editorialLocaleHint,
  hasEditorialUiLocaleBlocks,
  hasRequiredEditorialLocales,
  mapEditorialConflictMessage,
  resolvePersonnelOrderEditorialUiStatus,
} from "./personnelOrderEditorialUi";

function block(
  overrides: Partial<PersonnelOrderEditorialBlock> & Pick<PersonnelOrderEditorialBlock, "block_id" | "block_type">,
): PersonnelOrderEditorialBlock {
  return {
    scope: "order",
    locale: "kk",
    effective_text: "",
    review_status: "CURRENT",
    editable: true,
    revision: 1,
    ...overrides,
  };
}

describe("personnelOrderEditorialUi", () => {
  it("uses kk as the default editorial UI locale", () => {
    expect(PERSONNEL_ORDER_EDITORIAL_UI_LOCALE).toBe("kk");
    expect(PERSONNEL_ORDER_EDITORIAL_UI_LOCALES).toEqual(["kk", "ru"]);
  });

  it("provides locale-specific hints", () => {
    expect(editorialLocaleHint("kk")).toContain("казахского");
    expect(editorialLocaleHint("ru")).toContain("русского");
  });

  it("maps review/override to human status labels", () => {
    expect(resolvePersonnelOrderEditorialUiStatus(block({ block_id: 1, block_type: "title" }))).toBe(
      "generated",
    );
    expect(
      resolvePersonnelOrderEditorialUiStatus(
        block({ block_id: 1, block_type: "title", override_text: "Қолмен тақырып" }),
      ),
    ).toBe("edited");
    expect(
      resolvePersonnelOrderEditorialUiStatus(
        block({
          block_id: 1,
          block_type: "title",
          override_text: "x",
          review_status: "REVIEW_REQUIRED",
        }),
      ),
    ).toBe("requires_review");
    expect(PERSONNEL_ORDER_EDITORIAL_UI_STATUS_LABELS.generated).toBe("Generated");
    expect(PERSONNEL_ORDER_EDITORIAL_UI_STATUS_LABELS.edited).toBe("Edited");
    expect(PERSONNEL_ORDER_EDITORIAL_UI_STATUS_LABELS.requires_review).toBe("Requires review");
  });

  it("prefers override text for display", () => {
    expect(
      displayPersonnelOrderEditorialBlockText(
        block({
          block_id: 1,
          block_type: "title",
          generated_text: "Авто",
          override_text: "Қолмен",
          effective_text: "Қолмен",
        }),
      ),
    ).toBe("Қолмен");
    expect(
      displayPersonnelOrderEditorialBlockText(
        block({
          block_id: 1,
          block_type: "title",
          generated_text: "Авто",
          effective_text: "Авто",
        }),
      ),
    ).toBe("Авто");
  });

  it("builds document sections for kk and ru separately", () => {
    const state: PersonnelOrderEditorialState = {
      order_id: 1,
      order_status: "DRAFT",
      editable: true,
      order_blocks: [
        block({ block_id: 1, block_type: "title", effective_text: "Жұмысқа қабылдау туралы" }),
        block({ block_id: 2, block_type: "preamble", effective_text: "Кіріспе" }),
        block({ block_id: 3, block_type: "closing", effective_text: "" }),
        block({ block_id: 99, block_type: "title", locale: "ru", effective_text: "О приёме" }),
        block({ block_id: 98, block_type: "preamble", locale: "ru", effective_text: "Преамбула RU" }),
      ],
      items: [
        {
          order_item_id: 10,
          item_number: 1,
          item_type_code: "HIRE",
          basis_required: true,
          blocks: [
            block({
              block_id: 11,
              scope: "item",
              order_item_id: 10,
              block_type: "body",
              effective_text: "Қабылдау...",
            }),
            block({
              block_id: 12,
              scope: "item",
              order_item_id: 10,
              block_type: "basis",
              effective_text: "Негіз: өтініш.",
            }),
            block({
              block_id: 111,
              scope: "item",
              order_item_id: 10,
              locale: "ru",
              block_type: "body",
              effective_text: "Принять...",
            }),
          ],
        },
      ],
    };
    const items: PersonnelOrderItem[] = [
      {
        item_id: 10,
        order_id: 1,
        item_number: 1,
        item_type_code: "HIRE",
        item_status: "ACTIVE",
        employee_name: "Петрова Анна",
      },
    ];
    const kkSections = buildEditorialDocumentSections(state, items, "kk");
    expect(kkSections[0]).toMatchObject({ kind: "order", title: "Заголовок" });
    if (kkSections[0]?.kind === "order") {
      expect(kkSections[0].block?.effective_text).toBe("Жұмысқа қабылдау туралы");
    }

    const ruSections = buildEditorialDocumentSections(state, items, "ru");
    if (ruSections[0]?.kind === "order") {
      expect(ruSections[0].block?.effective_text).toBe("О приёме");
    }
    if (ruSections[2]?.kind === "item") {
      expect(ruSections[2].body?.effective_text).toBe("Принять...");
    }
  });

  it("detects locale presence and required bilingual state", () => {
    const kkOnly: PersonnelOrderEditorialState = {
      order_id: 1,
      order_status: "DRAFT",
      editable: true,
      order_blocks: [block({ block_id: 1, block_type: "title", effective_text: "KK" })],
      items: [],
    };
    expect(hasEditorialUiLocaleBlocks(kkOnly, "kk")).toBe(true);
    expect(hasEditorialUiLocaleBlocks(kkOnly, "ru")).toBe(false);
    expect(hasRequiredEditorialLocales(kkOnly)).toBe(false);

    const both: PersonnelOrderEditorialState = {
      ...kkOnly,
      order_blocks: [
        block({ block_id: 1, block_type: "title", effective_text: "KK" }),
        block({ block_id: 2, block_type: "title", locale: "ru", effective_text: "RU" }),
      ],
    };
    expect(hasRequiredEditorialLocales(both)).toBe(true);
  });

  it("maps revision conflict message for users", () => {
    expect(mapEditorialConflictMessage("Editorial block 5 revision mismatch")).toContain(
      "другим пользователем",
    );
  });
});
