import { afterAll, afterEach, describe, expect, it, vi } from "vitest";

import { emptyIntakeDraftPayload, type IntakeDraftPayload } from "./intakeApi.client";
import {
  buildIntakePdfContentDisposition,
  buildIntakePdfFilename,
  buildIntakePdfHrefByApplicationId,
  buildIntakePdfHrefByToken,
} from "./intakePdfFilename";
import { INTAKE_PDF_DOCUMENT_CSS, INTAKE_PDF_SECTION_FLOW_CLASS } from "./intakePdfDocumentCss";
import {
  buildIntakePdfHtmlDocument,
  INTAKE_PDF_SECTION_TEST_IDS,
} from "./intakePdfDocumentHtml";
import { buildIntakePdfGeneratedDateLabel, formatIntakePdfGeneratedDate } from "./intakePdfDate";
import { getIntakePdfRenderer, INTAKE_PDF_OPTIONS } from "./intakePdfRenderer";
import { buildIntakePdfTrainingSummaries } from "./intakePdfSummaries";
import { buildIntakePdfViewModel } from "./intakePdfViewModel";
import type { EmploymentTenureCalculation } from "./employmentTenureFormat";
import { INTAKE_MILITARY_COMPOSITION_OPTIONS } from "@/lib/militaryDictionary";
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

/** Anonymized v2 shape matching the nullable fields of application 225. */
function canonicalV2NullPayload(): IntakeDraftPayload {
  return {
    ...emptyIntakeDraftPayload(),
    schema_version: 2,
    personal: {
      ...emptyIntakeDraftPayload().personal,
      last_name: "Тестов",
      first_name: "Тест",
      middle_name: "Тестович",
      photo_file_id: null,
    },
    contacts: { email: null, mobile_phone: "+77770000000", residence_address: null, registration_address: null },
    education: [{
      record_id: "10000000-0000-4000-8000-000000000001",
      start_date: "2013-09-01", end_date: "2020-06-30",
      institution_original: "Тестовый медицинский университет", institution_normalized: null,
      city: null, country_code: "KZ", education_type: "basic", document_type: "diploma",
      document_number: "TEST-001", document_date: null, specialty_original: "Общая медицина",
      specialty_normalized: null, qualification_original: "Врач", qualification_normalized: null,
      evidence_document_ids: [],
    }],
    employment_biography: [{
      record_id: "10000000-0000-4000-8000-000000000002",
      start_date: "2020-08-01", end_date: null, organization_original: "Тестовая поликлиника",
      organization_normalized: null, city: null, position_original: "врач-хирург",
      position_normalized: null, reason_for_leaving: null, note: null, evidence_document_ids: [],
    }],
    relatives: [{
      record_id: "10000000-0000-4000-8000-000000000003", relationship: "жена", relationship_other: null,
      full_name: "Тестова Тест Тестовна", birth_date: "1996-11-21", workplace: null,
    }],
    military: {
      status: "not_provided", rank: null, category: null, composition: null, commissariat: null,
      specialty_code: null, specialty_name: null, fitness_category: null, registration_group: null,
      registration_category: null,
    },
    training: [{
      record_id: "10000000-0000-4000-8000-000000000004", start_date: "2022-07-01", end_date: "2023-05-31",
      training_type: "primary_specialization", course_name_original: "Тестовый курс", course_name_normalized: null,
      specialty_original: "Онкология", specialty_normalized: null, institution_original: "Тестовый центр",
      institution_normalized: null, document_type: "certificate", document_number: "123456", document_date: null,
      hours: 840, hours_is_manual: true, study_leave_type: "unknown", employment_continued: null,
      evidence_document_ids: [],
    }],
    additional: {
      foreign_languages: [], foreign_languages_none: true, awards: [], awards_none: true,
      academic_degrees: [], academic_degrees_none: true, academic_titles: [], academic_titles_none: true,
    },
  } as unknown as IntakeDraftPayload;
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
    expect(html).toContain("Трудовая биография");
    expect(html).toContain("Работа в текущей организации");
    expect(html).toContain("КазНУ");
    expect(html).toContain("Первая помощь");
    expect(html).toContain("Призывник");
    expect(html).not.toContain("intake-pdf-employment-tenure-ymd");
    expect(html).not.toContain("total_decimal_years");

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
    expect(html).not.toContain("intake-pdf-employment-tenure-ymd");
    expect(html).not.toContain("Код специальности");
    expect(html).toContain("Призывник");
    expect(html).toContain("Иностранные языки: 0 зап.");
    expect(html).not.toMatch(/Иностранные языки<\/h3>\s*<p>0 зап\.<\/p>/);
  });

  it("localizes military composition enum values in PDF", () => {
    for (const option of INTAKE_MILITARY_COMPOSITION_OPTIONS) {
      const payload = samplePayload();
      payload.military.composition = option.value;
      const html = buildIntakePdfHtmlDocument(
        buildIntakePdfViewModel({
          applicationId: 42,
          payload,
          summaries: sampleSummaries(payload),
        }),
      );

      expect(html).toContain(option.label);
      expect(html).not.toContain(`>${option.value}<`);
    }
  });

  it("formats foreign language proficiency without nested parentheses", () => {
    const payload = samplePayload();
    payload.additional.foreign_languages = [
      { language: "Английский", proficiency: "Выше среднего (B2)" },
    ];

    const html = buildIntakePdfHtmlDocument(
      buildIntakePdfViewModel({
        applicationId: 42,
        payload,
        summaries: sampleSummaries(payload),
      }),
    );

    expect(html).toContain("Английский — Выше среднего (B2)");
    expect(html).not.toContain("Английский (Выше среднего (B2))");
  });

  it("allows additional section to flow after military without forced page break", () => {
    const payload = samplePayload();
    const html = buildIntakePdfHtmlDocument(
      buildIntakePdfViewModel({
        applicationId: 42,
        payload,
        summaries: sampleSummaries(payload),
      }),
    );

    expect(html).toContain(`class="intake-pdf-section ${INTAKE_PDF_SECTION_FLOW_CLASS}"`);
    expect(html).toContain('data-testid="intake-pdf-section-additional"');
    expect(html.indexOf('data-testid="intake-pdf-section-military"')).toBeLessThan(
      html.indexOf('data-testid="intake-pdf-section-additional"'),
    );
    expect(INTAKE_PDF_DOCUMENT_CSS).toMatch(
      /\.intake-pdf-section\s*\{[^}]*page-break-inside:\s*auto;/s,
    );
    expect(INTAKE_PDF_DOCUMENT_CSS).toMatch(
      /\.intake-pdf-document tr\s*\{[^}]*page-break-inside:\s*avoid;/s,
    );
    expect(INTAKE_PDF_DOCUMENT_CSS).toMatch(
      /\.intake-pdf-summary-block\s*\{[^}]*page-break-inside:\s*avoid;/s,
    );
  });

  it("uses continuous flow for education and relatives without forced section page breaks", () => {
    const payload = samplePayload();
    const html = buildIntakePdfHtmlDocument(
      buildIntakePdfViewModel({
        applicationId: 42,
        payload,
        summaries: sampleSummaries(payload),
      }),
    );

    for (const testId of ["intake-pdf-section-education", "intake-pdf-section-relatives"] as const) {
      expect(html).toContain(
        `class="intake-pdf-section ${INTAKE_PDF_SECTION_FLOW_CLASS}" data-testid="${testId}"`,
      );
    }

    expect(INTAKE_PDF_DOCUMENT_CSS).not.toMatch(
      /\.intake-pdf-section\s*\{[^}]*page-break-inside:\s*avoid;/s,
    );
    expect(html).toContain('class="intake-pdf-data-table"');
  });

  it("keeps all PDF sections in continuous document order", () => {
    const html = buildIntakePdfHtmlDocument(
      buildIntakePdfViewModel({
        applicationId: 42,
        payload: samplePayload(),
        summaries: sampleSummaries(),
      }),
    );

    for (let index = 0; index < INTAKE_PDF_SECTION_TEST_IDS.length - 1; index += 1) {
      const current = INTAKE_PDF_SECTION_TEST_IDS[index];
      const next = INTAKE_PDF_SECTION_TEST_IDS[index + 1];
      expect(html.indexOf(`data-testid="${current}"`)).toBeGreaterThan(-1);
      expect(html.indexOf(`data-testid="${next}"`)).toBeGreaterThan(-1);
      expect(html.indexOf(`data-testid="${current}"`)).toBeLessThan(
        html.indexOf(`data-testid="${next}"`),
      );
    }
  });

  it("protects section leads, table rows, summary cards and additional subsections from splits", () => {
    expect(INTAKE_PDF_DOCUMENT_CSS).toMatch(
      /\.intake-pdf-section-title\s*\{[^}]*page-break-after:\s*avoid;/s,
    );
    expect(INTAKE_PDF_DOCUMENT_CSS).toMatch(
      /\.intake-pdf-data-table thead\s*\{[^}]*page-break-after:\s*avoid;/s,
    );
    expect(INTAKE_PDF_DOCUMENT_CSS).toMatch(
      /\.intake-pdf-data-table tbody tr:first-child\s*\{[^}]*page-break-before:\s*avoid;/s,
    );
    expect(INTAKE_PDF_DOCUMENT_CSS).toMatch(
      /\.intake-pdf-document tr\s*\{[^}]*page-break-inside:\s*avoid;/s,
    );
    expect(INTAKE_PDF_DOCUMENT_CSS).toMatch(
      /\.intake-pdf-summary-block\s*\{[^}]*page-break-inside:\s*avoid;/s,
    );
    expect(INTAKE_PDF_DOCUMENT_CSS).toMatch(
      /\.intake-pdf-additional-subsection\s*\{[^}]*page-break-inside:\s*avoid;/s,
    );
    expect(INTAKE_PDF_DOCUMENT_CSS).toMatch(
      /\.intake-pdf-document table\s*\{[^}]*page-break-inside:\s*auto;/s,
    );
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

  it(
    "renders the full canonical-v2 nullable payload without null or undefined text",
    async () => {
      const payload = canonicalV2NullPayload();
      const model = buildIntakePdfViewModel({
        applicationId: 225,
        payload,
        summaries: sampleSummaries(payload),
      });
      const html = buildIntakePdfHtmlDocument(model);
      const pdf = await getIntakePdfRenderer().render(model);

      expect(html).not.toContain("null");
      expect(html).not.toContain("undefined");
      expect(pdf.byteLength).toBeGreaterThan(1000);
      expect(pdf.subarray(0, 5).toString("utf8")).toBe("%PDF-");
    },
    45_000,
  );
});

describe("intakePdfOpen client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("keeps a canonical v2 840-hour course inside the five-year window", () => {
    const payload = canonicalV2NullPayload();
    const summaries = buildIntakePdfTrainingSummaries(payload, "2026-09-19");
    expect(summaries.trainingHours.trainingHoursLast5y).toBe(840);
  });

  it("renders a localized not-provided military state without an empty fields table", () => {
    const html = buildIntakePdfHtmlDocument(buildIntakePdfViewModel({
      applicationId: 225,
      payload: canonicalV2NullPayload(),
      summaries: sampleSummaries(),
    }));
    expect(html).toContain("Сведения о воинском учёте не предоставлены");
    expect(html).not.toContain("<td>Звание</td><td>—</td>");
  });

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

  it("downloads the protected application PDF using the registered GET route and releases its object URL", async () => {
    const fetchMock = vi.fn(async () => new Response("%PDF-1.7", {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": 'attachment; filename="anketa-225-nurtaev.pdf"',
      },
    }));
    const createObjectUrl = vi.fn(() => "blob:pdf");
    const revokeObjectUrl = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", { createObjectURL: createObjectUrl, revokeObjectURL: revokeObjectUrl });
    vi.spyOn(window, "setTimeout").mockImplementation(((callback: TimerHandler) => {
      if (typeof callback === "function") callback();
      return 1 as unknown as number;
    }) as typeof window.setTimeout);

    const { downloadIntakePdfByApplicationId } = await import("./intakePdfOpen.client");
    const result = await downloadIntakePdfByApplicationId(225);

    expect(result).toEqual({ ok: true, href: "/directory/personnel-applications/225/intake/pdf" });
    expect(fetchMock).toHaveBeenCalledWith(
      "/directory/personnel-applications/225/intake/pdf",
      expect.objectContaining({ method: "GET", credentials: "same-origin" }),
    );
    expect(click).toHaveBeenCalledOnce();
    expect(createObjectUrl).toHaveBeenCalledOnce();
    expect(revokeObjectUrl).toHaveBeenCalledWith("blob:pdf");
  });

  it("uses a readable fallback filename when Content-Disposition is absent", async () => {
    const append = vi.spyOn(document.body, "appendChild");
    vi.stubGlobal("fetch", vi.fn(async () => new Response("%PDF-1.7", {
      status: 200,
      headers: { "Content-Type": "application/pdf" },
    })));
    vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:pdf"), revokeObjectURL: vi.fn() });
    vi.spyOn(window, "setTimeout").mockImplementation((() => 1) as typeof window.setTimeout);

    const { downloadIntakePdfByApplicationId } = await import("./intakePdfOpen.client");
    await downloadIntakePdfByApplicationId(225);

    const anchor = append.mock.calls[0]?.[0] as HTMLAnchorElement;
    expect(anchor.download).toBe("Анкета_225.pdf");
  });

  it.each([
    [401, "Требуется авторизация для скачивания PDF."],
    [403, "Недостаточно прав для скачивания PDF."],
    [404, "Анкета не найдена."],
    [422, "PDF временно невозможно сформировать из-за ошибки данных."],
    [500, "Сервер формирования PDF недоступен."],
  ])("returns a safe message for HTTP %i", async (status, message) => {
    vi.stubGlobal("fetch", vi.fn(async () => Response.json({ error: { code: "SAFE", message } }, { status })));
    const { downloadIntakePdfByApplicationId } = await import("./intakePdfOpen.client");
    await expect(downloadIntakePdfByApplicationId(225)).resolves.toMatchObject({
      ok: false,
      status,
      code: "SAFE",
      error: message,
    });
  });

  it("rejects a successful JSON or HTML response instead of downloading it as PDF", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>error</html>", {
      status: 200,
      headers: { "Content-Type": "text/html; charset=utf-8" },
    })));
    const { downloadIntakePdfByApplicationId } = await import("./intakePdfOpen.client");
    await expect(downloadIntakePdfByApplicationId(225)).resolves.toMatchObject({
      ok: false,
      status: 200,
      code: "UNEXPECTED_CONTENT_TYPE",
    });
  });
});
