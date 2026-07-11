import { describe, expect, it } from "vitest";

import type {
  PersonnelOrderEditorialBlock,
  PersonnelOrderEditorialState,
  PersonnelOrderItem,
} from "./personnelOrdersApi.client";
import {
  PERSONNEL_ORDER_EDITORIAL_UI_LOCALE,
  PERSONNEL_ORDER_EDITORIAL_UI_STATUS_LABELS,
  buildEditorialDocumentSections,
  displayPersonnelOrderEditorialBlockText,
  hasEditorialUiLocaleBlocks,
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
  it("uses kk as the working editorial UI locale", () => {
    expect(PERSONNEL_ORDER_EDITORIAL_UI_LOCALE).toBe("kk");
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

  it("builds document sections with kk blocks and item FIO", () => {
    const state: PersonnelOrderEditorialState = {
      order_id: 1,
      order_status: "DRAFT",
      editable: true,
      order_blocks: [
        block({ block_id: 1, block_type: "title", effective_text: "Жұмысқа қабылдау туралы" }),
        block({ block_id: 2, block_type: "preamble", effective_text: "Кіріспе" }),
        block({ block_id: 3, block_type: "closing", effective_text: "" }),
        block({ block_id: 99, block_type: "title", locale: "ru", effective_text: "RU" }),
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
    const sections = buildEditorialDocumentSections(state, items);
    expect(sections[0]).toMatchObject({ kind: "order", title: "Заголовок" });
    if (sections[0]?.kind === "order") {
      expect(sections[0].block?.effective_text).toBe("Жұмысқа қабылдау туралы");
    }
    expect(sections[1]).toMatchObject({ kind: "order", title: "Преамбула" });
    expect(sections[2]).toMatchObject({
      kind: "item",
      itemNumber: 1,
      employeeName: "Петрова Анна",
    });
    expect(sections[3]).toMatchObject({ kind: "order", title: "Заключительная часть" });
    expect(hasEditorialUiLocaleBlocks(state)).toBe(true);
    expect(
      hasEditorialUiLocaleBlocks({
        order_id: 1,
        order_status: "DRAFT",
        editable: true,
        order_blocks: [block({ block_id: 1, block_type: "title", locale: "ru", effective_text: "RU" })],
        items: [],
      }),
    ).toBe(false);
  });

  it("maps revision conflict message for users", () => {
    expect(mapEditorialConflictMessage("Editorial block 5 revision mismatch")).toContain(
      "другим пользователем",
    );
  });
});
