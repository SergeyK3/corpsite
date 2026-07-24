import { formatTrainingSummaryDate, type ExpiringCertificateSummary, type TrainingHoursLast5ySummary } from "@/lib/trainingSummary";

import type { EmploymentTenureCalculation } from "./employmentTenureFormat";
import { formatTenureDisplay, formatTenureYmd } from "./employmentTenureFormat";
import type { IntakePdfCalculatedSummaries } from "./intakePdfSummaries";

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function cell(value: string | null | undefined): string {
  return escapeHtml(String(value ?? "").trim() || "—");
}

export function buildIntakePdfEmploymentTenureSummaryHtml(
  calculation: EmploymentTenureCalculation | null,
): string {
  if (!calculation) {
    return "";
  }

  return `<div class="intake-pdf-summary-block" data-testid="intake-pdf-employment-tenure-summary">
<p class="intake-pdf-summary-title">Общий стаж</p>
<p class="intake-pdf-summary-value" data-testid="intake-pdf-employment-total-tenure">${cell(formatTenureDisplay(calculation.total_days))}</p>
<p class="intake-pdf-summary-detail" data-testid="intake-pdf-employment-tenure-ymd">${cell(formatTenureYmd(calculation.total_ymd))}</p>
</div>`;
}

export function buildIntakePdfTrainingHoursSummaryHtml(summary: TrainingHoursLast5ySummary): string {
  return `<div class="intake-pdf-summary-block" data-testid="intake-pdf-training-hours-summary">
<p class="intake-pdf-summary-title" data-testid="intake-pdf-training-hours-value">Часы обучения за последние 5 лет: ${cell(String(summary.trainingHoursLast5y))}</p>
<p class="intake-pdf-summary-meta" data-testid="intake-pdf-training-hours-window">Период: ${cell(formatTrainingSummaryDate(summary.windowStart))} — ${cell(formatTrainingSummaryDate(summary.asOf))}</p>
</div>`;
}

export function buildIntakePdfExpiringCertificatesSummaryHtml(
  items: readonly ExpiringCertificateSummary[],
): string {
  const body =
    items.length === 0
      ? `<p class="intake-pdf-empty">Нет сертификатов, истекающих в ближайшие 6 месяцев.</p>`
      : `<table data-testid="intake-pdf-training-expiring-table"><thead><tr><th>Название</th><th>Дата истечения</th><th>Осталось дней</th></tr></thead><tbody>${items
          .map(
            (item) =>
              `<tr data-testid="intake-pdf-training-expiring-item"><td>${cell(item.title)}</td><td>${cell(formatTrainingSummaryDate(item.expiresAt))}</td><td>${cell(String(item.daysRemaining))}</td></tr>`,
          )
          .join("")}</tbody></table>`;

  return `<div class="intake-pdf-summary-block" data-testid="intake-pdf-training-expiring-summary">
<p class="intake-pdf-summary-title">Сертификаты, истекающие в ближайшие 6 месяцев</p>
${body}
</div>`;
}

export function buildIntakePdfCalculatedSummariesHtml(summaries: IntakePdfCalculatedSummaries): {
  employmentSummaryHtml: string;
  trainingSummaryHtml: string;
} {
  return {
    employmentSummaryHtml: buildIntakePdfEmploymentTenureSummaryHtml(summaries.employmentTenure),
    trainingSummaryHtml: [
      buildIntakePdfTrainingHoursSummaryHtml(summaries.trainingHours),
      buildIntakePdfExpiringCertificatesSummaryHtml(summaries.expiringCertificates),
    ].join(""),
  };
}
