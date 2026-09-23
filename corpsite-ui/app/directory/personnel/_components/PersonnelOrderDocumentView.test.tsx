import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import PersonnelOrderDocumentView from "./PersonnelOrderDocumentView";
import { renderPersonnelOrderDocument, resolvePersonnelOrderTemplateKey } from "./personnelOrderDocumentTemplates";
import type { PersonnelOrderDetailResponse } from "../_lib/personnelOrdersApi.client";

function detail(items: unknown[], basisDocuments: unknown[]) {
  return {
    order: {
      order_id: 104,
      order_number: "104",
      order_date: "2026-01-30",
      order_type_code: "COMPOSITE",
      order_class: "PERSONNEL",
      status: "DRAFT",
      source_mode: "DIGITAL",
      signed_by_name: "М. Тулеутаев",
      signed_by_position: "Директор",
      created_by: 1,
      storage_json: { basis_documents: basisDocuments },
    },
    localized_texts: [],
    items,
    attachments: [],
    prints: [],
    events: [],
  } as unknown as PersonnelOrderDetailResponse;
}

const application = [{ basis_id: "application", document_type: "EMPLOYEE_APPLICATION" }];

afterEach(cleanup);

describe("PersonnelOrderDocumentView", () => {
  it("resolves approved templates from actions, not control-order numbers", () => {
    for (const [type, key] of [
      ["HIRE", "personnel.hire.standard"],
      ["TRANSFER", "personnel.transfer.permanent"],
      ["CONCURRENT_DUTY_START", "personnel.concurrent-duty.start"],
      ["TERMINATION", "personnel.termination.employee-initiative-unused-leave"],
    ] as const) {
      const order = detail([{ item_id: 1, item_number: 1, item_type_code: type, payload: {} }], application);
      order.order.order_number = "1336-ж";
      expect(resolvePersonnelOrderTemplateKey(order)).toBe(key);
    }
  });

  it("renders both independent language templates and combines transfer with concurrent duty in one point", () => {
    const order = detail([
      {
        item_id: 1, order_id: 1, item_number: 1, item_type_code: "TRANSFER", item_status: "ACTIVE", employee_id: null, employee_name: null, effective_date: "2026-02-01",
        payload: {
          employee: { name: { canonical: "Ару Мұратқызы Амантай" } },
          from_assignment: { unit: { kk: "терапия және паллиативтік көмек бөлімшесінің А блогы" }, position: { kk: "мейіргер" }, rate: "1.0" },
          to_assignment: { unit: { kk: "қабылдау бөлімшесі" }, position: { kk: "күндізгі мейіргері" }, rate: "1.0" },
          legal_basis: "Қазақстан Республикасының Еңбек Кодексінің 38-бабы", basis_ids: ["application"],
        },
      },
      {
        item_id: 2, order_id: 1, item_number: 2, item_type_code: "CONCURRENT_DUTY_START", item_status: "ACTIVE", employee_id: null, employee_name: null, effective_date: "2026-02-01",
        payload: { assignment: { unit: { kk: "қабылдау бөлімшесі" }, position: { kk: "күндізгі мейіргері" }, rate: "0.5" }, basis_ids: ["application"] },
      },
    ], application);

    const kk = renderPersonnelOrderDocument(order, "kk");
    const ru = renderPersonnelOrderDocument(order, "ru");
    expect(kk?.points).toHaveLength(1);
    expect(kk?.points[0].text).toContain("тұрақты ауыстырылсын");
    expect(kk?.points[0].text).toContain("қоса атқаруға рұқсат");
    expect(kk?.points[0].basis).toEqual(["Қызметкердің жеке өтініші"]);
    expect(ru?.title).toBe("О переводе и совмещении должностей");
    expect(ru?.preamble).toBe("В соответствии со статьёй 38 Трудового кодекса Республики Казахстан");
    expect(ru?.points[0].text).toBe("Перевести сотрудника Ару Мұратқызы Амантай с 1 февраля 2026 года на должность медицинская сестра (приемное отделение) с оплатой 1.0 ставки и разрешить сотруднику Ару Мұратқызы Амантай совмещение обязанностей по должности медицинская сестра (приемное отделение) с оплатой 0.5 ставки.");

    render(<PersonnelOrderDocumentView detail={order} language="ru" />);
    expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("ПРИКАЗЫВАЮ:");
    expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("Основание: Личное заявление работника.");
  });

  it("renders the 1336-ж transfer vocabulary and real signatory in both languages", () => {
    const order = detail([{
      item_id: 1, order_id: 4831, item_number: 1, item_type_code: "TRANSFER", item_status: "ACTIVE", employee_id: null, employee_name: null, effective_date: "2026-02-01",
      payload: { employee: { name: { canonical: "А. Қызметкер" } }, assignment: { unit: { kk: "Реанимация", ru: "Реанимация" }, position: { kk: "Медсестра", ru: "Медсестра" }, rate: "1.0" }, basis_ids: ["application"] },
    }], application);
    order.order.order_number = "1336-ж";
    expect(renderPersonnelOrderDocument(order, "kk")?.title).toBe("Ауыстыру туралы");
    expect(renderPersonnelOrderDocument(order, "kk")?.points[0].text).toContain("мейіргер");
    expect(renderPersonnelOrderDocument(order, "kk")?.points[0].text).not.toContain("Медсестра");
    expect(renderPersonnelOrderDocument(order, "ru")?.title).toBe("О переводе");
    render(<PersonnelOrderDocumentView detail={order} language="ru" />);
    const document = screen.getByTestId("personnel-order-document");
    expect(document).toHaveTextContent("Директор");
    expect(document).not.toHaveTextContent("Подписант");
    render(<PersonnelOrderDocumentView detail={order} language="kk" />);
    expect(screen.getAllByTestId("personnel-order-document")[1]).toHaveTextContent("Директоры");
    order.order.signed_by_position = "ACTING_DIRECTOR";
    render(<PersonnelOrderDocumentView detail={order} language="kk" />);
    render(<PersonnelOrderDocumentView detail={order} language="ru" />);
    const documents = screen.getAllByTestId("personnel-order-document");
    expect(documents[2]).toHaveTextContent("Директордың міндетін атқарушы");
    expect(documents[3]).toHaveTextContent("И. о. директора");
  });

  it("renders termination, accounting instruction, and its basis", () => {
    const order = detail([{
      item_id: 1, order_id: 332, item_number: 1, item_type_code: "TERMINATION", item_status: "ACTIVE", employee_id: null, employee_name: null, effective_date: "2026-04-03",
      payload: {
        employee: { name: { canonical: "Айжан Солтан" } },
        legal_basis: "Қазақстан Республикасы Еңбек Кодексінің 49-бабының 5-тармағы және 56-бабының 2-тармағы",
        unused_leave_days: 6, basis_ids: ["application"],
      },
    }], application);

    render(<PersonnelOrderDocumentView detail={order} language="kk" />);
    const document = screen.getByTestId("personnel-order-document");
    expect(document).toHaveTextContent("49-бабының 5-тармағына");
    expect(document.querySelectorAll("ol > li")).toHaveLength(2);
    expect(document).toHaveTextContent("6 күнтізбелік күніне есеп айырысу жүргізсін");
    expect(document).not.toHaveTextContent("Қосымша өкімдер");
    expect(document).toHaveTextContent("Негіз: Қызметкердің жеке өтініші.");
  });

  it("uses the universal Russian leave instruction when days are not confirmed", () => {
    const order = detail([{
      item_id: 1, order_id: 4826, item_number: 1, item_type_code: "TERMINATION", item_status: "ACTIVE", employee_id: null, employee_name: "Сотрудник", effective_date: "2026-02-01",
      payload: { basis_ids: ["application"] },
    }], application);
    const text = renderPersonnelOrderDocument(order, "ru")?.points.map((point) => point.text).join(" ");
    expect(text).toContain("Бухгалтерии произвести расчёт за неиспользованные дни отпуска.");
    expect(text).not.toContain("календарных дней");
    expect(text).not.toContain("—");
  });

  it("uses Russian employee and assignment forms for concurrent duty", () => {
    const order = detail([{
      item_id: 1, order_id: 4845, item_number: 1, item_type_code: "CONCURRENT_DUTY_START", item_status: "ACTIVE", employee_id: null, employee_name: "Рудина Надежда Викторовна", effective_date: "2026-03-02",
      payload: { assignment: { position: { ru: "Санитар" }, unit: { ru: "Приемное" }, rate: "1.0" }, basis_ids: ["application"] },
    }], application);
    expect(renderPersonnelOrderDocument(order, "ru")?.points[0]?.text).toBe(
      "Разрешить сотруднику Рудина Надежда Викторовна с 2 марта 2026 года совмещение обязанностей по должности санитар (приемное отделение) с оплатой 1.0 ставки.",
    );
  });
});
