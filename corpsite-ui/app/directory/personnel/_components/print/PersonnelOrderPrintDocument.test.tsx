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
  it("confirms selected language", () => {
    const onConfirm = vi.fn();
    render(
      <PersonnelOrderPrintLanguageDialog open onClose={vi.fn()} onConfirm={onConfirm} />,
    );
    fireEvent.click(screen.getByLabelText("Қазақша"));
    fireEvent.click(screen.getByTestId("personnel-order-print-open"));
    expect(onConfirm).toHaveBeenCalledWith("kk");
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

    const hint = screen.getByTestId("personnel-order-print-headers-hint");
    expect(hint).toHaveTextContent("Колонтитулы");
    expect(hint.className).toContain("print:hidden");
  });
});

describe("PersonnelOrderPrintDocument", () => {
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
      "Петрова Анна",
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
});
