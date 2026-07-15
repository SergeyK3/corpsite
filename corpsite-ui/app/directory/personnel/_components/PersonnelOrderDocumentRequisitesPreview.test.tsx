import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import PersonnelOrderDocumentRequisitesPreview from "./PersonnelOrderDocumentRequisitesPreview";

afterEach(() => {
  cleanup();
});

describe("PersonnelOrderDocumentRequisitesPreview", () => {
  it("renders date and signatory row after closing without embedding in closing text", () => {
    render(
      <PersonnelOrderDocumentRequisitesPreview
        order={{
          order_date: "2026-07-18",
          signed_by_name: "М. Тулеутаев",
          signed_by_position: "Директор",
        }}
        locale="ru"
      />,
    );

    expect(screen.getByTestId("personnel-order-requisites-date")).toHaveTextContent(
      "18 июля 2026 года",
    );
    const signatory = screen.getByTestId("personnel-order-requisites-signatory");
    expect(signatory).toHaveTextContent("Директор");
    expect(signatory).toHaveTextContent("М. Тулеутаев");
    expect(signatory.className).toContain("grid");
  });

  it("shows placeholders when date or signatory are missing", () => {
    render(
      <PersonnelOrderDocumentRequisitesPreview
        order={{
          order_date: "2026-07-18",
          signed_by_name: null,
          signed_by_position: null,
        }}
        locale="ru"
      />,
    );

    expect(screen.getByTestId("personnel-order-requisites-date")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-requisites-signatory-missing")).toBeInTheDocument();
  });

  it("shows empty hint when both requisites are missing", () => {
    render(
      <PersonnelOrderDocumentRequisitesPreview
        order={{ order_date: null, signed_by_name: null, signed_by_position: null }}
        locale="ru"
      />,
    );

    expect(screen.getByTestId("personnel-order-requisites-preview-empty")).toBeInTheDocument();
  });

  it("wraps long signatory position without overlapping FIO", () => {
    render(
      <PersonnelOrderDocumentRequisitesPreview
        order={{
          order_date: "2026-07-18",
          signed_by_name: "М. Тулеутаев",
          signed_by_position:
            "Заместитель директора по клинико-диагностической работе и качеству медицинских услуг",
        }}
        locale="ru"
      />,
    );

    const position = screen.getByTestId("personnel-order-requisites-signatory-position");
    const fio = screen.getByTestId("personnel-order-requisites-signatory-fio");
    expect(position.className).toContain("min-w-0");
    expect(fio.className).toContain("text-right");
    expect(fio).toHaveTextContent("М. Тулеутаев");
  });

  it("shows manual signatory override with position left and FIO right", () => {
    render(
      <PersonnelOrderDocumentRequisitesPreview
        order={{
          order_date: "2026-07-18",
          signed_by_name: "К. Замещающий",
          signed_by_position: "И. о. директора",
        }}
        locale="ru"
      />,
    );

    const position = screen.getByTestId("personnel-order-requisites-signatory-position");
    const fio = screen.getByTestId("personnel-order-requisites-signatory-fio");
    expect(position).toHaveTextContent("И. о. директора");
    expect(fio).toHaveTextContent("К. Замещающий");
    expect(fio.className).toContain("text-right");
    expect(screen.queryByText("М. Тулеутаев")).not.toBeInTheDocument();
  });
});
