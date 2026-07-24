import { afterAll, describe, expect, it, vi } from "vitest";

import { emptyIntakeDraftPayload } from "./intakeApi.client";
import {
  buildIntakePdfContentDisposition,
  buildIntakePdfFilename,
  buildIntakePdfHrefByApplicationId,
  buildIntakePdfHrefByToken,
} from "./intakePdfFilename";
import {
  buildIntakePdfHtmlDocument,
  INTAKE_PDF_SECTION_TEST_IDS,
} from "./intakePdfDocumentHtml";
import { buildIntakePdfGeneratedDateLabel, formatIntakePdfGeneratedDate } from "./intakePdfDate";
import { getIntakePdfRenderer, INTAKE_PDF_OPTIONS } from "./intakePdfRenderer";
import { buildIntakePdfTrainingSummaries } from "./intakePdfSummaries";
import { buildIntakePdfViewModel } from "./intakePdfViewModel";
import type { EmploymentTenureCalculation } from "./employmentTenureFormat";
import { closePersonnelOrderPdfBrowser } from "@/app/directory/personnel/_lib/personnelOrderPdfBrowser";

function samplePayload() {
  const payload = emptyIntakeDraftPayload();
  payload.personal.last_name = "Иванов";
  payload.personal.first_name = "Иван";
  payload.personal.middle_name = "Иванович";
  payload.personal.birth_date = "1990-05-15";
  payload.contacts.mobile_phone = "+77001234567";
  payload.education = [
    {
      education_type: "basic",
      institution: "КазНУ",
      year_from: "2018-09-01",
      year_to: "2022-06-30",
      specialty: "Прикладная информатика",
      qualification: "Бакалавр",
      document_type: "diploma",
      diploma_number: "123",
    },
  ];
  payload.training = [
    {
      institution: "Центр обучения",
      course_name: "Первая помощь",
      year_from: "2024-01-10",
      year_to: "2024-02-10",
      document_type: "certificate",
      document_number: "ПО-1",
      hours: "24",
      hours_is_manual: false,
    },
  ];
  payload.military.status = "Призывник";
  return payload;
}

const AS_OF = "2026-07-23";

function sampleSummaries(payload = samplePayload()) {
  return {
    asOfIso: AS_OF,
    ...buildIntakePdfTrainingSummaries(payload, AS_OF),
    employmentTenure: {
      calculation_date: AS_OF,
      records: [],
      arithmetic_sum_days: 365,
      overlap_excluded_days: 0,
      total_days: 365,
      total_decimal_years: 1.0,
      total_ymd: { years: 1, months: 0, days: 0 },
    } satisfies EmploymentTenureCalculation,
  };
}

describe("intakePdfDate", () => {
  it("formats generation date in Asia/Almaty as dd.mm.yyyy", () => {
    const label = buildIntakePdfGeneratedDateLabel(new Date("2026-07-23T12:00:00.000Z"));
    expect(formatIntakePdfGeneratedDate(new Date("2026-07-23T12:00:00.000Z"))).toMatch(/^\d{2}\.\d{2}\.\d{4}$/);
    expect(label).toMatch(/^Дата формирования: \d{2}\.\d{2}\.\d{4}$/);
  });
});

describe("intakePdfFilename", () => {
  it("builds hrefs and sanitized filenames", () => {
    expect(buildIntakePdfHrefByToken("abc-token")).toBe("/intake/abc-token/pdf");
    expect(buildIntakePdfHrefByApplicationId(42)).toBe("/directory/personnel-applications/42/intake/pdf");
    expect(buildIntakePdfFilename(42, "Иванов Иван")).toBe("anketa-42-ivanov-ivan.pdf");
    expect(buildIntakePdfContentDisposition("anketa-42.pdf")).toBe('inline; filename="anketa-42.pdf"');
  });
});

describe("intakePdfHtmlDocument", () => {
  it("includes header, Cyrillic content and all main sections", () => {
    const model = buildIntakePdfViewModel({
      applicationId: 42,
      payload: samplePayload(),
      generatedAt: new Date("2026-07-23T12:00:00.000Z"),
      summaries: sampleSummaries(),
    });
    const html = buildIntakePdfHtmlDocument(model);

    expect(html).toContain('charset="utf-8"');
    expect(html).toContain("Times New Roman");
    expect(html).toContain("font-size: 10pt");
    expect(html).toContain("ЛИЧНАЯ КАРТОЧКА");
    expect(html).toContain("таб.номер");
    expect(html).toContain('class="intake-pdf-title"');
    expect(html).toContain('data-testid="intake-pdf-photo-slot"');
    expect(html).toContain("Место для фотографии 3×4");
    expect(html).toContain("Иванов Иван Иванович");
    expect(html).toContain('data-testid="intake-pdf-alphabet"');
    expect(html).toContain("Дата формирования");
    expect(html).toContain("Послужной список");
    expect(html).toContain("КазНУ");
    expect(html).toContain("Первая помощь");
    expect(html).toContain("Призывник");
    expect(html).toContain("Часы обучения за последние 5 лет:");
    expect(html).toContain("Сертификаты, истекающие в ближайшие 6 месяцев");
    expect(html).toContain("Общий стаж");
    expect(html).toContain("1 год 0 месяцев 0 дней");

    for (const testId of INTAKE_PDF_SECTION_TEST_IDS) {
      expect(html).toContain(`data-testid="${testId}"`);
    }
  });

  it("renders personnel number and alphabet in top-right index box", () => {
    const payload = samplePayload();
    payload.personal.birth_place = "г. Алматы";
    payload.personal.personnel_number = "";

    const emptyNumberHtml = buildIntakePdfHtmlDocument(
      buildIntakePdfViewModel({
        applicationId: 42,
        payload,
        summaries: sampleSummaries(payload),
      }),
    );
    expect(emptyNumberHtml).toContain('data-testid="intake-pdf-personnel-number"></td>');
    expect(emptyNumberHtml).not.toContain("<td>Табельный номер</td>");

    payload.personal.personnel_number = "ТН-0042";
    const withNumberHtml = buildIntakePdfHtmlDocument(
      buildIntakePdfViewModel({
        applicationId: 42,
        payload,
        summaries: sampleSummaries(payload),
      }),
    );
    expect(withNumberHtml).toContain('data-testid="intake-pdf-personnel-number">ТН-0042</td>');
    expect(withNumberHtml).toContain(
      'class="intake-pdf-alphabet" data-testid="intake-pdf-alphabet">И</td>',
    );
    expect(withNumberHtml).toMatch(
      /\.intake-pdf-alphabet\s*\{[^}]*font-size:\s*20pt;[^}]*font-weight:\s*700;[^}]*text-align:\s*center;/s,
    );
    expect(withNumberHtml).not.toContain("intake-pdf-section-personal");
    expect(withNumberHtml).toContain("Гражданство");
    expect(withNumberHtml).toContain('class="intake-pdf-split-row"');
  });

  it("renders photo placeholder when no photo is uploaded", () => {
    const payload = samplePayload();
    const html = buildIntakePdfHtmlDocument(
      buildIntakePdfViewModel({
        applicationId: 42,
        payload,
        summaries: sampleSummaries(payload),
        photoDataUrl: null,
      }),
    );
    expect(html).toContain("Место для фотографии 3×4");
    expect(html).not.toContain('data-testid="intake-pdf-photo-image"');
  });

  it("renders uploaded photo inside 3x4 slot", () => {
    const payload = samplePayload();
    payload.personal.photo_file_id = "photo123";
    const html = buildIntakePdfHtmlDocument(
      buildIntakePdfViewModel({
        applicationId: 42,
        payload,
        summaries: sampleSummaries(payload),
        photoDataUrl: "data:image/jpeg;base64,QUJD",
      }),
    );
    expect(html).toContain('data-testid="intake-pdf-photo-image"');
    expect(html).toContain('src="data:image/jpeg;base64,QUJD"');
    expect(html).not.toContain("Место для фотографии 3×4");
    expect(html).toContain("width: 3cm");
    expect(html).toContain("height: 4cm");
  });

  it("omits employment calc date, limits military fields and inlines empty additional subsections", () => {
    const payload = samplePayload();
    const html = buildIntakePdfHtmlDocument(
      buildIntakePdfViewModel({
        applicationId: 42,
        payload,
        summaries: sampleSummaries(payload),
      }),
    );

    expect(html).not.toContain("intake-pdf-employment-tenure-calc-date");
    expect(html).not.toContain("Код специальности");
    expect(html).toContain("Призывник");
    expect(html).toContain("Иностранные языки: 0 зап.");
    expect(html).not.toMatch(/Иностранные языки<\/h3>\s*<p>0 зап\.<\/p>/);
  });
});

describe("intakePdfRenderer", () => {
  afterAll(async () => {
    await closePersonnelOrderPdfBrowser();
  });

  it("uses A4 options shared with personnel orders", () => {
    expect(INTAKE_PDF_OPTIONS.format).toBe("A4");
    expect(INTAKE_PDF_OPTIONS.displayHeaderFooter).toBe(false);
  });

  it(
    "renders a non-empty PDF with Cyrillic payload",
    async () => {
      const model = buildIntakePdfViewModel({
        applicationId: 42,
        payload: samplePayload(),
        summaries: sampleSummaries(),
      });
      const pdf = await getIntakePdfRenderer().render(model);
      expect(pdf.subarray(0, 5).toString("utf8")).toBe("%PDF-");
      expect(pdf.byteLength).toBeGreaterThan(1000);
    },
    45_000,
  );
});

describe("intakePdfOpen client", () => {
  it("opens blob URL in a new tab", async () => {
    const openMock = vi.fn(() => ({ focus: vi.fn() }));
    vi.stubGlobal("open", openMock);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        blob: async () => new Blob(["%PDF-1.4"], { type: "application/pdf" }),
      })),
    );
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:pdf"),
      revokeObjectURL: vi.fn(),
    });

    const { openIntakePdfByToken } = await import("./intakePdfOpen.client");
    const result = await openIntakePdfByToken("token-abc");
    expect(result.ok).toBe(true);
    expect(openMock).toHaveBeenCalledWith("blob:pdf", "_blank", "noopener,noreferrer");
  });
});
