import { describe, expect, it } from "vitest";

import {
  buildPersonnelOrderDocumentRequisitesDisplay,
  hasPersonnelOrderRequisitesDate,
  hasPersonnelOrderSignatory,
  mergePersonnelOrderRequisitesForPreview,
  resolvePersonnelOrderSignatoryDisplay,
} from "./personnelOrderDocumentRequisites";

describe("personnelOrderDocumentRequisites", () => {
  it("resolves signatory from frozen order header snapshots", () => {
    expect(
      resolvePersonnelOrderSignatoryDisplay({
        signed_by_name: " М. Тулеутаев ",
        signed_by_position: " Директор ",
      }),
    ).toEqual({
      position: "Директор",
      fio: "М. Тулеутаев",
    });
  });

  it("formats order date per editorial locale", () => {
    const ru = buildPersonnelOrderDocumentRequisitesDisplay(
      {
        order_date: "2026-07-18",
        signed_by_name: "М. Тулеутаев",
        signed_by_position: "Директор",
      },
      "ru",
    );
    expect(ru.formattedDate).toBe("18 июля 2026 года");

    const kk = buildPersonnelOrderDocumentRequisitesDisplay(
      {
        order_date: "2026-07-18",
        signed_by_name: "М. Тулеутаев",
        signed_by_position: "Директор",
      },
      "kk",
    );
    expect(kk.formattedDate).toBe("2026 жылғы 18 шілде");
  });

  it("detects missing date and signatory", () => {
    expect(hasPersonnelOrderRequisitesDate(null)).toBe(false);
    expect(hasPersonnelOrderRequisitesDate("2026-07-18")).toBe(true);
    expect(hasPersonnelOrderSignatory({ position: null, fio: null })).toBe(false);
    expect(hasPersonnelOrderSignatory({ position: "Директор", fio: null })).toBe(true);
    expect(hasPersonnelOrderSignatory({ position: null, fio: "Иванов" })).toBe(true);
  });

  it("prefers header-editor draft over saved order for in-drawer preview", () => {
    const saved = {
      order_date: "2026-07-10",
      signed_by_name: "М. Тулеутаев",
      signed_by_position: "Директор",
    };
    const draft = {
      order_date: "2026-07-18",
      signed_by_name: "К. Замещающий",
      signed_by_position: "И. о. директора",
    };
    expect(mergePersonnelOrderRequisitesForPreview(saved, draft)).toEqual(draft);
    expect(mergePersonnelOrderRequisitesForPreview(saved, null)).toEqual(saved);
  });
});
