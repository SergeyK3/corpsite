import { describe, expect, it } from "vitest";

import { emptyIntakeDraftPayload } from "./intakeApi.client";
import { formatIntakePdfAsOfIso, formatIntakePdfCalculationDateLabel } from "./intakePdfDate";
import { buildIntakePdfTrainingSummaries } from "./intakePdfSummaries";
import {
  buildIntakePdfCalculatedSummariesHtml,
  buildIntakePdfEmploymentTenureSummaryHtml,
  buildIntakePdfExpiringCertificatesSummaryHtml,
  buildIntakePdfTrainingHoursSummaryHtml,
} from "./intakePdfSummaryHtml";
import type { EmploymentTenureCalculation } from "./employmentTenureFormat";
import { addCalendarMonths, addCalendarYears } from "@/lib/trainingSummary";

const AS_OF = "2026-07-23";

function sampleEmploymentTenure(): EmploymentTenureCalculation {
  return {
    calculation_date: AS_OF,
    records: [],
    arithmetic_sum_days: 7705,
    overlap_excluded_days: 4737,
    total_days: 7705,
    total_decimal_years: 21.1,
    total_ymd: { years: 21, months: 1, days: 10 },
  };
}

describe("intakePdfDate as-of", () => {
  it("derives Asia/Almaty ISO date for calculations", () => {
    expect(formatIntakePdfAsOfIso(new Date("2026-07-23T12:00:00.000Z"))).toBe("2026-07-23");
    expect(formatIntakePdfCalculationDateLabel("2026-07-23")).toBe("23.07.2026");
  });
});

describe("intakePdfSummaries training", () => {
  it("uses shared trainingSummary logic with explicit as-of date", () => {
    const payload = emptyIntakeDraftPayload();
    payload.training = [
      {
        institution: "Org",
        course_name: "Safety",
        year_from: "2022-03-10",
        year_to: "2022-03-12",
        document_type: "certificate",
        document_number: "C-1",
        hours: "",
        hours_is_manual: false,
      },
    ];

    const summaries = buildIntakePdfTrainingSummaries(payload, AS_OF);
    expect(summaries.trainingHours.trainingHoursLast5y).toBe(24);
    expect(summaries.trainingHours.windowStart).toBe("2021-07-23");
  });
});

describe("intakePdfSummaryHtml", () => {
  it("renders employment tenure ymd breakdown and calculation date", () => {
    const html = buildIntakePdfEmploymentTenureSummaryHtml(sampleEmploymentTenure());
    expect(html).toContain("Общий стаж");
    expect(html).toContain("21 год 1 месяц 10 дней");
    expect(html).not.toContain("Дата расчёта:");
    expect(html).toContain('data-testid="intake-pdf-employment-tenure-ymd"');
  });

  it("renders training hours and expiring certificates", () => {
    const completedAt = addCalendarMonths(addCalendarYears(AS_OF, -5), 3);
    const payload = emptyIntakeDraftPayload();
    payload.training = [
      {
        institution: "Org",
        course_name: "Скорая помощь",
        year_from: completedAt,
        year_to: completedAt,
        document_type: "certificate",
        document_number: "X-1",
        hours: "16",
        hours_is_manual: true,
      },
    ];
    const training = buildIntakePdfTrainingSummaries(payload, AS_OF);
    const hoursHtml = buildIntakePdfTrainingHoursSummaryHtml(training.trainingHours);
    const expiringHtml = buildIntakePdfExpiringCertificatesSummaryHtml(training.expiringCertificates);

    expect(hoursHtml).toContain("Часы обучения за последние 5 лет: 16");
    expect(expiringHtml).toContain("Сертификаты, истекающие в ближайшие 6 месяцев");
    expect(expiringHtml).toContain("Скорая помощь");
    expect(expiringHtml).toContain("Осталось");
  });

  it("builds combined summary html for employment and training sections", () => {
    const payload = emptyIntakeDraftPayload();
    const { employmentSummaryHtml, trainingSummaryHtml } = buildIntakePdfCalculatedSummariesHtml({
      asOfIso: AS_OF,
      ...buildIntakePdfTrainingSummaries(payload, AS_OF),
      employmentTenure: sampleEmploymentTenure(),
    });

    expect(employmentSummaryHtml).not.toContain("Послужной список");
    expect(employmentSummaryHtml).toContain("21 год 1 месяц 10 дней");
    expect(trainingSummaryHtml).toContain("Часы обучения за последние 5 лет: 0");
  });
});
