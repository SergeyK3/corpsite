// FILE: corpsite-ui/app/directory/personnel/_components/PersonnelImportAnalyticsPageClient.tsx
"use client";

import * as React from "react";
import Link from "next/link";

import ImportBatchSubNav from "./ImportBatchSubNav";
import PersonnelSubNav from "./PersonnelSubNav";
import {
  getAgeDistribution,
  getCertificationAnalytics,
  getDepartmentAnalytics,
  getImportSummary,
  getPositionAnalytics,
  getRiskAnalytics,
  getSheetDiagnostics,
  getTrainingAnalytics,
  mapImportApiError,
  SHEET_TYPE_LABELS,
  type AgeBucket,
  type DepartmentRow,
  type ImportSummary,
  type PositionRow,
  type RiskRow,
  type SheetDiagnosticRow,
} from "../_lib/importApi.client";

function StatCard({ label, value, hint }: { label: string; value: number | string; hint?: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{value}</div>
      {hint ? <div className="mt-1 text-xs text-zinc-500">{hint}</div> : null}
    </div>
  );
}

function AgeBarChart({ buckets }: { buckets: AgeBucket[] }) {
  const max = Math.max(...buckets.map((b) => b.count), 1);
  return (
    <div className="space-y-3">
      {buckets.map((b) => (
        <div key={b.key} className="grid grid-cols-[72px_1fr_48px] items-center gap-3 text-sm">
          <span className="text-zinc-600 dark:text-zinc-400">{b.label}</span>
          <div className="h-5 overflow-hidden rounded bg-zinc-100 dark:bg-zinc-900">
            <div
              className="h-full rounded bg-blue-600"
              style={{ width: `${Math.max(4, (b.count / max) * 100)}%` }}
            />
          </div>
          <span className="text-right font-medium">{b.count}</span>
        </div>
      ))}
    </div>
  );
}

export default function PersonnelImportAnalyticsPageClient({ batchId }: { batchId: number }) {
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [summary, setSummary] = React.useState<ImportSummary | null>(null);
  const [ageBuckets, setAgeBuckets] = React.useState<AgeBucket[]>([]);
  const [departments, setDepartments] = React.useState<DepartmentRow[]>([]);
  const [positions, setPositions] = React.useState<PositionRow[]>([]);
  const [trainingTotal, setTrainingTotal] = React.useState(0);
  const [trainingExamples, setTrainingExamples] = React.useState<
    { row_id: number; full_name: string; department: string; training_raw: string }[]
  >([]);
  const [certGroups, setCertGroups] = React.useState<{ group: string; label: string; count: number }[]>([]);
  const [certTotal, setCertTotal] = React.useState(0);
  const [risks, setRisks] = React.useState<RiskRow[]>([]);
  const [sheetDiagnostics, setSheetDiagnostics] = React.useState<SheetDiagnosticRow[]>([]);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      getImportSummary(batchId),
      getAgeDistribution(batchId),
      getDepartmentAnalytics(batchId),
      getPositionAnalytics(batchId),
      getTrainingAnalytics(batchId),
      getCertificationAnalytics(batchId),
      getRiskAnalytics(batchId),
      getSheetDiagnostics(batchId),
    ])
      .then(([s, age, dept, pos, train, cert, risk, sheets]) => {
        if (cancelled) return;
        setSummary(s);
        setAgeBuckets(age.buckets);
        setDepartments(dept.items.slice(0, 30));
        setPositions(pos.items);
        setTrainingTotal(train.total_with_training);
        setTrainingExamples(train.examples);
        setCertGroups(cert.by_group);
        setCertTotal(cert.total_with_certification);
        setRisks(risk.items.filter((r) => r.count > 0));
        setSheetDiagnostics(sheets.items);
        setError(null);
      })
      .catch((e) => {
        if (!cancelled) setError(mapImportApiError(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [batchId]);

  const riskTotal = risks.reduce((acc, r) => acc + r.count, 0);

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <PersonnelSubNav />
      <ImportBatchSubNav batchId={batchId} />
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Кадровый паспорт</h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Batch #{batchId} — read-only аналитика staging</p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/directory/personnel/import"
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            ← Импорты
          </Link>
          <Link
            href={`/directory/personnel/import/${batchId}/training`}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
          >
            Образовательные профили
          </Link>
          <Link
            href={`/directory/personnel/import/${batchId}/review?mode=personnel`}
            className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Review персонала
          </Link>
        </div>
      </div>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      ) : null}

      {loading || !summary ? (
        <div className="py-12 text-center text-zinc-500">Загрузка аналитики…</div>
      ) : (
        <>
          <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
            <StatCard label="Строки сотрудников" value={summary.employee_roster_rows ?? summary.total_rows} />
            <StatCard label="Декларационные листы" value={summary.declaration_rows ?? 0} />
            <StatCard
              label="Технические / служебные строки"
              value={summary.technical_category_rows ?? 0}
            />
            <StatCard label="Без ИИН (персонал)" value={summary.missing_iin} />
            <StatCard label="Валидных ИИН" value={summary.valid_iin} />
          </div>

          <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
            <StatCard label="Всего строк в batch" value={summary.total_rows} hint="включая декларации" />
            <StatCard label="Врачи" value={summary.by_sheet_type.doctors ?? 0} />
            <StatCard label="СМР" value={summary.by_sheet_type.nurses ?? 0} />
            <StatCard label="С обучением" value={summary.with_training} />
            <StatCard label="С категорией" value={summary.with_certification} />
            <StatCard label="Рисков (сумма)" value={riskTotal} hint="см. блок рисков" />
          </div>

          <section className="mb-6 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500">
              Разделы staging
            </h2>
            <p className="mb-3 text-sm text-zinc-600 dark:text-zinc-400">
              Это строки исходного Excel-файла, сгруппированные по типам листов. Они не записаны в
              кадровый контур.
            </p>
            <div className="flex flex-wrap gap-2 text-sm">
              <Link
                href={`/directory/personnel/import/${batchId}/review?mode=personnel`}
                className="rounded-lg bg-blue-600 px-3 py-2 font-medium text-white hover:bg-blue-700"
              >
                Строки сотрудников ({summary.employee_roster_rows ?? 0})
              </Link>
              <Link
                href={`/directory/personnel/import/${batchId}/review?mode=declaration`}
                className="rounded-lg border border-zinc-300 px-3 py-2 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
              >
                Декларационные листы ({summary.declaration_rows ?? 0})
              </Link>
              <Link
                href={`/directory/personnel/import/${batchId}/review?mode=technical`}
                className="rounded-lg border border-zinc-300 px-3 py-2 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
              >
                Технические / служебные строки ({summary.technical_category_rows ?? 0})
              </Link>
            </div>
            {summary.by_declaration_group && Object.keys(summary.by_declaration_group).length > 0 ? (
              <ul className="mt-3 space-y-1 text-xs text-zinc-500">
                {Object.entries(summary.by_declaration_group).map(([group, count]) => (
                  <li key={group}>
                    {SHEET_TYPE_LABELS[group] || group}: {count}
                  </li>
                ))}
              </ul>
            ) : null}
          </section>

          <section className="mb-6 overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
            <h2 className="border-b border-zinc-200 px-4 py-3 text-sm font-semibold dark:border-zinc-800">
              Диагностика листов Excel
            </h2>
            <p className="border-b border-zinc-200 px-4 py-2 text-xs text-zinc-500 dark:border-zinc-800">
              Строки исходного файла по листам — не сотрудники кадрового контура и не документы
              реестра.
            </p>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-zinc-50 text-left text-[11px] uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
                  <tr>
                    <th className="px-3 py-2">Лист Excel</th>
                    <th className="px-3 py-2">Интерпретированный тип</th>
                    <th className="px-3 py-2">Всего строк</th>
                    <th className="px-3 py-2">Строки сотрудников</th>
                    <th className="px-3 py-2">Декларации</th>
                    <th className="px-3 py-2">Служебные</th>
                  </tr>
                </thead>
                <tbody>
                  {sheetDiagnostics.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-center text-zinc-500">
                        Нет данных по листам
                      </td>
                    </tr>
                  ) : (
                    sheetDiagnostics.map((sheet) => (
                      <tr key={sheet.sheet_name} className="border-t border-zinc-100 dark:border-zinc-800">
                        <td className="px-3 py-2 font-medium">{sheet.sheet_name}</td>
                        <td className="px-3 py-2">{SHEET_TYPE_LABELS[sheet.sheet_type] || sheet.sheet_type || "—"}</td>
                        <td className="px-3 py-2">{sheet.rows_total}</td>
                        <td className="px-3 py-2">{sheet.employee_rows}</td>
                        <td className="px-3 py-2">{sheet.declaration_rows}</td>
                        <td className="px-3 py-2">{sheet.technical_rows}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <div className="mb-6 grid gap-4 lg:grid-cols-2">
            <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-500">Возрастная структура</h2>
              <AgeBarChart buckets={ageBuckets} />
            </section>
            <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-500">По типам листов</h2>
              <ul className="space-y-2 text-sm">
                {Object.entries(summary.by_sheet_type).map(([key, count]) => (
                  <li key={key} className="flex justify-between">
                    <span>{SHEET_TYPE_LABELS[key] || key}</span>
                    <span className="font-medium">{count}</span>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <section className="mb-6 overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
            <h2 className="border-b border-zinc-200 px-4 py-3 text-sm font-semibold dark:border-zinc-800">
              Персонал по отделениям (top 30)
            </h2>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-zinc-50 text-left text-[11px] uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
                  <tr>
                    <th className="px-3 py-2">Отделение</th>
                    <th className="px-3 py-2">Всего</th>
                    <th className="px-3 py-2">Врачи</th>
                    <th className="px-3 py-2">СМР</th>
                    <th className="px-3 py-2">Младш.</th>
                    <th className="px-3 py-2">Ср. возраст</th>
                    <th className="px-3 py-2">65+</th>
                    <th className="px-3 py-2">Обуч.</th>
                    <th className="px-3 py-2">Катег.</th>
                  </tr>
                </thead>
                <tbody>
                  {departments.map((d) => (
                    <tr key={d.department} className="border-t border-zinc-100 dark:border-zinc-800">
                      <td className="max-w-xs truncate px-3 py-2" title={d.department}>
                        {d.department}
                      </td>
                      <td className="px-3 py-2">{d.total}</td>
                      <td className="px-3 py-2">{d.doctors}</td>
                      <td className="px-3 py-2">{d.nurses}</td>
                      <td className="px-3 py-2">{d.junior_staff}</td>
                      <td className="px-3 py-2">{d.average_age ?? "—"}</td>
                      <td className="px-3 py-2">{d.age_65_plus}</td>
                      <td className="px-3 py-2">{d.with_training}</td>
                      <td className="px-3 py-2">{d.with_certification}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <div className="mb-6 grid gap-4 lg:grid-cols-2">
            <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">Top 20 должностей</h2>
              <ul className="space-y-1 text-sm">
                {positions.map((p) => (
                  <li key={p.position} className="flex justify-between gap-2">
                    <span className="truncate" title={p.position}>
                      {p.position}
                    </span>
                    <span className="font-medium">{p.count}</span>
                  </li>
                ))}
              </ul>
            </section>
            <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
              <div className="mb-3 flex items-center justify-between gap-2">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
                  Обучение ({trainingTotal})
                </h2>
                <Link
                  href={`/directory/personnel/import/${batchId}/training`}
                  className="text-xs text-blue-600 hover:underline dark:text-blue-400"
                >
                  Документы / обучение →
                </Link>
              </div>
              <ul className="space-y-2 text-xs text-zinc-600 dark:text-zinc-400">
                {trainingExamples.map((ex) => (
                  <li key={ex.row_id}>
                    <span className="font-medium text-zinc-800 dark:text-zinc-200">{ex.full_name}</span>
                    <span className="text-zinc-400"> · {ex.department}</span>
                    <div className="mt-0.5">{ex.training_raw}</div>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <section className="mb-6 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
              Категории и сертификаты ({certTotal})
            </h2>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {certGroups.map((g) => (
                <div key={g.group} className="flex justify-between rounded-lg bg-zinc-50 px-3 py-2 text-sm dark:bg-zinc-900">
                  <span>{g.label}</span>
                  <span className="font-medium">{g.count}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
            <h2 className="border-b border-zinc-200 px-4 py-3 text-sm font-semibold dark:border-zinc-800">Кадровые риски</h2>
            <table className="min-w-full text-sm">
              <thead className="bg-zinc-50 text-left text-[11px] uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
                <tr>
                  <th className="px-4 py-2">Тип риска</th>
                  <th className="px-4 py-2">Количество</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody>
                {risks.map((r) => (
                  <tr key={r.risk_type} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="px-4 py-2">{r.label}</td>
                    <td className="px-4 py-2 font-medium">{r.count}</td>
                    <td className="px-4 py-2 text-right">
                      <Link
                        href={`/directory/personnel/import/${batchId}/review?mode=personnel&risk_type=${r.risk_type}`}
                        className="text-blue-600 hover:underline dark:text-blue-400"
                      >
                        показать строки
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
