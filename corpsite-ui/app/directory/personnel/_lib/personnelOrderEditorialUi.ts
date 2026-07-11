/**
 * WP-PO-EDIT-003 — Kazakh-first editorial UI helpers.
 * UI works with locale=kk only; generate may persist both kk and ru.
 * Human labels only; no internal enum/fingerprint exposure in the UI layer.
 */

import type {
  PersonnelOrderEditorialBlock,
  PersonnelOrderEditorialItemGroup,
  PersonnelOrderEditorialState,
  PersonnelOrderItem,
} from "./personnelOrdersApi.client";

export const PERSONNEL_ORDER_EDITORIAL_UI_LOCALE = "kk" as const;

export type PersonnelOrderEditorialUiStatus = "generated" | "edited" | "requires_review";

export const PERSONNEL_ORDER_EDITORIAL_UI_STATUS_LABELS: Record<
  PersonnelOrderEditorialUiStatus,
  string
> = {
  generated: "Generated",
  edited: "Edited",
  requires_review: "Requires review",
};

export function resolvePersonnelOrderEditorialUiStatus(
  block: PersonnelOrderEditorialBlock | null | undefined,
): PersonnelOrderEditorialUiStatus {
  if (!block) return "generated";
  const review = String(block.review_status || "").toUpperCase();
  if (review === "STALE" || review === "REVIEW_REQUIRED" || review === "GENERATION_FAILED") {
    return "requires_review";
  }
  const hasOverride = Boolean(String(block.override_text ?? "").trim());
  return hasOverride ? "edited" : "generated";
}

export function displayPersonnelOrderEditorialBlockText(
  block: PersonnelOrderEditorialBlock | null | undefined,
): string {
  if (!block) return "";
  const override = String(block.override_text ?? "").trim();
  if (override) return String(block.override_text ?? "");
  const effective = String(block.effective_text ?? "").trim();
  if (effective) return String(block.effective_text ?? "");
  return String(block.generated_text ?? "");
}

export function pickEditorialBlockByType(
  blocks: PersonnelOrderEditorialBlock[] | undefined,
  blockType: string,
  locale: string = PERSONNEL_ORDER_EDITORIAL_UI_LOCALE,
): PersonnelOrderEditorialBlock | null {
  if (!blocks?.length) return null;
  const found = blocks.find(
    (b) =>
      String(b.block_type).toLowerCase() === blockType.toLowerCase() &&
      String(b.locale).toLowerCase() === locale.toLowerCase(),
  );
  return found ?? null;
}

/** True when the editor's working locale already has at least one stored block. */
export function hasEditorialUiLocaleBlocks(
  state: PersonnelOrderEditorialState | null | undefined,
): boolean {
  if (!state) return false;
  const locale = PERSONNEL_ORDER_EDITORIAL_UI_LOCALE;
  const orderHas = (state.order_blocks || []).some(
    (b) => String(b.locale).toLowerCase() === locale,
  );
  if (orderHas) return true;
  return (state.items || []).some((group) =>
    (group.blocks || []).some((b) => String(b.locale).toLowerCase() === locale),
  );
}

export type EditorialDocumentSection =
  | {
      kind: "order";
      key: string;
      title: string;
      blockType: "title" | "preamble" | "closing";
      block: PersonnelOrderEditorialBlock | null;
    }
  | {
      kind: "item";
      key: string;
      itemNumber: number;
      employeeName: string | null;
      orderItemId: number;
      body: PersonnelOrderEditorialBlock | null;
      basis: PersonnelOrderEditorialBlock | null;
      basisRequired: boolean;
    };

export function buildEditorialDocumentSections(
  state: PersonnelOrderEditorialState | null | undefined,
  items: PersonnelOrderItem[],
): EditorialDocumentSection[] {
  const sections: EditorialDocumentSection[] = [];
  sections.push({
    kind: "order",
    key: "title",
    title: "Заголовок",
    blockType: "title",
    block: pickEditorialBlockByType(state?.order_blocks, "title"),
  });
  sections.push({
    kind: "order",
    key: "preamble",
    title: "Преамбула",
    blockType: "preamble",
    block: pickEditorialBlockByType(state?.order_blocks, "preamble"),
  });

  const groupsByItem = new Map<number, PersonnelOrderEditorialItemGroup>();
  for (const group of state?.items || []) {
    groupsByItem.set(group.order_item_id, group);
  }

  const activeItems = (items || [])
    .filter((item) => String(item.item_status || "").toUpperCase() !== "VOIDED")
    .slice()
    .sort((a, b) => a.item_number - b.item_number);

  for (const item of activeItems) {
    const group = groupsByItem.get(item.item_id);
    sections.push({
      kind: "item",
      key: `item-${item.item_id}`,
      itemNumber: item.item_number,
      employeeName: item.employee_name ?? null,
      orderItemId: item.item_id,
      body: pickEditorialBlockByType(group?.blocks, "body"),
      basis: pickEditorialBlockByType(group?.blocks, "basis"),
      basisRequired: Boolean(group?.basis_required ?? true),
    });
  }

  sections.push({
    kind: "order",
    key: "closing",
    title: "Заключительная часть",
    blockType: "closing",
    block: pickEditorialBlockByType(state?.order_blocks, "closing"),
  });

  return sections;
}

export function mapEditorialConflictMessage(raw: string): string {
  const text = String(raw || "").trim();
  if (!text) return "Конфликт версий. Обновите текст и сохраните снова.";
  if (/revision mismatch/i.test(text) || /revision/i.test(text)) {
    return "Текст был изменён другим пользователем. Обновите блок и сохраните снова.";
  }
  return text;
}
