import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelOrderPrintDocument from "./PersonnelOrderPrintDocument";
import PersonnelOrderPrintLanguageDialog from "./PersonnelOrderPrintLanguageDialog";
import PersonnelOrderPrintToolbar from "./PersonnelOrderPrintToolbar";
import { buildPersonnelOrderPrintViewModel } from "../../_lib/personnelOrderPrintViewModel";
import type { PersonnelOrderDetailResponse } from "../../_lib/personnelOrdersApi.client";

afterEach(() => {
  cleanup();
});

const detail: PersonnelOrderDetailResponse = {
  order: {
    order_id: 42,
    order_number: "12-К",
    order_date: "2026-07-10",
    order_type_code: "HIRE",
    order_class: "SIMPLE",
    status: "DRAFT",
    source_mode: "PAPER",
    legal_basis_article: "ст. 33 ТК РК",
    signed_by_name: "Иванов И.И.",
    signed_by_position: "Директор",
    created_by: 1,
  },
  items: [
    {
      item_id: 1,
      order_id: 42,
      item_number: 1,
      item_type_code: "HIRE",
      item_status: "ACTIVE",
      employee_id: 7,
      employee_name: "Петрова Анна",
      effective_date: "2026-07-15",
      payload: { org_unit_id: 10, position_id: 20, employment_rate: 1 },
    },
  ],
  localized_texts: [
    {
      localized_text_id: 1,
      order_id: 42,
      locale: "ru",
      title: "О приёме на работу",
      preamble: null,
      body_text: null,
      render_version: 1,
      is_authoritative: true,
    },
  ],
  attachments: [],
  prints: [],
  events: [],
};

describe("PersonnelOrderPrintLanguageDialog", () => {
  it("confirms selected language for preview and pdf actions", () => {
    const onConfirm = vi.fn();
    render(
      <PersonnelOrderPrintLanguageDialog open onClose={vi.fn()} onConfirm={onConfirm} />,
    );
    fireEvent.click(screen.getByLabelText("Қазақша"));
    fireEvent.click(screen.getByTestId("personnel-order-print-open"));
    expect(onConfirm).toHaveBeenCalledWith("kk", "preview");

    fireEvent.click(screen.getByTestId("personnel-order-pdf-open"));
    expect(onConfirm).toHaveBeenCalledWith("kk", "pdf");
  });
});

describe("PersonnelOrderPrintToolbar", () => {
  it("hides with print:hidden and keeps UI font classes on controls", () => {
    render(
      <PersonnelOrderPrintToolbar
        backHref="/directory/personnel/orders?order_id=42"
        language="ru"
        onLanguageChange={vi.fn()}
      />,
    );
    const toolbar = screen.getByTestId("personnel-order-print-toolbar");
    expect(toolbar.className).toContain("print:hidden");
    expect(toolbar.className).not.toContain("personnel-order-print-document");
    expect(screen.getByTestId("personnel-order-print-button").className).toContain("text-sm");
    expect(screen.getByTestId("personnel-order-print-button")).toHaveTextContent("Печать HTML");

    const hint = screen.getByTestId("personnel-order-print-headers-hint");
    expect(hint).toHaveTextContent("Колонтитулы");
    expect(hint).toHaveTextContent("PDF");
    expect(hint.className).toContain("print:hidden");
  });
});

describe("PersonnelOrderPrintDocument", () => {
  it("keeps acknowledgement initials and executor in RU and KK without a recorded date", () => {
    const model = buildPersonnelOrderPrintViewModel({ ...detail, acknowledgements: [] }, {});
    for (const language of ["ru", "kk"] as const) {
      const { unmount } = render(<PersonnelOrderPrintDocument model={model} language={language} />);
      const acknowledgement = screen.getByTestId("personnel-order-print-acknowledgement");
      expect(acknowledgement).toHaveTextContent(language === "ru" ? "Петрова А." : "А. Петрова");
      expect(acknowledgement.innerHTML).toContain(
        language === "ru"
          ? "___________________&nbsp;&nbsp;Петрова А."
          : "___________________&nbsp;&nbsp;А. Петрова",
      );
      expect(screen.getByTestId("personnel-order-print-executor")).toHaveTextContent("М. Умерзакова");
      unmount();
    }
  });

  it("renders one localized acknowledgement and executor for a repeated subject", () => {
    const repeated = {
      ...detail,
      items: [...detail.items, { ...detail.items[0], item_id: 2, item_number: 2 }],
      acknowledgements: [{ acknowledgement_event_id: 1, order_id: 42, employee_id: 7, event_type: "RECORDED", acknowledged_on: "2026-07-12", created_by_user_id: 1 }],
    };
    render(<PersonnelOrderPrintDocument model={buildPersonnelOrderPrintViewModel(repeated, {})} language="ru" />);
    const ack = screen.getByTestId("personnel-order-print-acknowledgement");
    expect(ack.querySelectorAll(".personnel-order-print-ack-row")).toHaveLength(1);
    expect(ack).toHaveTextContent("Петрова А.");
    expect(ack).toHaveTextContent("12.07.2026");
    expect(screen.getByTestId("personnel-order-print-executor")).toHaveTextContent("Исполнитель: М. Умерзакова");
    expect(screen.getByTestId("personnel-order-print-items")).toHaveTextContent("Стаж работы ещё не определён.");
  });

  it("uses scoped print document class without Times on toolbar", () => {
    const model = buildPersonnelOrderPrintViewModel(detail, { organizationName: "ММЦ" });
    render(
      <>
        <PersonnelOrderPrintToolbar
          backHref="/directory/personnel/orders?order_id=42"
          language="ru"
          onLanguageChange={vi.fn()}
        />
        <PersonnelOrderPrintDocument model={model} language="ru" />
      </>,
    );
    const doc = screen.getByTestId("personnel-order-print-document");
    expect(doc.className).toContain("personnel-order-print-document");
    expect(screen.getByTestId("personnel-order-print-toolbar").className).not.toContain(
      "personnel-order-print-document",
    );
  });

  it("renders core blocks and draft watermark for Russian", () => {
    const model = buildPersonnelOrderPrintViewModel(detail, {
      organizationName: "ММЦ",
      orgUnitNames: { 10: "Хирургия" },
      positionNames: { 20: "Врач" },
    });
    render(<PersonnelOrderPrintDocument model={model} language="ru" />);

    expect(screen.getByTestId("personnel-order-print-document")).toHaveAttribute(
      "data-language",
      "ru",
    );
    expect(screen.getByTestId("personnel-order-print-header")).toHaveTextContent("12-К");
    expect(screen.getByTestId("personnel-order-print-header")).toHaveTextContent("О приёме на работу");
    expect(screen.getByTestId("personnel-order-print-header")).toHaveTextContent("ПРИКАЗ");
    expect(screen.getByTestId("personnel-order-print-header")).not.toHaveTextContent("БҰЙРЫҚ");
    expect(screen.getByTestId("personnel-order-print-items")).toHaveTextContent("ПРИКАЗЫВАЮ");
    expect(screen.getByTestId("personnel-order-print-items")).not.toHaveTextContent("БҰЙЫРАМЫН");
    expect(screen.getByTestId("personnel-order-print-basis")).toHaveTextContent("ст. 33 ТК РК");
    expect(screen.getByTestId("personnel-order-print-signature")).toHaveTextContent("Директор");
    expect(screen.getByTestId("personnel-order-print-signature")).toHaveTextContent("Иванов И.И.");
    expect(screen.getByTestId("personnel-order-print-signature")).not.toHaveTextContent("Руководитель");
    expect(screen.getByTestId("personnel-order-print-signature")).not.toHaveTextContent("Подпись");
    expect(screen.getByTestId("personnel-order-print-acknowledgement")).toHaveTextContent(
      "Петрова А.",
    );
    expect(screen.getByTestId("personnel-order-print-acknowledgement")).not.toHaveTextContent("Ф.И.О.");
    expect(screen.getByTestId("personnel-order-print-acknowledgement")).not.toHaveTextContent("Т.А.Ә.");
    expect(screen.getByTestId("personnel-order-print-status-mark")).toHaveAttribute(
      "data-status-mark",
      "draft",
    );
    expect(screen.getByTestId("personnel-order-print-status-mark")).toHaveTextContent("ПРОЕКТ");
    expect(screen.getByTestId("personnel-order-print-status-mark")).not.toHaveTextContent(
      "НЕ ДЛЯ ПОДШИВКИ",
    );
    expect(screen.getByTestId("personnel-order-print-status-mark")).not.toHaveTextContent(
      "МАКЕТ",
    );
  });

  it("renders ready-for-signature watermark as НА ПОДПИСЬ", () => {
    const model = buildPersonnelOrderPrintViewModel({
      ...detail,
      order: { ...detail.order, status: "READY_FOR_SIGNATURE" },
    });
    render(<PersonnelOrderPrintDocument model={model} language="ru" />);
    expect(screen.getByTestId("personnel-order-print-status-mark")).toHaveAttribute(
      "data-status-mark",
      "unsigned",
    );
    expect(screen.getByTestId("personnel-order-print-status-mark")).toHaveTextContent("НА ПОДПИСЬ");
    expect(screen.getByTestId("personnel-order-print-status-mark")).not.toHaveTextContent(
      "МАКЕТ ПРИКАЗА",
    );
    expect(screen.getByTestId("personnel-order-print-status-mark")).not.toHaveTextContent(
      "НЕ ПОДПИСАН",
    );
  });

  it("renders bilingual ready-for-signature watermark", () => {
    const model = buildPersonnelOrderPrintViewModel({
      ...detail,
      order: { ...detail.order, status: "READY_FOR_SIGNATURE" },
    });
    render(<PersonnelOrderPrintDocument model={model} language="kk-ru" />);
    const mark = screen.getByTestId("personnel-order-print-status-mark");
    expect(mark).toHaveTextContent("ҚОЛ ҚОЮҒА");
    expect(mark).toHaveTextContent("НА ПОДПИСЬ");
    expect(mark).not.toHaveTextContent("МАКЕТ");
  });

  it("hides watermark for SIGNED and REGISTERED", () => {
    for (const status of ["SIGNED", "REGISTERED"] as const) {
      const model = buildPersonnelOrderPrintViewModel({
        ...detail,
        order: { ...detail.order, status },
      });
      const { unmount } = render(<PersonnelOrderPrintDocument model={model} language="ru" />);
      expect(screen.queryByTestId("personnel-order-print-status-mark")).not.toBeInTheDocument();
      unmount();
    }
  });

  it("renders bilingual headings once for number and no draft mark for registered order", () => {
    const model = buildPersonnelOrderPrintViewModel(
      {
        ...detail,
        order: { ...detail.order, status: "REGISTERED" },
      },
      { organizationName: "ММЦ" },
    );
    render(<PersonnelOrderPrintDocument model={model} language="kk-ru" />);

    const header = screen.getByTestId("personnel-order-print-header");
    expect(header).toHaveTextContent("БҰЙРЫҚ");
    expect(header).toHaveTextContent("ПРИКАЗ");
    expect(header.textContent?.split("12-К").length).toBe(2);
    expect(screen.queryByTestId("personnel-order-print-status-mark")).not.toBeInTheDocument();

    const ack = screen.getByTestId("personnel-order-print-acknowledgement");
    expect(ack).toHaveTextContent("Бұйрықпен таныстым:");
    expect(ack).toHaveTextContent("С приказом ознакомлен(а):");
    expect(ack.querySelectorAll(".personnel-order-print-ack-row")).toHaveLength(1);
  });

  it("renders cancelled watermark for voided order", () => {
    const model = buildPersonnelOrderPrintViewModel({
      ...detail,
      order: { ...detail.order, status: "VOIDED" },
    });
    render(<PersonnelOrderPrintDocument model={model} language="ru" />);
    expect(screen.getByTestId("personnel-order-print-status-mark")).toHaveAttribute(
      "data-status-mark",
      "cancelled",
    );
    expect(screen.getByTestId("personnel-order-print-status-mark")).toHaveTextContent("АННУЛИРОВАН");
  });

  it("hides empty basis and uses composite document title instead of technical type", () => {
    const model = buildPersonnelOrderPrintViewModel({
      ...detail,
      order: {
        ...detail.order,
        order_type_code: "COMPOSITE",
        legal_basis_article: null,
        basis_summary: null,
        status: "SIGNED",
      },
      localized_texts: [],
    });
    render(<PersonnelOrderPrintDocument model={model} language="ru" />);
    expect(screen.queryByTestId("personnel-order-print-basis")).not.toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-print-header")).toHaveTextContent(
      "О кадровых изменениях",
    );
    expect(screen.getByTestId("personnel-order-print-header")).not.toHaveTextContent("Составной");
    expect(screen.getByTestId("personnel-order-print-header")).not.toHaveTextContent("COMPOSITE");
    expect(screen.queryByTestId("personnel-order-print-status-mark")).not.toBeInTheDocument();
  });

  it("does not hardcode Руководитель when position comes from order data", () => {
    const model = buildPersonnelOrderPrintViewModel({
      ...detail,
      order: { ...detail.order, signed_by_position: "Директор", status: "SIGNED" },
    });
    render(<PersonnelOrderPrintDocument model={model} language="kk" />);
    expect(screen.getByTestId("personnel-order-print-signature")).toHaveTextContent("Директор");
    expect(screen.getByTestId("personnel-order-print-signature")).not.toHaveTextContent("Руководитель");
    expect(screen.getByTestId("personnel-order-print-signature")).not.toHaveTextContent("Қолы");
  });

  it("renders signatory row as position, signature line, then FIO", () => {
    const model = buildPersonnelOrderPrintViewModel(detail, {
      organizationName: "ММЦ",
    });
    render(<PersonnelOrderPrintDocument model={model} language="ru" />);

    const signature = screen.getByTestId("personnel-order-print-signature");
    const grid = signature.querySelector(".personnel-order-print-signature-grid");
    expect(grid).not.toBeNull();
    const children = Array.from(grid!.children).map((node) => node.className);
    expect(children[0]).toContain("personnel-order-print-signature-position");
    expect(children[1]).toContain("personnel-order-print-signature-line");
    expect(children[2]).toContain("personnel-order-print-signature-fio");
    expect(screen.getByTestId("personnel-order-print-signature-position")).toHaveTextContent("Директор");
    expect(screen.getByTestId("personnel-order-print-signature-line")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-print-signature-fio")).toHaveTextContent("Иванов И.И.");
  });

  it("renders editorial closing before tail date and signature block", () => {
    const model = buildPersonnelOrderPrintViewModel(detail, {
      organizationName: "ММЦ",
      editorial: {
        order_id: 42,
        order_status: "DRAFT",
        editable: true,
        order_blocks: [
          {
            block_id: 50,
            scope: "order",
            locale: "ru",
            block_type: "closing",
            effective_text: "Контроль за исполнением приказа оставляю за собой.",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
        ],
        items: [],
      },
    });
    render(<PersonnelOrderPrintDocument model={model} language="ru" />);
    expect(screen.getByTestId("personnel-order-print-closing")).toHaveTextContent(
      "Контроль за исполнением приказа оставляю за собой.",
    );
    expect(screen.getByTestId("personnel-order-print-tail-date")).toHaveTextContent("10 июля 2026 года");
    expect(screen.getByTestId("personnel-order-print-signature")).toHaveTextContent("Директор");
  });

  it("moves an embedded legacy directive out of the preamble and centers it once", () => {
    const model = buildPersonnelOrderPrintViewModel(detail, {
      organizationName: "ММЦ",
      editorial: {
        order_id: 42,
        order_status: "DRAFT",
        editable: true,
        order_blocks: [
          {
            block_id: 2,
            scope: "order",
            locale: "ru",
            block_type: "preamble",
            effective_text:
              "В соответствии с Трудовым кодексом Республики Казахстан\nПРИКАЗЫВАЮ:",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
        ],
        items: [],
      },
    });
    render(<PersonnelOrderPrintDocument model={model} language="ru" />);
    const items = screen.getByTestId("personnel-order-print-items");
    expect(items).toHaveTextContent("ПРИКАЗЫВАЮ");
    expect(items.querySelectorAll(".personnel-order-print-order-verb")).toHaveLength(1);
    expect(items.querySelectorAll(".personnel-order-print-preamble p")).toHaveLength(1);
  });

  it("renders the childcare-return basis and footer once without removed review blocks", () => {
    const model = buildPersonnelOrderPrintViewModel({
      ...detail,
      order: {
        ...detail.order,
        order_type_code: "RETURN_FROM_CHILDCARE_LEAVE",
        legal_basis_article: null,
        basis_summary: null,
      },
      items: [{
        ...detail.items[0],
        item_type_code: "RETURN_FROM_CHILDCARE_LEAVE",
        employee_name: "Тестова Анна",
        payload: {},
      }],
    }, {
      editorial: {
        order_id: 42,
        order_status: "DRAFT",
        editable: true,
        order_blocks: [{
          block_id: 81, scope: "order", locale: "ru", block_type: "preamble",
          generated_text: "В соответствии с Трудовым кодексом Республики Казахстан\nПРИКАЗЫВАЮ:",
          effective_text: "В соответствии с Трудовым кодексом Республики Казахстан\nПРИКАЗЫВАЮ:",
          review_status: "CURRENT", editable: true, revision: 1,
        }, {
          block_id: 82, scope: "order", locale: "ru", block_type: "closing",
          generated_text: "Контроль за исполнением приказа оставляю за собой.",
          effective_text: "Контроль за исполнением приказа оставляю за собой.",
          review_status: "CURRENT", editable: true, revision: 1,
        }],
        items: [{
          order_item_id: 1, item_number: 1, item_type_code: "RETURN_FROM_CHILDCARE_LEAVE", basis_required: true,
          blocks: [{ block_id: 83, scope: "item", order_item_id: 1, locale: "ru", block_type: "body", generated_text: "Актуальный текст выхода.", effective_text: "Актуальный текст выхода.", review_status: "CURRENT", editable: true, revision: 1 },
            { block_id: 84, scope: "item", order_item_id: 1, locale: "ru", block_type: "basis", generated_text: "Личное заявление.", effective_text: "Личное заявление.", review_status: "CURRENT", editable: true, revision: 1 }],
        }],
      },
    });
    render(<PersonnelOrderPrintDocument model={model} language="ru" />);
    const document = screen.getByTestId("personnel-order-print-document");
    expect(document).toHaveTextContent("Основание: Личное заявление.");
    expect(document).not.toHaveTextContent("Стаж работы ещё не определён.");
    expect(document).not.toHaveTextContent("Контроль за исполнением приказа");
    expect(document.querySelectorAll(".personnel-order-print-order-verb")).toHaveLength(1);
    expect(screen.getByTestId("personnel-order-print-acknowledgement").innerHTML).toContain("___________________&nbsp;&nbsp;Тестова А.");
    expect(screen.getByTestId("personnel-order-print-executor")).toHaveTextContent("Исполнитель: М. Умерзакова");
  });

  it("normalizes a legacy labelled childcare-return basis in RU and KK print", () => {
    const model = buildPersonnelOrderPrintViewModel({
      ...detail,
      order: { ...detail.order, order_type_code: "RETURN_FROM_CHILDCARE_LEAVE" },
      items: [{ ...detail.items[0], item_type_code: "RETURN_FROM_CHILDCARE_LEAVE", employee_name: "Тестов Сотрудник" }],
    }, {
      editorial: {
        order_id: 42,
        order_status: "DRAFT",
        editable: true,
        order_blocks: [{ block_id: 90, scope: "order", locale: "ru", block_type: "closing", generated_text: "Контроль за исполнением приказа оставляю за собой.", effective_text: "Контроль за исполнением приказа оставляю за собой.", review_status: "CURRENT", editable: true, revision: 1 }, { block_id: 91, scope: "order", locale: "kk", block_type: "closing", generated_text: "Бұйрықтың орындалуын бақылауды өзіме қалдырамын.", effective_text: "Бұйрықтың орындалуын бақылауды өзіме қалдырамын.", review_status: "CURRENT", editable: true, revision: 1 }],
        items: [{ order_item_id: 1, item_number: 1, item_type_code: "RETURN_FROM_CHILDCARE_LEAVE", basis_required: true, blocks: [{ block_id: 92, scope: "item", order_item_id: 1, locale: "ru", block_type: "basis", generated_text: "Основание: личное заявление Тестов Сотрудник.", effective_text: "Основание: личное заявление Тестов Сотрудник.", review_status: "CURRENT", editable: true, revision: 1 }, { block_id: 93, scope: "item", order_item_id: 1, locale: "kk", block_type: "basis", generated_text: "Негіз: Тестов Сотрудниктің жеке өтініші.", effective_text: "Негіз: Тестов Сотрудниктің жеке өтініші.", review_status: "CURRENT", editable: true, revision: 1 }] }],
      },
    });

    for (const [language, label, value] of [["ru", "Основание:", "Личное заявление."], ["kk", "Негіз:", "Жеке өтініші."]] as const) {
      const { unmount } = render(<PersonnelOrderPrintDocument model={model} language={language} />);
      const document = screen.getByTestId("personnel-order-print-document");
      expect((document.textContent || "").split(label).length - 1, language).toBe(1);
      expect(screen.getByTestId("personnel-order-print-basis")).toHaveTextContent(`${label} ${value}`);
      expect(screen.getByTestId("personnel-order-print-basis")).not.toHaveTextContent("Тестов Сотрудник");
      expect(document).not.toHaveTextContent("Дополнительные распоряжения");
      expect(document).not.toHaveTextContent("Қосымша өкімдер");
      expect(document).not.toHaveTextContent("Контроль за исполнением приказа");
      expect(document).not.toHaveTextContent("Бұйрықтың орындалуын бақылауды");
      unmount();
    }
  });

  it("uses a CURRENT generated editorial body over the legacy payload template", () => {
    const model = buildPersonnelOrderPrintViewModel(detail, {
      editorial: {
        order_id: 42,
        order_status: "DRAFT",
        editable: true,
        order_blocks: [],
        items: [{
          order_item_id: 1,
          item_number: 1,
          item_type_code: "TRANSFER",
          basis_required: false,
          blocks: [{
            block_id: 70,
            scope: "item",
            order_item_id: 1,
            locale: "ru",
            block_type: "body",
            generated_text: "Актуальный editorial body.",
            effective_text: "Актуальный editorial body.",
            review_status: "CURRENT",
            editable: true,
            revision: 2,
          }],
        }],
      },
    });
    render(<PersonnelOrderPrintDocument model={model} language="ru" />);
    expect(screen.getByTestId("personnel-order-print-items")).toHaveTextContent("Актуальный editorial body.");
  });
});
