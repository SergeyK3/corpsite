import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import PersonnelOrderDocumentView from "./PersonnelOrderDocumentView";
import { renderPersonnelOrderDocument } from "./personnelOrderDocumentTemplates";
import { buildPersonnelOrderPrintDocumentHtml } from "../_lib/personnelOrderPrintDocumentHtml";
import { buildPersonnelOrderPrintViewModel } from "../_lib/personnelOrderPrintViewModel";
import type {
  PersonnelOrderDetailResponse,
  PersonnelOrderEditorialState,
} from "../_lib/personnelOrdersApi.client";

function detailWithPositionOverride(): PersonnelOrderDetailResponse {
  return {
    order: {
      order_id: 1336,
      order_number: "1336-ж",
      order_date: "2026-02-01",
      order_type_code: "HIRE",
      order_class: "PERSONNEL",
      status: "DRAFT",
      source_mode: "PAPER",
      created_by: 1,
    },
    items: [{
      item_id: 44,
      order_id: 1336,
      item_number: 1,
      item_type_code: "HIRE",
      item_status: "ACTIVE",
      employee_id: 77,
      employee_name: "Иванов Иван",
      effective_date: "2026-02-01",
      payload: {
        position_id: 20,
        assignment: {
          unit: { ru: "Приемное отделение", kk: "Қабылдау бөлімшесі" },
          position: { ru: "Медсестра", kk: "мейіргер" },
          rate: "1.0",
        },
        position_text_override: { ru: "медицинский брат", kk: "мейіргер" },
      },
    }],
    localized_texts: [],
    attachments: [],
    prints: [],
    events: [],
  };
}

function editorial(ruBody: string, kkBody: string): PersonnelOrderEditorialState {
  return {
    order_id: 1336,
    order_status: "DRAFT",
    editable: true,
    order_blocks: [],
    items: [{
      order_item_id: 44,
      item_number: 1,
      item_type_code: "HIRE",
      basis_required: false,
      blocks: [
        { block_id: 1, scope: "item", order_item_id: 44, locale: "ru", block_type: "body", effective_text: ruBody, review_status: "CURRENT", editable: true, revision: 2 },
        { block_id: 2, scope: "item", order_item_id: 44, locale: "kk", block_type: "body", effective_text: kkBody, review_status: "CURRENT", editable: true, revision: 2 },
      ],
    }],
  };
}

afterEach(cleanup);

describe("localized personnel order editing", () => {
  it("shows saved locale-specific editorial bodies in the document and keeps the other locale intact", () => {
    const order = detailWithPositionOverride();
    const state = editorial("РУЧНОЙ ТЕКСТ RU", "ҚОЛМЕН МӘТІН KK");

    expect(renderPersonnelOrderDocument(order, "ru", state)?.points[0]?.text).toBe("РУЧНОЙ ТЕКСТ RU");
    expect(renderPersonnelOrderDocument(order, "kk", state)?.points[0]?.text).toBe("ҚОЛМЕН МӘТІН KK");
    render(<PersonnelOrderDocumentView detail={order} language="ru" editorial={state} />);
    expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("РУЧНОЙ ТЕКСТ RU");
  });

  it("uses persisted position overrides in screen and print without changing employment identifiers", () => {
    const reread = structuredClone(detailWithPositionOverride());
    const before = {
      employeeId: reread.items[0]?.employee_id,
      positionId: reread.items[0]?.payload.position_id,
      assignment: structuredClone(reread.items[0]?.payload.assignment),
    };

    expect(renderPersonnelOrderDocument(reread, "ru")?.points[0]?.text).toContain("медицинский брат");
    expect(renderPersonnelOrderDocument(reread, "kk")?.points[0]?.text).toContain("мейіргер");

    const model = buildPersonnelOrderPrintViewModel(reread, {
      positionNames: { 20: "Медсестра" },
    });
    expect(model.items[0]?.context.positionName).toEqual({ ru: "медицинский брат", kk: "мейіргер" });
    const printHtml = buildPersonnelOrderPrintDocumentHtml(model, "kk-ru");
    expect(printHtml).toContain("медицинский брат");
    expect(printHtml).toContain("мейіргер");
    expect({
      employeeId: reread.items[0]?.employee_id,
      positionId: reread.items[0]?.payload.position_id,
      assignment: reread.items[0]?.payload.assignment,
    }).toEqual(before);
  });

  it("gives a manual editorial body priority over a position override in document and print", () => {
    const order = detailWithPositionOverride();
    const state = editorial("РУЧНОЙ ТЕКСТ ВЫШЕ ДОЛЖНОСТИ", "ҚОЛМЕН МӘТІН");

    expect(renderPersonnelOrderDocument(order, "ru", state)?.points[0]?.text).toBe("РУЧНОЙ ТЕКСТ ВЫШЕ ДОЛЖНОСТИ");
    const model = buildPersonnelOrderPrintViewModel(order, { editorial: state });
    expect(model.items[0]?.body?.ru).toBe("РУЧНОЙ ТЕКСТ ВЫШЕ ДОЛЖНОСТИ");
    const printHtml = buildPersonnelOrderPrintDocumentHtml(model, "ru");
    expect(printHtml).toContain("РУЧНОЙ ТЕКСТ ВЫШЕ ДОЛЖНОСТИ");
  });
});
