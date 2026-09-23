import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import PersonnelOrderDocumentView from "./PersonnelOrderDocumentView";
import { renderPersonnelOrderDocument } from "./personnelOrderDocumentTemplates";
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
  it("renders both independent language templates and combines transfer with concurrent duty in one point", () => {
    const order = detail([
      {
        item_id: 1, order_id: 104, item_number: 1, item_type_code: "TRANSFER", item_status: "ACTIVE", employee_id: null, employee_name: null, effective_date: "2026-02-01",
        payload: {
          employee: { name: { canonical: "Ару Мұратқызы Амантай" } },
          from_assignment: { unit: { kk: "терапия және паллиативтік көмек бөлімшесінің А блогы" }, position: { kk: "мейіргер" }, rate: "1.0" },
          to_assignment: { unit: { kk: "қабылдау бөлімшесі" }, position: { kk: "күндізгі мейіргері" }, rate: "1.0" },
          legal_basis: "Қазақстан Республикасының Еңбек Кодексінің 38-бабы", basis_ids: ["application"],
        },
      },
      {
        item_id: 2, order_id: 104, item_number: 2, item_type_code: "CONCURRENT_DUTY_START", item_status: "ACTIVE", employee_id: null, employee_name: null, effective_date: "2026-02-01",
        payload: { assignment: { unit: { kk: "қабылдау бөлімшесі" }, position: { kk: "күндізгі мейіргері" }, rate: "0.5" }, basis_ids: ["application"] },
      },
    ], application);

    const kk = renderPersonnelOrderDocument(order, "kk");
    const ru = renderPersonnelOrderDocument(order, "ru");
    expect(kk?.points).toHaveLength(1);
    expect(kk?.points[0].text).toContain("тұрақты ауыстырылсын");
    expect(kk?.points[0].text).toContain("қоса атқаруға рұқсат");
    expect(kk?.points[0].basis).toEqual(["Қызметкердің жеке өтініші"]);
    expect(ru?.title).toBe("О постоянном переводе и совмещении должностей");
    expect(ru?.preamble).toBe("В соответствии со статьёй 38 Трудового кодекса Республики Казахстан");
    expect(ru?.points[0].text).toBe("Медицинскую сестру блока А отделения терапии и паллиативной помощи Ару Мұратқызы Амантай с 1 февраля 2026 года перевести на должность медицинской сестры приёмного отделения на 1,0 ставки и разрешить ей совмещение должности медицинской сестры этого же отделения на 0,5 ставки.");

    render(<PersonnelOrderDocumentView detail={order} language="ru" />);
    expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("ПРИКАЗЫВАЮ:");
    expect(screen.getByTestId("personnel-order-document")).toHaveTextContent("Основание: Личное заявление работника.");
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
});
