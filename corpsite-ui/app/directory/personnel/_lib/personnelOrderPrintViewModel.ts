import type {
  PersonnelOrderDetailResponse,
  PersonnelOrderEditorialBlock,
  PersonnelOrderEditorialState,
  PersonnelOrderItem,
} from "./personnelOrdersApi.client";
import type { LocalizedText } from "./personnelOrderPrintLocalized";
import { localizedFromSingle, localizedText } from "./personnelOrderPrintLocalized";
import type { PersonnelOrderPrintItemContext } from "./personnelOrderPrintItemText";

export type PersonnelOrderPrintStatusMark = "none" | "draft" | "unsigned" | "cancelled";

export type PersonnelOrderPrintItemViewModel = {
  itemId: number;
  itemNumber: number;
  itemTypeCode: string;
  employeeId: number | null;
  employeeName: string | null;
  effectiveDate: string | null;
  context: PersonnelOrderPrintItemContext;
  /**
   * Effective editorial body (override → generated) when editorial state exists.
   * Null means HTML renderer should fall back to deterministic templates.
   */
  body: LocalizedText | null;
  /** Effective editorial item basis when present. */
  basis: LocalizedText | null;
};

export type PersonnelOrderPrintViewModel = {
  orderId: number;
  orderNumber: string | null;
  orderDate: string | null;
  status: string;
  statusMark: PersonnelOrderPrintStatusMark;
  organization: LocalizedText;
  title: LocalizedText;
  preamble: LocalizedText | null;
  /** Order-level closing (editorial effective); omitted from print when empty. */
  closing: LocalizedText | null;
  documentTypeCode: string;
  placeOfIssue: LocalizedText;
  items: PersonnelOrderPrintItemViewModel[];
  basis: LocalizedText[];
  signatory: {
    position: LocalizedText | null;
    fio: string | null;
  };
  acknowledgements: Array<{ employeeId: number | null; employeeName: string | null }>;
};

export type PersonnelOrderPrintNameMaps = {
  organizationName?: string | null;
  organizationNameKk?: string | null;
  orgUnitNames?: Record<number, string>;
  positionNames?: Record<number, string>;
  /** Optional localized signatory position from directory when order field is empty. */
  signatoryPosition?: LocalizedText | string | null;
  /** Optional editorial state from GET …/editorial (WP-PO-EDIT-002). */
  editorial?: PersonnelOrderEditorialState | null;
};

/** Official document titles — not technical type labels (HIRE / Составной). */
export const PERSONNEL_ORDER_PRINT_DOCUMENT_TITLES: Record<string, LocalizedText> = {
  HIRE: localizedText("Жұмысқа қабылдау туралы", "О приёме на работу"),
  TRANSFER: localizedText("Ауыстыру туралы", "О переводе"),
  TERMINATION: localizedText("Жұмыстан босату туралы", "Об увольнении"),
  CONCURRENT_DUTY_START: localizedText("Қоса атқаруды белгілеу туралы", "Об установлении совмещения"),
  CONCURRENT_DUTY_END: localizedText("Қоса атқаруды тоқтату туралы", "О прекращении совмещения"),
  COMPOSITE: localizedText("Кадрлық өзгерістер туралы", "О кадровых изменениях"),
};

function optionalNumber(value: unknown): number | null {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? Math.trunc(n) : null;
}

function optionalString(value: unknown): string | null {
  if (value == null) return null;
  const text = String(value).trim();
  return text || null;
}

function nameFromMap(map: Record<number, string> | undefined, id: number | null): LocalizedText | null {
  if (id == null || !map) return null;
  const name = optionalString(map[id]);
  return name ? localizedFromSingle(name) : null;
}

function resolveStatusMark(status: string): PersonnelOrderPrintStatusMark {
  const normalized = String(status || "").trim().toUpperCase();
  if (normalized === "VOIDED") return "cancelled";
  if (normalized === "DRAFT") return "draft";
  if (normalized === "READY_FOR_SIGNATURE") return "unsigned";
  return "none";
}

function isTechnicalTitle(value: string | null | undefined): boolean {
  const text = optionalString(value);
  if (!text) return true;
  const upper = text.toUpperCase();
  if (
    [
      "HIRE",
      "TRANSFER",
      "TERMINATION",
      "CONCURRENT_DUTY_START",
      "CONCURRENT_DUTY_END",
      "COMPOSITE",
    ].includes(upper)
  ) {
    return true;
  }
  // Russian/Kazakh technical type labels used in UI badges
  const technicalLabels = new Set([
    "приём",
    "прием",
    "перевод",
    "увольнение",
    "совмещение (начало)",
    "совмещение (окончание)",
    "составной",
  ]);
  return technicalLabels.has(text.toLowerCase());
}

function documentTitleFallback(typeCode: string | null | undefined): LocalizedText {
  const normalized = String(typeCode || "").trim().toUpperCase();
  return (
    PERSONNEL_ORDER_PRINT_DOCUMENT_TITLES[normalized] ||
    PERSONNEL_ORDER_PRINT_DOCUMENT_TITLES.COMPOSITE
  );
}

function pickEffectiveByLocale(
  blocks: PersonnelOrderEditorialBlock[] | undefined,
  blockType: string,
): LocalizedText | null {
  if (!blocks?.length) return null;
  const kk = optionalString(
    blocks.find((b) => b.block_type === blockType && String(b.locale).toLowerCase() === "kk")
      ?.effective_text,
  );
  const ru = optionalString(
    blocks.find((b) => b.block_type === blockType && String(b.locale).toLowerCase() === "ru")
      ?.effective_text,
  );
  if (!kk && !ru) return null;
  return localizedText(kk, ru);
}

/**
 * Fallback priority (PO-EDIT-002):
 * editorial override/generated effective → legacy localized → deterministic renderer.
 */
function pickLocalizedTexts(
  detail: PersonnelOrderDetailResponse,
  editorial: PersonnelOrderEditorialState | null | undefined,
): {
  title: LocalizedText;
  preamble: LocalizedText | null;
  closing: LocalizedText | null;
} {
  const editorialTitle = pickEffectiveByLocale(editorial?.order_blocks, "title");
  const editorialPreamble = pickEffectiveByLocale(editorial?.order_blocks, "preamble");
  const editorialClosing = pickEffectiveByLocale(editorial?.order_blocks, "closing");

  const rows = detail.localized_texts || [];
  const kk = rows.find((row) => String(row.locale).toLowerCase() === "kk");
  const ru = rows.find((row) => String(row.locale).toLowerCase() === "ru");

  const fromLocalized = localizedText(
    isTechnicalTitle(kk?.title) ? null : kk?.title,
    isTechnicalTitle(ru?.title) ? null : ru?.title,
  );
  const fallback = documentTitleFallback(detail.order.order_type_code);
  const title: LocalizedText = {
    kk: editorialTitle?.kk || fromLocalized.kk || fallback.kk || null,
    ru: editorialTitle?.ru || fromLocalized.ru || fallback.ru || null,
  };

  const legacyPreamble = localizedText(kk?.preamble, ru?.preamble);
  const preambleMerged = localizedText(
    editorialPreamble?.kk || legacyPreamble.kk,
    editorialPreamble?.ru || legacyPreamble.ru,
  );
  const hasPreamble = Boolean(preambleMerged.kk || preambleMerged.ru);
  const hasClosing = Boolean(editorialClosing?.kk || editorialClosing?.ru);
  return {
    title,
    preamble: hasPreamble ? preambleMerged : null,
    closing: hasClosing ? editorialClosing : null,
  };
}

function resolveSignatoryPosition(
  orderPosition: string | null,
  maps: PersonnelOrderPrintNameMaps,
): LocalizedText | null {
  if (orderPosition) return localizedFromSingle(orderPosition);
  const fromMap = maps.signatoryPosition;
  if (fromMap == null) return null;
  if (typeof fromMap === "string") {
    const text = optionalString(fromMap);
    return text ? localizedFromSingle(text) : null;
  }
  const kk = optionalString(fromMap.kk);
  const ru = optionalString(fromMap.ru);
  if (!kk && !ru) return null;
  return localizedText(kk, ru);
}

function buildItemContext(
  item: PersonnelOrderItem,
  maps: PersonnelOrderPrintNameMaps,
): PersonnelOrderPrintItemContext {
  const payload = item.payload || {};
  const orgUnitId = optionalNumber(payload.org_unit_id) ?? optionalNumber(item.org_unit_id);
  const positionId = optionalNumber(payload.position_id);
  const toOrgUnitId = optionalNumber(payload.to_org_unit_id);
  const toPositionId = optionalNumber(payload.to_position_id);

  return {
    itemNumber: item.item_number,
    itemTypeCode: item.item_type_code,
    employeeName: optionalString(item.employee_name),
    effectiveDate: optionalString(item.effective_date),
    orgUnitName:
      nameFromMap(maps.orgUnitNames, orgUnitId) ||
      (optionalString(item.org_unit_name) ? localizedFromSingle(item.org_unit_name) : null),
    positionName: nameFromMap(maps.positionNames, positionId),
    toOrgUnitName: nameFromMap(maps.orgUnitNames, toOrgUnitId),
    toPositionName: nameFromMap(maps.positionNames, toPositionId),
    rate: (payload.employment_rate as number | string | null | undefined) ?? null,
    toRate:
      (payload.to_rate as number | string | null | undefined) ??
      (payload.to_employment_rate as number | string | null | undefined) ??
      null,
    concurrentRate: (payload.concurrent_rate as number | string | null | undefined) ?? null,
    remainingRate: (payload.remaining_rate as number | string | null | undefined) ?? null,
    totalRate: (payload.total_rate as number | string | null | undefined) ?? null,
    terminationReason: optionalString(payload.termination_reason),
    payload,
  };
}

function itemEditorialTexts(
  editorial: PersonnelOrderEditorialState | null | undefined,
  itemId: number,
): { body: LocalizedText | null; basis: LocalizedText | null } {
  const group = editorial?.items?.find((row) => row.order_item_id === itemId);
  return {
    body: pickEffectiveByLocale(group?.blocks, "body"),
    basis: pickEffectiveByLocale(group?.blocks, "basis"),
  };
}

export function buildPersonnelOrderPrintViewModel(
  detail: PersonnelOrderDetailResponse,
  maps: PersonnelOrderPrintNameMaps = {},
): PersonnelOrderPrintViewModel {
  const order = detail.order;
  const editorial = maps.editorial ?? null;
  const { title, preamble, closing } = pickLocalizedTexts(detail, editorial);

  const basis: LocalizedText[] = [];
  const legal = optionalString(order.legal_basis_article);
  const summary = optionalString(order.basis_summary);
  if (legal) basis.push(localizedFromSingle(legal));
  if (summary && summary !== legal) basis.push(localizedFromSingle(summary));

  const activeItems = (detail.items || []).filter(
    (item) => String(item.item_status || "").toUpperCase() !== "VOIDED",
  );

  const items: PersonnelOrderPrintItemViewModel[] = activeItems.map((item) => {
    const editorialTexts = itemEditorialTexts(editorial, item.item_id);
    if (editorialTexts.basis) {
      const already = basis.some(
        (entry) =>
          (entry.kk && entry.kk === editorialTexts.basis?.kk) ||
          (entry.ru && entry.ru === editorialTexts.basis?.ru),
      );
      if (!already) basis.push(editorialTexts.basis);
    }
    return {
      itemId: item.item_id,
      itemNumber: item.item_number,
      itemTypeCode: item.item_type_code,
      employeeId: item.employee_id ?? null,
      employeeName: optionalString(item.employee_name),
      effectiveDate: optionalString(item.effective_date),
      context: buildItemContext(item, maps),
      body: editorialTexts.body,
      basis: editorialTexts.basis,
    };
  });

  const seenEmployees = new Set<string>();
  const acknowledgements: PersonnelOrderPrintViewModel["acknowledgements"] = [];
  for (const item of items) {
    const key = item.employeeId != null ? `id:${item.employeeId}` : `name:${item.employeeName || ""}`;
    if (seenEmployees.has(key)) continue;
    seenEmployees.add(key);
    if (!item.employeeName && item.employeeId == null) continue;
    acknowledgements.push({
      employeeId: item.employeeId,
      employeeName: item.employeeName,
    });
  }

  const signatoryFio = optionalString(order.signed_by_name);
  const signatoryPosition = resolveSignatoryPosition(
    optionalString(order.signed_by_position),
    maps,
  );

  return {
    orderId: order.order_id,
    orderNumber: optionalString(order.order_number),
    orderDate: optionalString(order.order_date),
    status: order.status,
    statusMark: resolveStatusMark(order.status),
    organization: localizedText(maps.organizationNameKk, maps.organizationName),
    title,
    preamble,
    closing,
    documentTypeCode: order.order_type_code,
    placeOfIssue: localizedText(
      "Астана қ.",
      "г. Астана",
    ),
    items,
    basis,
    signatory: {
      position: signatoryPosition,
      fio: signatoryFio,
    },
    acknowledgements,
  };
}

/** Collect directory IDs needed to enrich print names from item payloads. */
export function collectPersonnelOrderPrintLookupIds(detail: PersonnelOrderDetailResponse): {
  orgUnitIds: number[];
  positionIds: number[];
} {
  const orgUnitIds = new Set<number>();
  const positionIds = new Set<number>();
  for (const item of detail.items || []) {
    const payload = item.payload || {};
    for (const key of ["org_unit_id", "to_org_unit_id"] as const) {
      const id = optionalNumber(payload[key]);
      if (id != null) orgUnitIds.add(id);
    }
    const itemOrg = optionalNumber(item.org_unit_id);
    if (itemOrg != null) orgUnitIds.add(itemOrg);
    for (const key of ["position_id", "to_position_id"] as const) {
      const id = optionalNumber(payload[key]);
      if (id != null) positionIds.add(id);
    }
  }
  return {
    orgUnitIds: [...orgUnitIds],
    positionIds: [...positionIds],
  };
}
