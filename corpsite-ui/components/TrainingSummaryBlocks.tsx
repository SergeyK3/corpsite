"use client";

import {
  calculateExpiringCertificates,
  calculateTrainingHoursLast5y,
  formatTrainingSummaryDate,
  type ExpiringCertificateSummary,
  type TrainingSummaryRecord,
} from "@/lib/trainingSummary";

type Props = {
  records: readonly TrainingSummaryRecord[];
  asOfIso?: string;
  testIdPrefix?: string;
};

function ExpiringCertificateList({
  items,
  testIdPrefix,
}: {
  items: readonly ExpiringCertificateSummary[];
  testIdPrefix: string;
}) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-zinc-500" data-testid={`${testIdPrefix}-expiring-empty`}>
        Нет сертификатов, истекающих в ближайшие 6 месяцев.
      </p>
    );
  }

  return (
    <ul className="space-y-2" data-testid={`${testIdPrefix}-expiring-list`}>
      {items.map((item) => (
        <li
          key={`${item.title}-${item.expiresAt}`}
          className="rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-800"
          data-testid={`${testIdPrefix}-expiring-item`}
        >
          <div className="font-medium text-zinc-900 dark:text-zinc-100">{item.title}</div>
          <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
            Истекает: {formatTrainingSummaryDate(item.expiresAt)} · Осталось {item.daysRemaining} дней
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function TrainingSummaryBlocks({
  records,
  asOfIso,
  testIdPrefix = "training-summary",
}: Props) {
  const hoursSummary = calculateTrainingHoursLast5y(records, asOfIso);
  const expiringCertificates = calculateExpiringCertificates(records, asOfIso);

  return (
    <div className="grid gap-3 lg:grid-cols-2" data-testid={`${testIdPrefix}-blocks`}>
      <section
        className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40"
        data-testid={`${testIdPrefix}-hours-block`}
      >
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
          Часы обучения за последние 5 лет
        </h3>
        <p className="mt-2 text-2xl font-semibold text-zinc-900 dark:text-zinc-50" data-testid={`${testIdPrefix}-hours-value`}>
          {hoursSummary.trainingHoursLast5y}
        </p>
        <p className="mt-1 text-xs text-zinc-500" data-testid={`${testIdPrefix}-hours-window`}>
          Период: {formatTrainingSummaryDate(hoursSummary.windowStart)} — {formatTrainingSummaryDate(hoursSummary.asOf)}
        </p>
      </section>

      <section
        className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40"
        data-testid={`${testIdPrefix}-expiring-block`}
      >
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
          Сертификаты, истекающие в ближайшие 6 месяцев
        </h3>
        <div className="mt-3">
          <ExpiringCertificateList items={expiringCertificates} testIdPrefix={testIdPrefix} />
        </div>
      </section>
    </div>
  );
}
