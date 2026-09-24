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
      order_id: 405,
      order_number: "1336-ж",
      order_date: "2026-02-01",
      order_type_code: "TRANSFER",
      order_class: "PERSONNEL",
      status: "DRAFT",
      source_mode: "PAPER",
      created_by: 1,
    },
    items: [{
      item_id: 399,
      order_id: 405,
      item_number: 1,
      item_type_code: "TRANSFER",
      item_status: "ACTIVE",
      employee_id: 77,
      employee_name: "Иванов Иван",
      effective_date: "2026-02-01",
      payload: {
        position_id: 20,
        to_assignment: {
          unit: { ru: "Приемное отделение", kk: "Қабылдау бөлімшесі" },
          position: { ru: "Медсестра", kk: "мейіргер" },
          rate: "1.0",
        },
        position_text_override: { ru: "медбрат", kk: "" },
      },
    }],
    localized_texts: [],
    attachments: [],
    prints: [],
    events: [],
  };
}

function productionEditorialState(): PersonnelOrderEditorialState {
  return {
    order_id: 405,
    order_status: "DRAFT",
    editable: true,
    order_blocks: [],
    items: [{
      order_item_id: 399,
      item_number: 1,
      item_type_code: "TRANSFER",
      basis_required: true,
      blocks: [
        { block_id: 1, scope: "item", order_item_id: 399, locale: "ru", block_type: "body", generated_text: "Перевести Иванова на должность медсестра.", override_text: null, effective_text: "Перевести Иванова на должность медсестра.", review_status: "CURRENT", editable: true, revision: 1 },
        { block_id: 2, scope: "item", order_item_id: 399, locale: "kk", block_type: "body", generated_text: "Автоматты мәтін", override_text: "мейіргер", effective_text: "мейіргер", review_status: "CURRENT", editable: true, revision: 1 },
      ],
    }],
  };
}

function editorial(ruBody: string, kkBody: string): PersonnelOrderEditorialState {
  return {
    order_id: 405,
    order_status: "DRAFT",
    editable: true,
    order_blocks: [],
    items: [{
      order_item_id: 399,
      item_number: 1,
      item_type_code: "HIRE",
      basis_required: false,
      blocks: [
        { block_id: 1, scope: "item", order_item_id: 399, locale: "ru", block_type: "body", generated_text: "AUTO RU", override_text: ruBody, effective_text: ruBody, review_status: "CURRENT", editable: true, revision: 2 },
        { block_id: 2, scope: "item", order_item_id: 399, locale: "kk", block_type: "body", generated_text: "AUTO KK", override_text: kkBody, effective_text: kkBody, review_status: "CURRENT", editable: true, revision: 2 },
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

  it("rehydrates the production GET payload into ru document and print while kk manual body stays isolated", () => {
    const reread = structuredClone(detailWithPositionOverride());
    const state = productionEditorialState();
    const before = {
      employeeId: reread.items[0]?.employee_id,
      positionId: reread.items[0]?.payload.position_id,
      assignment: structuredClone(reread.items[0]?.payload.to_assignment),
    };

    expect(renderPersonnelOrderDocument(reread, "ru", state)?.points[0]?.text).toContain("медбрат");
    expect(renderPersonnelOrderDocument(reread, "kk", state)?.points[0]?.text).toBe("мейіргер");

    const model = buildPersonnelOrderPrintViewModel(reread, {
      positionNames: { 20: "Медсестра" },
      editorial: state,
    });
    expect(model.items[0]?.context.positionName).toEqual({ ru: "медбрат" });
    const ruPrintHtml = buildPersonnelOrderPrintDocumentHtml(model, "ru");
    expect(ruPrintHtml).toContain("медбрат");
    expect(ruPrintHtml).not.toContain("мейіргер");
    const kkPrintHtml = buildPersonnelOrderPrintDocumentHtml(model, "kk");
    expect(kkPrintHtml).toContain("мейіргер");
    expect({
      employeeId: reread.items[0]?.employee_id,
      positionId: reread.items[0]?.payload.position_id,
      assignment: reread.items[0]?.payload.to_assignment,
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

  it("renders every termination item in item order and adds one shared accounting point", () => {
    const order = detailWithPositionOverride();
    order.order.order_type_code = "TERMINATION";
    order.items = [1, 2, 3].map((number) => ({
      ...order.items[0]!, item_id: 500 + number, item_number: number,
      item_type_code: "TERMINATION", employee_id: number,
      employee_name: `Сотрудник ${number}`, effective_date: "2026-02-01",
      payload: { source_employee_name: `Сотрудник ${number}`, basis_ids: ["application"] },
    }));
    const screen = renderPersonnelOrderDocument(order, "ru");
    expect(screen?.points).toHaveLength(4);
    expect(screen?.points.map((point) => point.text).join(" ")).toContain("Сотрудник 3");
    expect(screen?.points[3]?.text).toBe("Бухгалтерии произвести расчёт за неиспользованные дни отпуска увольняемых работников.");
    const print = buildPersonnelOrderPrintViewModel(order);
    expect(print.items.map((item) => item.itemNumber)).toEqual([1, 2, 3, 4]);
    expect(buildPersonnelOrderPrintDocumentHtml(print, "ru")).toContain("увольняемых работников");
  });

});
