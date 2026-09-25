import { describe, expect, it } from "vitest";

import {
  PERSONNEL_ORDER_PRINT_LANGUAGE_DEFAULT,
  buildPersonnelOrderPrintHref,
  isPersonnelOrderPrintLanguage,
  isPersonnelOrderPrintRoute,
  parsePersonnelOrderPrintLanguage,
} from "./personnelOrderPrintLanguage";
import { PERSONNEL_ORDER_PRINT_DICTIONARIES, statusMarkLinesForLanguage } from "./personnelOrderPrintLocale";
import {
  formatPersonnelOrderPrintDate,
  formatPersonnelOrderPrintDateLines,
  formatPersonnelOrderPrintStartDate,
  formatPersonnelOrderPrintRate,
  formatPersonnelOrderPrintRateValue,
  parsePersonnelOrderCalendarDate,
} from "./personnelOrderPrintFormat";
import { resolveLocalizedLines, resolveLocalizedText } from "./personnelOrderPrintLocalized";
import { renderPersonnelOrderPrintItemText } from "./personnelOrderPrintItemText";
import {
  buildPersonnelOrderPrintDocumentHtml,
  preambleIncludesOrderVerb,
} from "./personnelOrderPrintDocumentHtml";
import {
  buildPersonnelOrderPrintViewModel,
  type PersonnelOrderPrintViewModel,
} from "./personnelOrderPrintViewModel";
import type { PersonnelOrderDetailResponse } from "./personnelOrdersApi.client";

function sampleDetail(overrides?: Partial<PersonnelOrderDetailResponse["order"]>): PersonnelOrderDetailResponse {
  return {
    order: {
      order_id: 42,
      order_number: "12-К",
      order_date: "2026-07-10",
      order_type_code: "HIRE",
      order_class: "SIMPLE",
      status: "DRAFT",
      source_mode: "PAPER",
      legal_basis_article: "ст. 33 ТК РК",
      basis_summary: "Заявление работника",
      signed_by_name: "Иванов И.И.",
      signed_by_position: "Директор",
      created_by: 1,
      ...overrides,
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
        payload: {
          org_unit_id: 10,
          position_id: 20,
          employment_rate: 1,
        },
      },
    ],
    localized_texts: [
      {
        localized_text_id: 1,
        order_id: 42,
        locale: "kk",
        title: "Жұмысқа қабылдау туралы",
        preamble: null,
        body_text: null,
        render_version: 1,
        is_authoritative: true,
      },
      {
        localized_text_id: 2,
        order_id: 42,
        locale: "ru",
        title: "О приёме на работу",
        preamble: null,
        body_text: null,
        render_version: 1,
        is_authoritative: false,
      },
    ],
    attachments: [],
    prints: [],
    events: [],
  };
}

describe("personnelOrderPrintLanguage", () => {
  it("accepts kk, ru, kk-ru", () => {
    expect(isPersonnelOrderPrintLanguage("kk")).toBe(true);
    expect(isPersonnelOrderPrintLanguage("ru")).toBe(true);
    expect(isPersonnelOrderPrintLanguage("kk-ru")).toBe(true);
    expect(isPersonnelOrderPrintLanguage("en")).toBe(false);
  });

  it("parses missing and unknown language values", () => {
    expect(parsePersonnelOrderPrintLanguage(null)).toBe(PERSONNEL_ORDER_PRINT_LANGUAGE_DEFAULT);
    expect(parsePersonnelOrderPrintLanguage(undefined)).toBe("ru");
    expect(parsePersonnelOrderPrintLanguage("kk")).toBe("kk");
    expect(parsePersonnelOrderPrintLanguage("unknown")).toBeNull();
    expect(parsePersonnelOrderPrintLanguage("unknown", { fallbackToDefault: true })).toBe("ru");
  });

  it("builds print href and detects print route", () => {
    expect(buildPersonnelOrderPrintHref(42, "kk-ru")).toBe(
      "/directory/personnel/orders/42/print?language=kk-ru",
    );
    expect(isPersonnelOrderPrintRoute("/directory/personnel/orders/42/print")).toBe(true);
    expect(isPersonnelOrderPrintRoute("/directory/personnel/orders")).toBe(false);
  });
});

describe("personnelOrderPrint localization", () => {
  it("keeps service headings language-specific", () => {
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.ru.documentType).toBe("ПРИКАЗ");
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.kk.documentType).toBe("БҰЙРЫҚ");
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.ru.orderVerb).toContain("ПРИКАЗЫВАЮ");
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.kk.orderVerb).toContain("БҰЙЫРАМЫН");
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.ru.draft).toBe("ПРОЕКТ");
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.kk.draft).toBe("ЖОБА");
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.ru.readyForSignature).toBe("НА ПОДПИСЬ");
    expect(PERSONNEL_ORDER_PRINT_DICTIONARIES.kk.readyForSignature).toBe("ҚОЛ ҚОЮҒА");
  });

  it("maps print watermarks to human-facing labels", () => {
    expect(statusMarkLinesForLanguage("draft", "ru")).toEqual(["ПРОЕКТ"]);
    expect(statusMarkLinesForLanguage("draft", "kk")).toEqual(["ЖОБА"]);
    expect(statusMarkLinesForLanguage("draft", "kk-ru")).toEqual(["ЖОБА / ПРОЕКТ"]);
    expect(statusMarkLinesForLanguage("unsigned", "ru")).toEqual(["НА ПОДПИСЬ"]);
    expect(statusMarkLinesForLanguage("unsigned", "kk")).toEqual(["ҚОЛ ҚОЮҒА"]);
    expect(statusMarkLinesForLanguage("unsigned", "kk-ru")).toEqual(["ҚОЛ ҚОЮҒА / НА ПОДПИСЬ"]);
    expect(statusMarkLinesForLanguage("cancelled", "ru")).toEqual(["АННУЛИРОВАН"]);
    expect(statusMarkLinesForLanguage("cancelled", "kk")).toEqual(["КҮШІ ЖОЙЫЛҒАН"]);
  });

  it("falls back without undefined/null technical values", () => {
    expect(resolveLocalizedText({ kk: null, ru: undefined }, "kk", "fallback")).toBe("fallback");
    expect(resolveLocalizedLines({ kk: "A", ru: "A" }, "kk-ru")).toEqual(["A"]);
    expect(resolveLocalizedLines({ kk: "A", ru: "B" }, "kk-ru")).toEqual(["A", "B"]);
    expect(resolveLocalizedText({}, "ru")).toBe("—");
  });
});

describe("personnelOrderPrint formatters", () => {
  it("formats calendar dates without timezone shift", () => {
    expect(parsePersonnelOrderCalendarDate("2026-07-10")).toEqual({
      year: 2026,
      month: 7,
      day: 10,
    });
    expect(formatPersonnelOrderPrintDate("2026-07-10", "ru")).toBe("10 июля 2026 года");
    expect(formatPersonnelOrderPrintDate("2026-07-10", "kk")).toBe("2026 жылғы 10 шілде");
    expect(formatPersonnelOrderPrintDateLines("2026-07-10", "kk-ru")).toEqual([
      "2026 жылғы 10 шілде",
      "10 июля 2026 года",
    ]);
  });

  it("declines Kazakh start dates for every month", () => {
    const monthSuffixes = [
      "\u049b\u0430\u04a3\u0442\u0430\u0440\u0434\u0430\u043d", "\u0430\u049b\u043f\u0430\u043d\u043d\u0430\u043d", "\u043d\u0430\u0443\u0440\u044b\u0437\u0434\u0430\u043d", "\u0441\u04d9\u0443\u0456\u0440\u0434\u0435\u043d", "\u043c\u0430\u043c\u044b\u0440\u0434\u0430\u043d", "\u043c\u0430\u0443\u0441\u044b\u043c\u043d\u0430\u043d",
      "\u0448\u0456\u043b\u0434\u0435\u0434\u0435\u043d", "\u0442\u0430\u043c\u044b\u0437\u0434\u0430\u043d", "\u049b\u044b\u0440\u043a\u04af\u0439\u0435\u043a\u0442\u0435\u043d", "\u049b\u0430\u0437\u0430\u043d\u043d\u0430\u043d", "\u049b\u0430\u0440\u0430\u0448\u0430\u0434\u0430\u043d", "\u0436\u0435\u043b\u0442\u043e\u049b\u0441\u0430\u043d\u043d\u0430\u043d",
    ];
    monthSuffixes.forEach((month, index) => {
      const value = `2026-${String(index + 1).padStart(2, "0")}-05`;
      expect(formatPersonnelOrderPrintStartDate(value, "kk")).toBe(`2026 \u0436\u044b\u043b\u0493\u044b 5 ${month}`);
    });
  });

  it("formats rates by language", () => {
    expect(formatPersonnelOrderPrintRateValue(1)).toBe("1,0");
    expect(formatPersonnelOrderPrintRate(1, "ru")).toContain("ставки");
    expect(formatPersonnelOrderPrintRate(1, "kk")).toContain("мөлшерлеме");
  });
});

describe("buildPersonnelOrderPrintViewModel", () => {
  it("builds normalized print model with draft watermark and acknowledgements", () => {
    const model = buildPersonnelOrderPrintViewModel(sampleDetail(), {
      organizationName: "ММЦ г. Астана",
      orgUnitNames: { 10: "Хирургия" },
      positionNames: { 20: "Врач" },
    });

    expect(model.orderId).toBe(42);
    expect(model.orderNumber).toBe("12-К");
    expect(model.orderDate).toBe("2026-07-10");
    expect(model.statusMark).toBe("draft");
    expect(model.title.kk).toBe("Жұмысқа қабылдау туралы");
    expect(model.title.ru).toBe("О приёме на работу");
    expect(model.items).toHaveLength(1);
    expect(model.items[0]?.context.orgUnitName?.ru).toBe("Хирургия");
    expect(model.basis.length).toBeGreaterThan(0);
    expect(model.signatory?.fio).toBe("Иванов И.И.");
    expect(model.signatory?.position?.ru).toBe("Директор");
    expect(model.acknowledgements).toEqual([
      { employeeId: 7, employeeName: "Петрова Анна", acknowledgedOn: null },
    ]);
  });

  it("marks draft/unsigned/registered/voided correctly", () => {
    expect(buildPersonnelOrderPrintViewModel(sampleDetail({ status: "DRAFT" })).statusMark).toBe(
      "draft",
    );
    expect(
      buildPersonnelOrderPrintViewModel(sampleDetail({ status: "READY_FOR_SIGNATURE" })).statusMark,
    ).toBe("unsigned");
    expect(buildPersonnelOrderPrintViewModel(sampleDetail({ status: "SIGNED" })).statusMark).toBe(
      "none",
    );
    expect(
      buildPersonnelOrderPrintViewModel(sampleDetail({ status: "REGISTERED" })).statusMark,
    ).toBe("none");
    expect(buildPersonnelOrderPrintViewModel(sampleDetail({ status: "VOIDED" })).statusMark).toBe(
      "cancelled",
    );
  });

  it("uses document title for composite instead of technical type label", () => {
    const model = buildPersonnelOrderPrintViewModel(
      {
        ...sampleDetail({ order_type_code: "COMPOSITE", legal_basis_article: null, basis_summary: null }),
        localized_texts: [],
      },
    );
    expect(model.title.ru).toBe("О кадровых изменениях");
    expect(model.title.kk).toBe("Кадрлық өзгерістер туралы");
    expect(model.basis).toEqual([]);
  });

  it("uses the approved return-from-childcare-leave preamble when legacy editorial data is absent", () => {
    const detail = {
      ...sampleDetail({ order_type_code: "RETURN_FROM_CHILDCARE_LEAVE", legal_basis_article: null, basis_summary: null }),
      items: [{
        ...sampleDetail().items[0],
        item_type_code: "RETURN_FROM_CHILDCARE_LEAVE",
        effective_date: "2026-08-05",
        payload: {
          presentation_context: {
            position_name: { ru: "руководитель отдела кадров", kk: "кадрлар бөлімінің басшысы" },
            org_unit_name: { ru: "отдел кадров", kk: "кадрлар бөлімі" },
          },
        },
      }],
      localized_texts: [],
    };
    const model = buildPersonnelOrderPrintViewModel(detail, {});
    expect(model.title.ru).toBe("О выходе на работу из отпуска по уходу за ребёнком");
    expect(model.title.kk).toBe("Бала күтіміне байланысты демалыстан жұмысқа шығу туралы");
    expect(resolveLocalizedLines(model.preamble || {}, "ru")).toEqual([
      "В соответствии с Трудовым кодексом Республики Казахстан",
      "ПРИКАЗЫВАЮ:",
    ]);
    expect(resolveLocalizedLines(model.preamble || {}, "kk")).toEqual([
      "Қазақстан Республикасының Еңбек кодексіне сәйкес",
      "БҰЙЫРАМЫН:",
    ]);
    const html = buildPersonnelOrderPrintDocumentHtml(model, "ru");
    expect(html).toContain("Разрешить сотруднику");
    expect(html).toContain("Стаж работы ещё не определён.");
    expect(html).not.toContain("RETURN_FROM_CHILDCARE_LEAVE");
  });

  it("resolves signatory position from directory map when order field empty", () => {
    const model = buildPersonnelOrderPrintViewModel(
      sampleDetail({ signed_by_position: null }),
      { signatoryPosition: "Директор" },
    );
    expect(model.signatory.position?.ru).toBe("Директор");
  });

  it("prefers editorial effective title/body/basis over legacy and templates", () => {
    const model = buildPersonnelOrderPrintViewModel(sampleDetail(), {
      orgUnitNames: { 10: "Хирургия" },
      positionNames: { 20: "Врач" },
      editorial: {
        order_id: 42,
        order_status: "DRAFT",
        editable: true,
        order_blocks: [
          {
            block_id: 1,
            scope: "order",
            locale: "kk",
            block_type: "title",
            effective_text: "Редакциялық тақырып",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
          {
            block_id: 2,
            scope: "order",
            locale: "ru",
            block_type: "title",
            effective_text: "Редакционный заголовок",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
          {
            block_id: 3,
            scope: "order",
            locale: "ru",
            block_type: "preamble",
            effective_text: "Редакционная преамбула",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
        ],
        items: [
          {
            order_item_id: 1,
            item_number: 1,
            item_type_code: "HIRE",
            basis_required: true,
            blocks: [
              {
                block_id: 10,
                scope: "item",
                order_item_id: 1,
                locale: "ru",
                block_type: "body",
                effective_text: "OVERRIDE BODY RU",
                review_status: "CURRENT",
                editable: true,
                revision: 1,
              },
              {
                block_id: 11,
                scope: "item",
                order_item_id: 1,
                locale: "kk",
                block_type: "body",
                effective_text: "OVERRIDE BODY KK",
                review_status: "CURRENT",
                editable: true,
                revision: 1,
              },
              {
                block_id: 12,
                scope: "item",
                order_item_id: 1,
                locale: "ru",
                block_type: "basis",
                effective_text: "Основание: личное заявление.",
                review_status: "CURRENT",
                editable: true,
                revision: 1,
                basis_required: true,
              },
            ],
          },
        ],
      },
    });

    expect(model.title.ru).toBe("Редакционный заголовок");
    expect(model.title.kk).toBe("Редакциялық тақырып");
    expect(model.preamble?.ru).toBe("Редакционная преамбула");
    expect(model.items[0]?.body?.ru).toBe("OVERRIDE BODY RU");
    expect(model.items[0]?.body?.kk).toBe("OVERRIDE BODY KK");
    expect(model.items[0]?.basis?.ru).toContain("личное заявление");
    expect(model.basis.some((b) => b.ru?.includes("личное заявление"))).toBe(true);
  });

  it("falls back to legacy localized title when editorial absent", () => {
    const model = buildPersonnelOrderPrintViewModel(sampleDetail(), {});
    expect(model.title.ru).toBe("О приёме на работу");
    expect(model.items[0]?.body).toBeNull();
    expect(model.closing).toBeNull();
  });

  it("maps editorial closing effective text into the view model", () => {
    const model = buildPersonnelOrderPrintViewModel(sampleDetail(), {
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
          {
            block_id: 51,
            scope: "order",
            locale: "kk",
            block_type: "closing",
            effective_text: "Бұйрықты орындалу бақылауын өзімде қалдырамын.",
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
        ],
        items: [],
      },
    });
    expect(model.closing?.ru).toContain("Контроль за исполнением");
    expect(model.closing?.kk).toContain("бақылауын");
  });

  it("renders closing in shared HTML and omits empty closing", () => {
    const withClosing = buildPersonnelOrderPrintViewModel(sampleDetail(), {
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
    const html = buildPersonnelOrderPrintDocumentHtml(withClosing, "ru");
    expect(html).toContain('data-testid="personnel-order-print-closing"');
    expect(html).toContain("Контроль за исполнением приказа оставляю за собой.");
    expect(html).toContain('data-testid="personnel-order-print-tail-date"');
    expect(html).toContain("10 июля 2026 года");
    expect(html).toContain('data-testid="personnel-order-print-signature"');
    expect(html.indexOf("personnel-order-print-closing")).toBeLessThan(
      html.indexOf("personnel-order-print-tail-date"),
    );
    expect(html.indexOf("personnel-order-print-tail-date")).toBeLessThan(
      html.indexOf("personnel-order-print-signature"),
    );

    const withoutClosing = buildPersonnelOrderPrintViewModel(sampleDetail(), {});
    const htmlEmpty = buildPersonnelOrderPrintDocumentHtml(withoutClosing, "ru");
    expect(htmlEmpty).not.toContain('data-testid="personnel-order-print-closing"');
  });

  it("omits tail date when order_date is empty but keeps signature block", () => {
    const model = buildPersonnelOrderPrintViewModel(sampleDetail({ order_date: null }), {
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
    const html = buildPersonnelOrderPrintDocumentHtml(model, "ru");
    expect(html).not.toContain('data-testid="personnel-order-print-tail-date"');
    expect(html).toContain('data-testid="personnel-order-print-signature"');
  });

  it("renders tail date once in bilingual HTML", () => {
    const model = buildPersonnelOrderPrintViewModel(sampleDetail(), {
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
    const html = buildPersonnelOrderPrintDocumentHtml(model, "kk-ru");
    expect(html.match(/data-testid="personnel-order-print-tail-date"/g)?.length).toBe(1);
    expect(html).toContain("2026 жылғы 10 шілде");
    expect(html).toContain("10 июля 2026 года");
  });

  it("detects embedded order verb in editorial preamble to avoid duplication", () => {
    const preamble = {
      ru: "В соответствии с Трудовым кодексом Республики Казахстан ПРИКАЗЫВАЮ:",
      kk: null,
    };
    expect(preambleIncludesOrderVerb(preamble, "ru")).toBe(true);

    const custom = { ru: "Редакционная преамбула без глагола.", kk: null };
    expect(preambleIncludesOrderVerb(custom, "ru")).toBe(false);

    const model = buildPersonnelOrderPrintViewModel(sampleDetail(), {
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
            effective_text: preamble.ru,
            review_status: "CURRENT",
            editable: true,
            revision: 1,
          },
        ],
        items: [],
      },
    });
    const html = buildPersonnelOrderPrintDocumentHtml(model, "ru");
    const verbMatches = html.match(/personnel-order-print-order-verb/g) ?? [];
    expect(verbMatches).toHaveLength(0);
  });

  it("preserves item numbering for many active items", () => {
    const manyItems = Array.from({ length: 12 }, (_, index) => ({
      item_id: index + 1,
      order_id: 42,
      item_number: index + 1,
      item_type_code: "HIRE",
      item_status: "ACTIVE",
      employee_id: 100 + index,
      employee_name: `Сотрудник ${index + 1}`,
      effective_date: "2026-07-15",
      payload: {},
    }));
    const model = buildPersonnelOrderPrintViewModel(
      { ...sampleDetail(), items: manyItems },
      {},
    );
    expect(model.items).toHaveLength(12);
    expect(model.items.map((item) => item.itemNumber)).toEqual([
      1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,
    ]);
    const html = buildPersonnelOrderPrintDocumentHtml(model, "ru");
    expect(html).toContain('12.');
    expect(html).toContain("Сотрудник 12");
  });
});

describe("personnelOrderPrint item text", () => {
  it("renders hire text for ru/kk/kk-ru", () => {
    const model: PersonnelOrderPrintViewModel = buildPersonnelOrderPrintViewModel(sampleDetail(), {
      orgUnitNames: { 10: "Хирургия" },
      positionNames: { 20: "Врач" },
    });
    const ctx = model.items[0]!.context;
    expect(renderPersonnelOrderPrintItemText(ctx, "ru")[0]).toContain("Принять сотрудника");
    expect(renderPersonnelOrderPrintItemText(ctx, "ru")[0]).toContain("врач (хирургия)");
    expect(renderPersonnelOrderPrintItemText(ctx, "kk")[0]).toContain("жұмысқа қабылдансын");
    expect(renderPersonnelOrderPrintItemText(ctx, "kk-ru")).toHaveLength(2);
  });

  it("renders the Russian concurrent-duty wording with a normalized assignment", () => {
    const text = renderPersonnelOrderPrintItemText(
      {
        itemNumber: 2,
        itemTypeCode: "CONCURRENT_DUTY_START",
        employeeName: "Иванова Алия Сериковна",
        effectiveDate: "2026-07-10",
        orgUnitName: { ru: "Приемное", kk: null },
        positionName: { ru: "Санитар", kk: null },
        toOrgUnitName: null,
        toPositionName: null,
        rate: null,
        toRate: null,
        concurrentRate: 0.5,
        remainingRate: null,
        totalRate: null,
        terminationReason: null,
        payload: {},
      },
      "ru",
    )[0];
    expect(text).toContain("Разрешить сотруднику Иванова Алия Сериковна");
    expect(text).toContain("санитар (приемное отделение)");
    expect(text).toContain("с оплатой 0,5 ставки");
  });

  it("does not print a leave-days placeholder when the source does not confirm days", () => {
    const text = renderPersonnelOrderPrintItemText(
      {
        itemNumber: 1, itemTypeCode: "TERMINATION", employeeName: "Сотрудник", effectiveDate: "2026-02-01",
        orgUnitName: null, positionName: null, toOrgUnitName: null, toPositionName: null,
        rate: null, toRate: null, concurrentRate: null, remainingRate: null, totalRate: null,
        terminationReason: null, payload: {},
      },
      "ru",
    )[0];
    expect(text).toContain("Бухгалтерии произвести расчёт за неиспользованные дни отпуска.");
    expect(text).not.toContain("календарных дней");
    expect(text).not.toContain("— календарных");
  });
});
